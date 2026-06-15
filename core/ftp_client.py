# -*- coding: utf-8 -*-
"""
FTP客户端核心类 - 使用Socket实现FTP协议
"""
import socket
import re
import os
import threading
from typing import Optional, Tuple, List, Callable
from ..config import FTP_DEFAULT_PORT, FTP_TIMEOUT, FTP_ENCODING, CHUNK_SIZE


class TransferPaused(Exception):
    """传输被用户暂停"""
    pass


class TransferStopped(Exception):
    """传输被用户取消"""
    pass


class FTPClient:
    """FTP客户端类 - 基于Socket实现"""
    
    def __init__(self, host: str, port: int = FTP_DEFAULT_PORT, 
                 encoding: str = FTP_ENCODING, timeout: int = FTP_TIMEOUT):
        self.host = host
        self.port = port
        self.encoding = encoding
        self.timeout = timeout
        
        # 命令通道Socket
        self.cmd_socket: Optional[socket.socket] = None
        # 数据通道Socket
        self.data_socket: Optional[socket.socket] = None
        # 被动模式地址
        self.pasv_addr: Optional[Tuple[str, int]] = None
        
        # 连接状态
        self.connected = False
        self.logged_in = False
        self.binary_mode = False
        self._lock = threading.RLock()
        # 传输锁 - 确保同一时间只有一个传输操作（FTP协议限制）
        self._transfer_lock = threading.Lock()
        # 响应缓冲区 - 防止一次recv读取多个响应
        self._response_buffer = b""
        
        # 回调函数
        self._progress_callback: Optional[Callable] = None
        self._log_callback: Optional[Callable] = None
    
    def set_progress_callback(self, callback: Callable):
        """设置进度回调函数"""
        self._progress_callback = callback
    
    def set_log_callback(self, callback: Callable):
        """设置日志回调函数"""
        self._log_callback = callback
    
    def _log(self, message: str):
        """记录日志"""
        if self._log_callback:
            self._log_callback(message)
        else:
            print(message)
    
    def _send_command(self, command: str) -> Tuple[int, str]:
        """发送FTP命令并获取响应"""
        with self._lock:
            return self._send_command_raw(command)
    
    def _send_command_raw(self, command: str) -> Tuple[int, str]:
        """发送FTP命令并获取响应（不使用锁，调用者需持有锁）"""
        if not self.cmd_socket:
            raise Exception("未连接到服务器")
        
        self._log(f">> {command}")
        self.cmd_socket.sendall((command + "\r\n").encode(self.encoding))
        
        response = self._recv_response()
        self._log(f"<< {response}")
        
        lines = response.split('\n')
        last_line = lines[-1] if lines else response
        code_str = last_line[:3] if len(last_line) >= 3 else response[:3]
        code = int(code_str)
        return code, response
    
    def _recv_response(self) -> str:
        """接收服务器响应（需在 _lock 内调用）
        
        逐行读取，确保只消费一个完整响应，多余数据保留在缓冲区
        """
        response_lines = []
        
        # 先从缓冲区读取
        buf = self._response_buffer
        self._response_buffer = b""
        
        while True:
            # 从缓冲区提取一行
            while b"\r\n" in buf:
                line, buf = buf.split(b"\r\n", 1)
                line_str = line.decode(self.encoding, errors='replace')
                response_lines.append(line_str)
                
                # 检查是否是响应的最后一行
                # FTP响应格式: XYZ message (最后一行) 或 XYZ-message (续行)
                if len(line_str) >= 4 and line_str[3] == " ":
                    # 这是最后一行，保存剩余缓冲区
                    self._response_buffer = buf
                    return "\r\n".join(response_lines)
                elif len(line_str) >= 3 and line_str[0:3].isdigit() and "-" not in line_str[3:4]:
                    # 单行响应 (XYZ message)
                    self._response_buffer = buf
                    return "\r\n".join(response_lines)
            
            # 缓冲区没有完整行，从socket读取更多数据
            try:
                chunk = self.cmd_socket.recv(4096)
                if not chunk:
                    # 连接关闭
                    if response_lines:
                        return "\r\n".join(response_lines)
                    raise Exception("连接已关闭")
                buf += chunk
            except socket.timeout:
                # 超时，返回已读取的数据
                if response_lines:
                    self._response_buffer = buf
                    return "\r\n".join(response_lines)
                raise
    
    def connect(self) -> bool:
        """连接FTP服务器"""
        try:
            # 创建命令Socket
            self.cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.cmd_socket.settimeout(self.timeout)
            self.cmd_socket.connect((self.host, self.port))
            
            with self._lock:
                response = self._recv_response()
            self._log(f"<< {response}")
            
            code = int(response[:3])
            if code == 220:
                self.connected = True
                return True
            else:
                raise Exception(f"连接失败: {response}")
        except Exception as e:
            self._log(f"连接错误: {str(e)}")
            raise e
    
    def login(self, username: str = "anonymous", password: str = "") -> bool:
        """登录FTP服务器"""
        if not self.connected:
            raise Exception("请先连接服务器")
        
        # 发送用户名
        code, response = self._send_command(f"USER {username}")
        if code == 331:  # 需要密码
            code, response = self._send_command(f"PASS {password}")
        
        if code == 230:  # 登录成功
            self.logged_in = True
            # 设置二进制模式
            self.set_binary_mode()
            return True
        else:
            raise Exception(f"登录失败: {response}")
    
    def _drain_response(self):
        """清空缓冲区中可能残留的响应"""
        try:
            self.cmd_socket.setblocking(False)
            try:
                while True:
                    chunk = self.cmd_socket.recv(4096)
                    if not chunk:
                        break
            except BlockingIOError:
                pass
            except OSError:
                pass
            finally:
                self.cmd_socket.setblocking(True)
        except OSError:
            pass
    
    def _is_private_ip(self, ip: str) -> bool:
        """判断是否为内网/保留地址"""
        try:
            parts = [int(x) for x in ip.split('.')]
        except ValueError:
            return False
        if len(parts) != 4:
            return False
        if parts[0] == 10:
            return True
        if parts[0] == 172 and 16 <= parts[1] <= 31:
            return True
        if parts[0] == 192 and parts[1] == 168:
            return True
        if parts[0] in (127, 0):
            return True
        return False
    
    def _get_data_connection_hosts(self) -> List[str]:
        """获取数据连接候选主机（按优先级）"""
        pasv_host = self.pasv_addr[0]
        peer_host = self.cmd_socket.getpeername()[0]
        hosts = []
        
        if self._is_private_ip(pasv_host):
            hosts.append(peer_host)
            if self.host not in hosts:
                hosts.append(self.host)
        else:
            hosts.append(pasv_host)
            if peer_host not in hosts:
                hosts.append(peer_host)
            if self.host not in hosts:
                hosts.append(self.host)
        return hosts
    
    def _drain_pending_responses(self, timeout: float = 3.0):
        """读取传输结束后控制通道上残留的响应"""
        if not self.cmd_socket:
            return
        old_timeout = self.cmd_socket.gettimeout()
        self.cmd_socket.settimeout(timeout)
        try:
            while True:
                response = self._recv_response()
                self._log(f"<< {response} (drained)")
                code = int(response[:3]) if len(response) >= 3 else 0
                if code in (226, 426, 225, 250):
                    break
        except (socket.timeout, OSError, ValueError):
            pass
        finally:
            self.cmd_socket.settimeout(old_timeout)
    
    def _transfer_cleanup(self, data_socket: Optional[socket.socket] = None):
        """中止传输并同步控制通道状态"""
        if data_socket:
            self._close_data_connection(data_socket)
        if not self.cmd_socket:
            return
        try:
            self.cmd_socket.sendall(b'ABOR\r\n')
        except OSError:
            pass
        self._drain_pending_responses()
    
    def _close_data_on_error(self, data_socket: Optional[socket.socket]):
        """传输出错时仅关闭数据连接，不发送 ABOR"""
        if data_socket:
            self._close_data_connection(data_socket)
    
    def quit(self):
        """退出FTP服务器"""
        if self.connected:
            try:
                self._send_command("QUIT")
            except:
                pass
        self._close()
    
    def _close(self):
        """关闭连接"""
        if self.data_socket:
            try:
                self.data_socket.close()
            except:
                pass
            self.data_socket = None
        
        if self.cmd_socket:
            try:
                self.cmd_socket.close()
            except:
                pass
            self.cmd_socket = None
        
        self.connected = False
        self.logged_in = False
    
    def set_binary_mode(self) -> bool:
        """设置为二进制传输模式（断点续传需要）"""
        code, response = self._send_command("TYPE I")
        if code == 200:
            self.binary_mode = True
            return True
        raise Exception(f"设置二进制模式失败: {response}")
    
    def set_pasv(self) -> Tuple[str, int]:
        """进入被动模式"""
        with self._lock:
            return self.set_pasv_raw()
    
    def set_pasv_raw(self) -> Tuple[str, int]:
        """进入被动模式（不使用锁，调用者需持有锁）"""
        code, response = self._send_command_raw("PASV")
        
        if code != 227:
            raise Exception(f"进入被动模式失败: {response}")
        
        lines = response.split('\n')
        last_line = lines[-1] if lines else response
        
        match = re.search(r'\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)', last_line)
        if not match:
            match = re.search(r'\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)', response)
        
        if not match:
            raise Exception(f"无法解析被动模式地址: {response}")
        
        groups = match.groups()
        host = f"{groups[0]}.{groups[1]}.{groups[2]}.{groups[3]}"
        port = int(groups[4]) * 256 + int(groups[5])
        
        self.pasv_addr = (host, port)
        return self.pasv_addr
    
    def _ensure_control_ready(self):
        """传输前清空控制通道残留数据，避免响应错位"""
        if not self.cmd_socket:
            return
        try:
            self.cmd_socket.setblocking(False)
            try:
                while self.cmd_socket.recv(4096):
                    pass
            except BlockingIOError:
                pass
            except OSError:
                pass
            finally:
                self.cmd_socket.setblocking(True)
                self.cmd_socket.settimeout(self.timeout)
        except OSError:
            pass
    
    def _open_data_connection(self) -> socket.socket:
        """打开数据连接（PASV 后连接数据端口）"""
        print("_open_data_connection: 开始PASV...")  # 调试
        self.set_pasv()
        print(f"_open_data_connection: PASV成功，地址={self.pasv_addr}")  # 调试
        
        port = self.pasv_addr[1]
        hosts = self._get_data_connection_hosts()
        print(f"_open_data_connection: 尝试连接 hosts={hosts}, port={port}")  # 调试
        
        last_error = None
        for host in hosts:
            data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            data_socket.settimeout(self.timeout)
            try:
                print(f"_open_data_connection: 尝试连接 {host}:{port}")  # 调试
                data_socket.connect((host, port))
                print("_open_data_connection: 数据连接成功")  # 调试
                return data_socket
            except OSError as e:
                print(f"_open_data_connection: 连接失败 {host}:{port} - {str(e)}")  # 调试
                last_error = e
                data_socket.close()
        
        raise Exception(f"无法建立数据连接: {last_error}")
    
    def _close_data_connection(self, data_socket: socket.socket):
        """关闭数据连接"""
        try:
            data_socket.close()
        except:
            pass
    
    def pwd(self) -> str:
        """获取当前工作目录"""
        code, response = self._send_command("PWD")
        if code != 257:
            raise Exception(f"获取目录失败: {response}")
        
        # 解析目录路径，响应可能是多行
        lines = response.split('\n')
        last_line = lines[-1] if lines else response
        
        match = re.search(r'"([^"]+)"', last_line)
        if match:
            return match.group(1)
        # 尝试从整个响应中查找
        match = re.search(r'"([^"]+)"', response)
        if match:
            return match.group(1)
        return response
    
    def cwd(self, path: str) -> bool:
        """切换工作目录"""
        code, response = self._send_command(f"CWD {path}")
        if code == 250:
            return True
        raise Exception(f"切换目录失败: {response}")
    
    def mkd(self, path: str) -> bool:
        """创建目录"""
        code, response = self._send_command(f"MKD {path}")
        if code == 257:
            return True
        raise Exception(f"创建目录失败: {response}")
    
    def rmd(self, path: str) -> bool:
        """删除目录"""
        code, response = self._send_command(f"RMD {path}")
        if code == 250:
            return True
        raise Exception(f"删除目录失败: {response}")
    
    def dele(self, filename: str) -> bool:
        """删除文件"""
        code, response = self._send_command(f"DELE {filename}")
        if code == 250:
            return True
        raise Exception(f"删除文件失败: {response}")
    
    def rename(self, old_name: str, new_name: str) -> bool:
        """重命名文件"""
        code, response = self._send_command(f"RNFR {old_name}")
        if code != 350:
            raise Exception(f"重命名失败: {response}")
        
        code, response = self._send_command(f"RNTO {new_name}")
        if code == 250:
            return True
        raise Exception(f"重命名失败: {response}")
    
    def size(self, filename: str) -> int:
        """获取文件大小"""
        code, response = self._send_command(f"SIZE {filename}")
        if code == 213:
            # 响应可能是多行，从最后一行提取大小
            lines = response.split('\n')
            last_line = lines[-1] if lines else response
            parts = last_line.split()
            if len(parts) >= 2:
                return int(parts[1])
            # 尝试从整个响应中提取
            match = re.search(r'213\s+(\d+)', response)
            if match:
                return int(match.group(1))
        raise Exception(f"获取文件大小失败: {response}")
    
    def list(self, path: str = "") -> List[dict]:
        """列出目录内容"""
        print("list: 开始...")  # 调试
        
        with self._transfer_lock:
            print("list: 获取传输锁成功")  # 调试
            data_socket = None
            # 整个LIST操作使用同一个锁保护，避免响应错位
            with self._lock:
                try:
                    # 1. 进入被动模式
                    print("list: 发送PASV...")  # 调试
                    self.set_pasv_raw()
                    port = self.pasv_addr[1]
                    hosts = self._get_data_connection_hosts()
                    print(f"list: PASV: {self.pasv_addr[0]}:{port}, hosts={hosts}")  # 调试
                    
                    # 2. 连接数据端口
                    self._lock.release()
                    try:
                        connect_ok = False
                        for host in hosts:
                            data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            data_socket.settimeout(10)  # 10秒超时
                            try:
                                print(f"list: 连接数据端口 {host}:{port}")  # 调试
                                data_socket.connect((host, port))
                                connect_ok = True
                                print("list: 数据连接成功")  # 调试
                                break
                            except OSError as e:
                                print(f"list: 连接失败 {host}:{port} - {e}")  # 调试
                                data_socket.close()
                                data_socket = None
                        if not connect_ok:
                            raise Exception("无法建立数据连接")
                    finally:
                        self._lock.acquire()
                    
                    # 3. 发送LIST命令
                    cmd = f"LIST {path}" if path else "LIST"
                    print(f"list: 发送 {cmd}")  # 调试
                    code, response = self._send_command_raw(cmd)
                    print(f"list: 响应码={code}")  # 调试
                    if code not in (125, 150):
                        raise Exception(f"列出目录失败: {response}")
                except Exception:
                    if data_socket:
                        try: data_socket.close()
                        except: pass
                    raise
            
            # 4. 接收数据（不需要锁）
            print("list: 接收数据...")  # 调试
            data = b""
            try:
                while True:
                    chunk = data_socket.recv(4096)
                    if not chunk:
                        break
                    data += chunk
            finally:
                try: data_socket.close()
                except: pass
            
            print(f"list: 接收到 {len(data)} 字节")  # 调试
            
            # 5. 接收完成响应
            with self._lock:
                response = self._recv_response()
            self._log(f"<< {response}")
            
            decoded = data.decode(self.encoding, errors='ignore')
            return self._parse_list(decoded)
    
    def _parse_list(self, data: str) -> List[dict]:
        """解析LIST命令返回的数据"""
        items = []
        lines = data.strip().split("\n")
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split()
            if len(parts) < 4:
                continue
            
            # Unix格式: drwxr-xr-x 2 user group 4096 Jan 1 12:00 dirname
            # 或: -rw-r--r-- 1 user group 12345 Jan 1 12:00 filename
            if len(parts) >= 9 and parts[0][0] in ('d', '-', 'l'):
                is_dir = parts[0][0] == 'd'
                is_link = parts[0][0] == 'l'
                perms = parts[0]
                try:
                    size = int(parts[4])
                except ValueError:
                    size = 0
                name = ' '.join(parts[8:])
                if ' -> ' in name:
                    name = name.split(' -> ', 1)[0].strip()
                
                items.append({
                    'name': name,
                    'is_dir': is_dir,
                    'is_link': is_link,
                    'size': size,
                    'permissions': perms
                })
            # Windows格式: 01-01-12  12:00PM <DIR> dirname
            # 或: 01-01-12  12:00PM 12345 filename
            elif '<DIR>' in line:
                is_dir = True
                size = 0
                name = parts[-1]
                
                items.append({
                    'name': name,
                    'is_dir': is_dir,
                    'size': size,
                    'permissions': ''
                })
            elif len(parts) >= 4:
                # 尝试解析Windows格式的文件
                try:
                    size = int(parts[2].replace(',', ''))
                    is_dir = False
                    name = parts[-1]
                    
                    items.append({
                        'name': name,
                        'is_dir': is_dir,
                        'size': size,
                        'permissions': ''
                    })
                except:
                    pass
        
        return items
    
    def _format_transfer_error(self, action: str, response: str, code: int) -> str:
        """生成更易理解的传输错误信息"""
        lower = response.lower()
        if code == 550:
            if 'permission denied' in lower or 'access denied' in lower:
                return (f"{action}失败: 服务器拒绝写入。"
                        f"匿名 FTP（如 ftp.gnu.org）通常只允许下载，不支持上传。")
            if 'failed to open file' in lower:
                return f"{action}失败: 无法打开远程文件，请检查文件名或路径是否正确"
        return f"{action}失败: {response}"
    
    def download(self, remote_file: str, local_file: str, 
                 offset: int = 0, callback: Callable = None,
                 total_size: Optional[int] = None) -> bool:
        """下载文件，支持断点续传"""
        print(f"download: 开始 {remote_file} -> {local_file}")  # 调试
        
        if not self.binary_mode:
            self.set_binary_mode()
        
        with self._transfer_lock:
            print("download: 获取传输锁成功")  # 调试
            data_socket = None
            # 整个命令交互使用同一个锁保护，避免响应错位
            with self._lock:
                try:
                    # 1. 获取文件大小
                    if total_size is None:
                        try:
                            print("download: 发送SIZE...")  # 调试
                            code, response = self._send_command_raw(f"SIZE {remote_file}")
                            print(f"download: SIZE响应码={code}")  # 调试
                            if code == 213:
                                match = re.search(r'\d+\s+(\d+)', response)
                                if match:
                                    total_size = int(match.group(1))
                            if total_size is None:
                                total_size = 0
                        except Exception as e:
                            print(f"download: SIZE失败: {e}")  # 调试
                            total_size = 0
                    print(f"download: 文件大小={total_size}")  # 调试
                    
                    # 2. 进入被动模式
                    print("download: 发送PASV...")  # 调试
                    self.set_pasv_raw()
                    port = self.pasv_addr[1]
                    hosts = self._get_data_connection_hosts()
                    print(f"download: PASV: {self.pasv_addr[0]}:{port}")  # 调试
                    
                    # 3. 连接数据端口（释放锁避免阻塞）
                    self._lock.release()
                    try:
                        connect_ok = False
                        for host in hosts:
                            data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            data_socket.settimeout(10)  # 10秒超时
                            try:
                                print(f"download: 连接 {host}:{port}")  # 调试
                                data_socket.connect((host, port))
                                connect_ok = True
                                print("download: 数据连接成功")  # 调试
                                break
                            except OSError as e:
                                print(f"download: 连接失败 {host}:{port} - {e}")  # 调试
                                data_socket.close()
                                data_socket = None
                        if not connect_ok:
                            raise Exception("无法建立数据连接")
                    finally:
                        self._lock.acquire()
                    
                    # 4. 发送REST命令（断点续传）
                    if offset > 0:
                        print(f"download: 发送REST {offset}")  # 调试
                        code, response = self._send_command_raw(f"REST {offset}")
                        if code != 350:
                            print(f"download: REST失败，忽略 offset")  # 调试
                            offset = 0
                    
                    # 5. 发送RETR命令
                    print(f"download: 发送RETR {remote_file}")  # 调试
                    code, response = self._send_command_raw(f"RETR {remote_file}")
                    print(f"download: RETR响应码={code}")  # 调试
                    if code not in (125, 150):
                        raise Exception(self._format_transfer_error("下载", response, code))
                        
                except Exception as e:
                    print(f"download: 准备阶段错误: {e}")  # 调试
                    if data_socket:
                        try: data_socket.close()
                        except: pass
                    raise
            
            # 6. 接收文件数据（不需要锁）
            print("download: 开始接收数据...")  # 调试
            try:
                mode = 'ab' if offset > 0 else 'wb'
                with open(local_file, mode) as f:
                    transferred = offset
                    while True:
                        chunk = data_socket.recv(CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        transferred += len(chunk)
                        
                        if callback:
                            callback(transferred, total_size)
                        elif self._progress_callback:
                            self._progress_callback(transferred, total_size)
                
                print(f"download: 接收完成，共{transferred}字节")  # 调试
                data_socket.close()
                data_socket = None
                
                # 7. 接收完成响应
                print("download: 等待完成响应...")  # 调试
                with self._lock:
                    response = self._recv_response()
                self._log(f"<< {response}")
                print("download: 完成")  # 调试
                
            except (TransferPaused, TransferStopped):
                if data_socket:
                    self._transfer_cleanup(data_socket)
                raise
            except Exception as e:
                print(f"download: 接收错误: {e}")  # 调试
                if data_socket:
                    self._transfer_cleanup(data_socket)
                raise
        
        return True
    
    def upload(self, local_file: str, remote_file: str,
               offset: int = 0, callback: Callable = None) -> bool:
        """上传文件，支持断点续传"""
        print(f"upload: 开始 {local_file} -> {remote_file}")  # 调试
        
        if not self.binary_mode:
            self.set_binary_mode()
        
        total_size = os.path.getsize(local_file)
        print(f"upload: 文件大小={total_size}")  # 调试
        
        with self._transfer_lock:
            print("upload: 获取传输锁成功")  # 调试
            data_socket = None
            # 整个命令交互使用同一个锁保护，避免响应错位
            with self._lock:
                try:
                    # 1. 进入被动模式
                    print("upload: 发送PASV...")  # 调试
                    self.set_pasv_raw()
                    port = self.pasv_addr[1]
                    hosts = self._get_data_connection_hosts()
                    print(f"upload: PASV: {self.pasv_addr[0]}:{port}")  # 调试
                    
                    # 2. 连接数据端口（释放锁避免阻塞）
                    self._lock.release()
                    try:
                        connect_ok = False
                        for host in hosts:
                            data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            data_socket.settimeout(10)  # 10秒超时
                            try:
                                print(f"upload: 连接 {host}:{port}")  # 调试
                                data_socket.connect((host, port))
                                connect_ok = True
                                print("upload: 数据连接成功")  # 调试
                                break
                            except OSError as e:
                                print(f"upload: 连接失败 {host}:{port} - {e}")  # 调试
                                data_socket.close()
                                data_socket = None
                        if not connect_ok:
                            raise Exception("无法建立数据连接")
                    finally:
                        self._lock.acquire()
                    
                    # 3. 发送REST命令（断点续传）
                    if offset > 0:
                        print(f"upload: 发送REST {offset}")  # 调试
                        code, response = self._send_command_raw(f"REST {offset}")
                        if code != 350:
                            print(f"upload: REST失败，忽略 offset")  # 调试
                            offset = 0
                    
                    # 4. 发送STOR命令
                    print(f"upload: 发送STOR {remote_file}")  # 调试
                    code, response = self._send_command_raw(f"STOR {remote_file}")
                    print(f"upload: STOR响应码={code}")  # 调试
                    if code not in (125, 150):
                        raise Exception(self._format_transfer_error("上传", response, code))
                        
                except Exception as e:
                    print(f"upload: 准备阶段错误: {e}")  # 调试
                    if data_socket:
                        try: data_socket.close()
                        except: pass
                    raise
            
            # 5. 发送文件数据（不需要锁）
            print("upload: 开始发送数据...")  # 调试
            try:
                with open(local_file, 'rb') as f:
                    if offset > 0:
                        f.seek(offset)
                    
                    transferred = offset
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        data_socket.sendall(chunk)
                        transferred += len(chunk)
                        
                        if callback:
                            callback(transferred, total_size)
                        elif self._progress_callback:
                            self._progress_callback(transferred, total_size)
                
                print(f"upload: 发送完成，共{transferred}字节")  # 调试
                data_socket.close()
                data_socket = None
                
                # 6. 接收完成响应
                print("upload: 等待完成响应...")  # 调试
                with self._lock:
                    response = self._recv_response()
                self._log(f"<< {response}")
                print("upload: 完成")  # 调试
                
            except (TransferPaused, TransferStopped):
                if data_socket:
                    self._transfer_cleanup(data_socket)
                raise
            except Exception as e:
                print(f"upload: 发送错误: {e}")  # 调试
                if data_socket:
                    self._transfer_cleanup(data_socket)
                raise
        
        return True
    
    def abort(self):
        """中止当前传输"""
        if self.cmd_socket:
            self._send_command("ABOR")