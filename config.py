# -*- coding: utf-8 -*-
"""
FTP客户端配置文件
"""

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '200508140086',
    'database': 'ftp_client',
    'charset': 'utf8mb4'
}

# FTP默认配置
FTP_DEFAULT_PORT = 21
FTP_TIMEOUT = 30
FTP_ENCODING = 'utf-8'

# 传输配置
CHUNK_SIZE = 8192  # 传输块大小
MAX_RETRIES = 3    # 最大重试次数

# 界面配置
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700