# -*- coding: utf-8 -*-
"""
传输记录模型
"""
from .database import Database


class TransferRecord:
    """传输记录管理类"""
    
    def __init__(self):
        self.db = Database()
    
    def create(self, file_name, local_path, remote_path, file_size, transfer_type):
        """创建传输记录"""
        sql = """
            INSERT INTO transfer_records 
            (file_name, local_path, remote_path, file_size, transferred_size, transfer_type, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        return self.db.execute(sql, (
            file_name, local_path, remote_path, file_size, 0, transfer_type, 'pending'
        ))
    
    def update_progress(self, record_id, transferred_size, status='transferring'):
        """更新传输进度"""
        sql = """
            UPDATE transfer_records 
            SET transferred_size = %s, status = %s
            WHERE id = %s
        """
        return self.db.execute(sql, (transferred_size, status, record_id))
    
    def complete(self, record_id):
        """标记传输完成"""
        sql = "UPDATE transfer_records SET status = 'completed' WHERE id = %s"
        return self.db.execute(sql, (record_id,))
    
    def pause(self, record_id, transferred_size):
        """暂停传输"""
        sql = """
            UPDATE transfer_records 
            SET transferred_size = %s, status = 'paused'
            WHERE id = %s
        """
        return self.db.execute(sql, (transferred_size, record_id))
    
    def fail(self, record_id, error_message):
        """标记传输失败"""
        sql = """
            UPDATE transfer_records 
            SET status = 'failed', error_message = %s
            WHERE id = %s
        """
        return self.db.execute(sql, (error_message, record_id))
    
    def get_by_id(self, record_id):
        """根据ID获取记录"""
        sql = "SELECT * FROM transfer_records WHERE id = %s"
        return self.db.query_one(sql, (record_id,))
    
    def get_paused_records(self):
        """获取所有暂停的记录"""
        sql = "SELECT * FROM transfer_records WHERE status = 'paused' ORDER BY update_time DESC"
        return self.db.query(sql)
    
    def get_incomplete_records(self):
        """获取所有未完成的记录"""
        sql = """
            SELECT * FROM transfer_records 
            WHERE status IN ('paused', 'failed')
            ORDER BY update_time DESC
        """
        return self.db.query(sql)
    
    def delete(self, record_id):
        """删除记录"""
        sql = "DELETE FROM transfer_records WHERE id = %s"
        return self.db.execute(sql, (record_id,))
    
    def clear_completed(self):
        """清除已完成的记录"""
        sql = "DELETE FROM transfer_records WHERE status = 'completed'"
        return self.db.execute(sql)