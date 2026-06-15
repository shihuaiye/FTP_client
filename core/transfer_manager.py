# -*- coding: utf-8 -*-
"""
传输管理器 - 管理上传下载任务和断点续传
"""
import os
import threading
from typing import Optional, Callable
from enum import Enum

from .ftp_client import FTPClient, TransferPaused, TransferStopped
from ..models.transfer_record import TransferRecord
from ..config import CHUNK_SIZE


class TransferStatus(Enum):
    """传输状态枚举"""
    PENDING = 'pending'
    TRANSFERRING = 'transferring'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    FAILED = 'failed'


class TransferTask:
    """传输任务"""
    
    def __init__(self, task_id: int, transfer_type: str, local_path: str, 
                 remote_path: str, file_size: int, ftp_client: FTPClient):
        self.task_id = task_id
        self.transfer_type = transfer_type  # 'upload' or 'download'
        self.local_path = local_path
        self.remote_path = remote_path
        self.file_size = file_size
        self.ftp_client = ftp_client
        
        self.transferred = 0
        self.status = TransferStatus.PENDING
        self.error_message = ""
        
        # 回调函数
        self._progress_callback: Optional[Callable] = None
        self._complete_callback: Optional[Callable] = None
        self._error_callback: Optional[Callable] = None
        
        # 控制标志
        self._pause_flag = False
        self._stop_flag = False
        self._thread: Optional[threading.Thread] = None
    
    def set_callbacks(self, progress: Callable = None, 
                     complete: Callable = None, error: Callable = None):
        """设置回调函数"""
        self._progress_callback = progress
        self._complete_callback = complete
        self._error_callback = error
    
    def _progress_handler(self, transferred: int, total: int):
        """进度处理"""
        self.transferred = transferred
        
        # 更新文件大小（下载时file_size可能为0，由传输过程获取）
        if total > 0 and self.file_size == 0:
            self.file_size = total
        
        if self._pause_flag:
            self.status = TransferStatus.PAUSED
            raise TransferPaused()
        
        if self._stop_flag:
            raise TransferStopped()
        
        # 减少数据库更新频率：每1MB更新一次
        if transferred % (1024 * 1024) < CHUNK_SIZE or transferred == total:
            try:
                record_model = TransferRecord()
                record_model.update_progress(self.task_id, transferred)
            except:
                pass  # 忽略数据库更新错误
        
        # 调用进度回调
        if self._progress_callback:
            self._progress_callback(transferred, total)
    
    def _wait_thread(self, timeout: float = 30.0):
        """等待上一次传输线程结束"""
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
    
    def start(self, offset: int = 0):
        """开始传输"""
        self._wait_thread()
        
        self.transferred = offset
        self.status = TransferStatus.TRANSFERRING
        self._pause_flag = False
        self._stop_flag = False
        
        def _transfer():
            try:
                if self.transfer_type == 'download':
                    self.ftp_client.download(
                        self.remote_path, 
                        self.local_path,
                        offset=offset,
                        callback=self._progress_handler,
                        total_size=self.file_size if self.file_size > 0 else None
                    )
                else:
                    self.ftp_client.upload(
                        self.local_path,
                        self.remote_path,
                        offset=offset,
                        callback=self._progress_handler
                    )
                
                self.status = TransferStatus.COMPLETED
                try:
                    TransferRecord().complete(self.task_id)
                except Exception:
                    pass
                
                if self._complete_callback:
                    self._complete_callback(self.task_id)
                    
            except TransferPaused:
                try:
                    TransferRecord().pause(self.task_id, self.transferred)
                except Exception:
                    pass
            except TransferStopped:
                self.status = TransferStatus.FAILED
                self.error_message = "传输已取消"
                try:
                    TransferRecord().pause(self.task_id, self.transferred)
                except Exception:
                    pass
            except Exception as e:
                self.status = TransferStatus.FAILED
                self.error_message = str(e)
                try:
                    TransferRecord().fail(self.task_id, str(e))
                except Exception:
                    pass
                
                if self._error_callback:
                    self._error_callback(self.task_id, str(e))
        
        self._thread = threading.Thread(target=_transfer, daemon=True)
        self._thread.start()
    
    def pause(self):
        """暂停传输"""
        self._pause_flag = True
    
    def resume(self):
        """恢复传输"""
        if self.status == TransferStatus.PAUSED:
            self._wait_thread()
            self.start(offset=self.transferred)
    
    def stop(self):
        """停止传输"""
        self._stop_flag = True


class TransferManager:
    """传输管理器"""
    
    def __init__(self):
        self.tasks = {}  # task_id -> TransferTask
        self.record_model = TransferRecord()
    
    def create_download_task(self, ftp_client: FTPClient, remote_file: str, 
                           local_path: str) -> TransferTask:
        """创建下载任务"""
        # 文件大小在传输时获取，避免多线程冲突
        file_size = 0
        
        # 创建数据库记录
        task_id = None
        try:
            task_id = self.record_model.create(
                file_name=os.path.basename(remote_file),
                local_path=local_path,
                remote_path=remote_file,
                file_size=file_size,
                transfer_type='download'
            )
        except Exception as e:
            print(f"创建数据库记录失败: {e}")
            # 如果数据库失败，使用临时ID
            task_id = -int(os.path.getmtime(local_path) if os.path.exists(local_path) else 0)
        
        # 创建任务对象
        task = TransferTask(
            task_id=task_id,
            transfer_type='download',
            local_path=local_path,
            remote_path=remote_file,
            file_size=file_size,
            ftp_client=ftp_client
        )
        
        if task_id and task_id > 0:
            self.tasks[task_id] = task
        return task
    
    def create_upload_task(self, ftp_client: FTPClient, local_file: str,
                          remote_path: str) -> TransferTask:
        """创建上传任务"""
        # 获取本地文件大小
        file_size = os.path.getsize(local_file)
        
        # 创建数据库记录
        task_id = None
        try:
            task_id = self.record_model.create(
                file_name=os.path.basename(local_file),
                local_path=local_file,
                remote_path=remote_path,
                file_size=file_size,
                transfer_type='upload'
            )
        except Exception as e:
            print(f"创建数据库记录失败: {e}")
            # 如果数据库失败，使用临时ID
            task_id = -int(os.path.getmtime(local_file))
        
        # 创建任务对象
        task = TransferTask(
            task_id=task_id,
            transfer_type='upload',
            local_path=local_file,
            remote_path=remote_path,
            file_size=file_size,
            ftp_client=ftp_client
        )
        
        if task_id and task_id > 0:
            self.tasks[task_id] = task
        return task
    
    def get_task(self, task_id: int) -> Optional[TransferTask]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def get_paused_tasks(self) -> list:
        """获取所有暂停的任务"""
        return [t for t in self.tasks.values() if t.status == TransferStatus.PAUSED]
    
    def load_incomplete_tasks(self, ftp_client: FTPClient) -> list:
        """从数据库加载未完成的任务"""
        records = self.record_model.get_incomplete_records()
        tasks = []
        
        for record in records:
            task = TransferTask(
                task_id=record['id'],
                transfer_type=record['transfer_type'],
                local_path=record['local_path'],
                remote_path=record['remote_path'],
                file_size=record['file_size'],
                ftp_client=ftp_client
            )
            task.transferred = record['transferred_size']
            task.status = TransferStatus.PAUSED if record['status'] == 'paused' else TransferStatus.FAILED
            
            self.tasks[record['id']] = task
            tasks.append(task)
        
        return tasks
    
    def remove_task(self, task_id: int):
        """移除任务"""
        if task_id in self.tasks:
            del self.tasks[task_id]
            self.record_model.delete(task_id)
    
    def clear_completed_tasks(self):
        """清除已完成的任务"""
        to_remove = [tid for tid, task in self.tasks.items() 
                    if task.status == TransferStatus.COMPLETED]
        for task_id in to_remove:
            self.remove_task(task_id)
        
        self.record_model.clear_completed()