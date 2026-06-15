# -*- coding: utf-8 -*-
"""
FTP客户端包初始化
"""
from .core.ftp_client import FTPClient
from .core.transfer_manager import TransferManager, TransferTask
from .models.database import Database
from .models.transfer_record import TransferRecord
from .models.ftp_connection import FTPConnection

__version__ = "1.0.0"
__all__ = [
    'FTPClient',
    'TransferManager',
    'TransferTask',
    'Database',
    'TransferRecord',
    'FTPConnection'
]