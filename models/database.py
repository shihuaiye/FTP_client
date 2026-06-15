# -*- coding: utf-8 -*-
"""
数据库连接和初始化模块
"""
import threading
import pymysql
from ..config import DB_CONFIG


class Database:
    """数据库管理类"""
    
    _instance = None
    _local = threading.local()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_connection(self):
        """获取当前线程的数据库连接"""
        conn = getattr(self._local, 'connection', None)
        try:
            if conn is None or not conn.open:
                conn = pymysql.connect(**DB_CONFIG)
                self._local.connection = conn
        except Exception:
            conn = pymysql.connect(**DB_CONFIG)
            self._local.connection = conn
        return conn
    
    def init_database(self):
        """初始化数据库和表"""
        # 先连接不指定数据库
        config = DB_CONFIG.copy()
        db_name = config.pop('database')
        
        conn = pymysql.connect(**config)
        cursor = conn.cursor()
        
        # 创建数据库
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET utf8mb4")
        cursor.execute(f"USE `{db_name}`")
        
        # 创建传输记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transfer_records (
                id INT PRIMARY KEY AUTO_INCREMENT,
                file_name VARCHAR(255) NOT NULL,
                local_path VARCHAR(500) NOT NULL,
                remote_path VARCHAR(500) NOT NULL,
                file_size BIGINT DEFAULT 0,
                transferred_size BIGINT DEFAULT 0,
                transfer_type ENUM('upload', 'download') NOT NULL,
                status ENUM('pending', 'transferring', 'paused', 'completed', 'failed') DEFAULT 'pending',
                error_message TEXT,
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_status (status),
                INDEX idx_file (file_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        # 创建FTP连接配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ftp_connections (
                id INT PRIMARY KEY AUTO_INCREMENT,
                name VARCHAR(100),
                host VARCHAR(255) NOT NULL,
                port INT DEFAULT 21,
                username VARCHAR(100),
                password VARCHAR(255),
                encoding VARCHAR(20) DEFAULT 'utf-8',
                is_default TINYINT DEFAULT 0,
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("数据库初始化完成")
    
    def execute(self, sql, params=None):
        """执行SQL语句"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params)
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def query(self, sql, params=None):
        """查询数据"""
        conn = self.get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        try:
            cursor.execute(sql, params)
            return cursor.fetchall()
        finally:
            cursor.close()
    
    def query_one(self, sql, params=None):
        """查询单条数据"""
        conn = self.get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        try:
            cursor.execute(sql, params)
            return cursor.fetchone()
        finally:
            cursor.close()
    
    def close(self):
        """关闭当前线程的数据库连接"""
        conn = getattr(self._local, 'connection', None)
        if conn and conn.open:
            conn.close()
            self._local.connection = None