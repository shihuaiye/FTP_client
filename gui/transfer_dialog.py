# -*- coding: utf-8 -*-
"""
传输进度对话框
"""
import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal

from ..core.transfer_manager import TransferStatus


class TransferDialog(QDialog):
    """传输进度对话框"""
    
    # 定义信号，用于线程安全的UI更新
    progress_signal = pyqtSignal(int, int)
    complete_signal = pyqtSignal(int)
    error_signal = pyqtSignal(int, str)
    
    def __init__(self, parent, task):
        super().__init__(parent)
        self.task = task
        self.setWindowTitle("文件传输")
        self.setMinimumSize(400, 200)
        
        self.init_ui()
        self.setup_callbacks()
        
        # 连接信号到UI更新方法
        self.progress_signal.connect(self._update_progress_ui)
        self.complete_signal.connect(self._on_complete_ui)
        self.error_signal.connect(self._on_error_ui)
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        # 文件名
        filename = os.path.basename(self.task.local_path)
        self.file_label = QLabel(f"文件: {filename}")
        layout.addWidget(self.file_label)
        
        # 传输类型
        transfer_type = "上传" if self.task.transfer_type == "upload" else "下载"
        self.type_label = QLabel(f"类型: {transfer_type}")
        layout.addWidget(self.type_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        if self.task.file_size > 0:
            self.progress_bar.setMaximum(self.task.file_size)
        else:
            self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)
        
        # 进度文本
        self.progress_label = QLabel("0 / 0")
        layout.addWidget(self.progress_label)
        
        # 状态
        self.status_label = QLabel("状态: 准备中...")
        layout.addWidget(self.status_label)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.clicked.connect(self.toggle_pause)
        btn_layout.addWidget(self.pause_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.cancel_transfer)
        btn_layout.addWidget(self.cancel_btn)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setEnabled(False)
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)
        
        # 定时更新
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(100)
    
    def setup_callbacks(self):
        """设置回调函数"""
        self.task.set_callbacks(
            progress=self.on_progress,
            complete=self.on_complete,
            error=self.on_error
        )
    
    def on_progress(self, transferred, total):
        """进度更新（在子线程中调用）"""
        # 发射信号，在主线程中更新UI
        self.progress_signal.emit(transferred, total)
    
    def on_complete(self, task_id):
        """传输完成（在子线程中调用）"""
        # 发射信号，在主线程中更新UI
        self.complete_signal.emit(task_id)
    
    def on_error(self, task_id, error_message):
        """传输错误（在子线程中调用）"""
        # 发射信号，在主线程中更新UI
        self.error_signal.emit(task_id, error_message)
    
    def _update_progress_ui(self, transferred, total):
        """更新进度UI（在主线程中调用）"""
        pass  # 由定时器更新
    
    def _on_complete_ui(self, task_id):
        """传输完成UI更新（在主线程中调用）"""
        self.status_label.setText("状态: 完成")
        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        
        QMessageBox.information(self, "完成", "文件传输完成")
    
    def _on_error_ui(self, task_id, error_message):
        """传输错误UI更新（在主线程中调用）"""
        self.status_label.setText(f"状态: 错误 - {error_message}")
        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        
        QMessageBox.critical(self, "错误", f"传输失败: {error_message}")
    
    def update_progress(self):
        """更新进度显示"""
        transferred = self.task.transferred
        total = self.task.file_size
        
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(transferred)
            
            # 格式化大小
            transferred_str = self.format_size(transferred)
            total_str = self.format_size(total)
            percent = (transferred / total) * 100
            
            self.progress_label.setText(f"{transferred_str} / {total_str} ({percent:.1f}%)")
        else:
            self.progress_bar.setValue(0)
            self.progress_label.setText("计算中...")
        
        # 更新状态
        status_map = {
            TransferStatus.PENDING: "准备中",
            TransferStatus.TRANSFERRING: "传输中",
            TransferStatus.PAUSED: "已暂停",
            TransferStatus.COMPLETED: "已完成",
            TransferStatus.FAILED: "失败"
        }
        self.status_label.setText(f"状态: {status_map.get(self.task.status, '未知')}")
        
        # 更新按钮状态
        if self.task.status == TransferStatus.COMPLETED:
            self.pause_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            self.close_btn.setEnabled(True)
        elif self.task.status == TransferStatus.PAUSED:
            self.pause_btn.setText("恢复")
        else:
            self.pause_btn.setText("暂停")
    
    def toggle_pause(self):
        """暂停/恢复传输"""
        if self.task.status == TransferStatus.PAUSED:
            self.task.resume()
            self.pause_btn.setText("暂停")
        else:
            self.task.pause()
            self.pause_btn.setText("恢复")
    
    def cancel_transfer(self):
        """取消传输"""
        reply = QMessageBox.question(
            self, "确认",
            "确定要取消传输吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.task.stop()
            self.status_label.setText("状态: 已取消")
            self.pause_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            self.close_btn.setEnabled(True)
    
    def closeEvent(self, event):
        """关闭事件"""
        self.timer.stop()
        event.accept()
    
    def format_size(self, size):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"