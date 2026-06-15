# -*- coding: utf-8 -*-
"""
FTP连接配置模型
"""
from .database import Database


class FTPConnection:
    """FTP连接配置管理类"""
    
    def __init__(self):
        self.db = Database()
    
    def create(self, name, host, port, username, password, encoding='utf-8', is_default=False):
        """创建连接配置"""
        # 如果设为默认，先取消其他默认
        if is_default:
            self.db.execute("UPDATE ftp_connections SET is_default = 0")
        
        sql = """
            INSERT INTO ftp_connections 
            (name, host, port, username, password, encoding, is_default)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        return self.db.execute(sql, (name, host, port, username, password, encoding, is_default))
    
    def update(self, conn_id, name, host, port, username, password, encoding='utf-8', is_default=False):
        """更新连接配置"""
        if is_default:
            self.db.execute("UPDATE ftp_connections SET is_default = 0")
        
        sql = """
            UPDATE ftp_connections 
            SET name = %s, host = %s, port = %s, username = %s, password = %s, encoding = %s, is_default = %s
            WHERE id = %s
        """
        return self.db.execute(sql, (name, host, port, username, password, encoding, is_default, conn_id))
    
    def delete(self, conn_id):
        """删除连接配置"""
        sql = "DELETE FROM ftp_connections WHERE id = %s"
        return self.db.execute(sql, (conn_id,))
    
    def get_by_id(self, conn_id):
        """根据ID获取配置"""
        sql = "SELECT * FROM ftp_connections WHERE id = %s"
        return self.db.query_one(sql, (conn_id,))
    
    def get_all(self):
        """获取所有配置"""
        sql = "SELECT * FROM ftp_connections ORDER BY is_default DESC, name"
        return self.db.query(sql)
    
    def get_default(self):
        """获取默认配置"""
        sql = "SELECT * FROM ftp_connections WHERE is_default = 1 LIMIT 1"
        return self.db.query_one(sql)
    
    def set_default(self, conn_id):
        """设置默认配置"""
        self.db.execute("UPDATE ftp_connections SET is_default = 0")
        sql = "UPDATE ftp_connections SET is_default = 1 WHERE id = %s"
        return self.db.execute(sql, (conn_id,))