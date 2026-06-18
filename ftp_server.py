# -*- coding: utf-8 -*-
"""
本地FTP测试服务器
使用方法: python ftp_server.py
"""
import os
import sys

try:
    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer
except ImportError:
    print("请先安装 pyftpdlib:")
    print("  pip install pyftpdlib")
    sys.exit(1)


def create_test_directory():
    """创建测试目录和文件"""
    test_dir = os.path.join(os.path.dirname(__file__), 'ftp_test')
    
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
        print(f"创建测试目录: {test_dir}")
    
    # 创建一些测试文件
    test_files = {
        'test1.txt': '这是测试文件1的内容\n用于测试FTP下载功能',
        'test2.txt': '这是测试文件2的内容\n包含一些中文字符',
        'test3.txt': '测试断点续传功能\n这个文件可以用来测试暂停和恢复',
        'readme.txt': 'FTP测试服务器\n用户名: test\n密码: 123456\n匿名用户只能下载'
    }
    
    for filename, content in test_files.items():
        filepath = os.path.join(test_dir, filename)
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"创建测试文件: {filename}")
    
    # 创建大文件用于测试断点续传
    large_file = os.path.join(test_dir, 'large_test.bin')
    if not os.path.exists(large_file):
        print("创建大测试文件 (100MB)...")
        with open(large_file, 'wb') as f:
            f.write(b'0' * 100 * 1024 * 1024)
        print("创建完成: large_test.bin")
    
    return test_dir


def start_ftp_server():
    """启动FTP服务器"""
    print("=" * 50)
    print("本地FTP测试服务器")
    print("=" * 50)
    
    # 创建测试目录
    test_dir = create_test_directory()
    print(f"\nFTP根目录: {test_dir}")
    
    # 创建授权器
    authorizer = DummyAuthorizer()
    
    # 添加用户（完整权限：读取、写入、删除）
    authorizer.add_user('test', '123456', test_dir, perm='elradfmw')
    
    # 添加匿名用户（只读权限）
    authorizer.add_anonymous(test_dir, perm='elr')
    
    # 创建FTP处理器
    handler = FTPHandler
    handler.authorizer = authorizer
    
    # 设置被动模式端口范围（避免防火墙问题）
    handler.passive_ports = range(60000, 60100)
    
    # 创建服务器
    server = FTPServer(('127.0.0.1', 21), handler)
    
    print("\n服务器配置:")
    print("  地址: 127.0.0.1:21")
    print("  用户名: test")
    print("  密码: 123456")
    print("  匿名用户: anonymous (只读)")
    print("\n按 Ctrl+C 停止服务器")
    print("=" * 50)
    
    # 启动服务器
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        server.close_all()


if __name__ == '__main__':
    start_ftp_server()