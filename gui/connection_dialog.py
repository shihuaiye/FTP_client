# -*- coding: utf-8 -*-
"""
连接配置对话框
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QGroupBox, QDialogButtonBox
)
from PyQt5.QtCore import Qt

from ..models.ftp_connection import FTPConnection


class ConnectionDialog(QDialog):
    """连接配置对话框"""
    
    def __init__(self, parent=None, manage_mode=False):
        super().__init__(parent)
        self.manage_mode = manage_mode
        self.conn_model = FTPConnection()
        self.conn_data = None
        
        self.setWindowTitle("连接管理" if manage_mode else "新建连接")
        self.setMinimumSize(500, 400 if manage_mode else 300)
        
        self.init_ui()
        
        if manage_mode:
            self.load_connections()
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        if self.manage_mode:
            # 管理模式：显示连接列表
            self.create_connection_list(layout)
        else:
            # 新建模式：显示连接表单
            self.create_connection_form(layout)
    
    def create_connection_list(self, layout):
        """创建连接列表"""
        # 连接列表
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["名称", "主机", "端口", "用户名", "默认"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        
        btn_add = QPushButton("新建")
        btn_add.clicked.connect(self.add_connection)
        btn_layout.addWidget(btn_add)
        
        btn_edit = QPushButton("编辑")
        btn_edit.clicked.connect(self.edit_connection)
        btn_layout.addWidget(btn_edit)
        
        btn_delete = QPushButton("删除")
        btn_delete.clicked.connect(self.delete_connection)
        btn_layout.addWidget(btn_delete)
        
        btn_default = QPushButton("设为默认")
        btn_default.clicked.connect(self.set_default_connection)
        btn_layout.addWidget(btn_default)
        
        btn_layout.addStretch()
        
        btn_connect = QPushButton("连接")
        btn_connect.clicked.connect(self.connect_selected)
        btn_layout.addWidget(btn_connect)
        
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
    
    def create_connection_form(self, layout):
        """创建连接表单"""
        form_group = QGroupBox("连接信息")
        form_layout = QFormLayout(form_group)
        
        # 名称
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("连接名称")
        form_layout.addRow("名称:", self.name_edit)
        
        # 主机
        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("FTP服务器地址")
        form_layout.addRow("主机:", self.host_edit)
        
        # 端口
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(21)
        form_layout.addRow("端口:", self.port_spin)
        
        # 用户名
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("用户名 (匿名登录请留空)")
        form_layout.addRow("用户名:", self.username_edit)
        
        # 密码
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("密码")
        form_layout.addRow("密码:", self.password_edit)
        
        # 编码
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(["utf-8", "gbk", "gb2312", "latin-1"])
        form_layout.addRow("编码:", self.encoding_combo)
        
        layout.addWidget(form_group)
        
        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def load_connections(self):
        """加载连接列表"""
        connections = self.conn_model.get_all()
        
        self.table.setRowCount(len(connections))
        for i, conn in enumerate(connections):
            self.table.setItem(i, 0, QTableWidgetItem(conn['name'] or ''))
            self.table.setItem(i, 1, QTableWidgetItem(conn['host']))
            self.table.setItem(i, 2, QTableWidgetItem(str(conn['port'])))
            self.table.setItem(i, 3, QTableWidgetItem(conn['username'] or ''))
            self.table.setItem(i, 4, QTableWidgetItem("是" if conn['is_default'] else "否"))
            
            # 存储ID
            self.table.item(i, 0).setData(Qt.UserRole, conn['id'])
    
    def add_connection(self):
        """添加连接"""
        dialog = ConnectionDialog(self, manage_mode=False)
        if dialog.exec_():
            data = dialog.get_connection_data()
            try:
                self.conn_model.create(
                    name=data['name'],
                    host=data['host'],
                    port=data['port'],
                    username=data['username'],
                    password=data['password'],
                    encoding=data['encoding']
                )
                self.load_connections()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")
    
    def edit_connection(self):
        """编辑连接"""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "提示", "请选择要编辑的连接")
            return
        
        conn_id = self.table.item(selected[0].row(), 0).data(Qt.UserRole)
        conn_data = self.conn_model.get_by_id(conn_id)
        
        if conn_data:
            dialog = ConnectionDialog(self, manage_mode=False)
            dialog.set_connection_data(conn_data)
            if dialog.exec_():
                data = dialog.get_connection_data()
                try:
                    self.conn_model.update(
                        conn_id=conn_id,
                        name=data['name'],
                        host=data['host'],
                        port=data['port'],
                        username=data['username'],
                        password=data['password'],
                        encoding=data['encoding']
                    )
                    self.load_connections()
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"更新失败: {str(e)}")
    
    def delete_connection(self):
        """删除连接"""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "提示", "请选择要删除的连接")
            return
        
        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除选中的连接吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            conn_id = self.table.item(selected[0].row(), 0).data(Qt.UserRole)
            try:
                self.conn_model.delete(conn_id)
                self.load_connections()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除失败: {str(e)}")
    
    def set_default_connection(self):
        """设置默认连接"""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "提示", "请选择要设为默认的连接")
            return
        
        conn_id = self.table.item(selected[0].row(), 0).data(Qt.UserRole)
        try:
            self.conn_model.set_default(conn_id)
            self.load_connections()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"设置失败: {str(e)}")
    
    def connect_selected(self):
        """连接选中的服务器"""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "提示", "请选择要连接的服务器")
            return
        
        conn_id = self.table.item(selected[0].row(), 0).data(Qt.UserRole)
        conn_data = self.conn_model.get_by_id(conn_id)
        
        if conn_data:
            self.conn_data = conn_data
            self.accept()
    
    def set_connection_data(self, data):
        """设置连接数据（用于编辑）"""
        self.name_edit.setText(data['name'] or '')
        self.host_edit.setText(data['host'])
        self.port_spin.setValue(data['port'])
        self.username_edit.setText(data['username'] or '')
        self.password_edit.setText(data['password'] or '')
        
        index = self.encoding_combo.findText(data['encoding'] or 'utf-8')
        if index >= 0:
            self.encoding_combo.setCurrentIndex(index)
        
        # 存储ID用于更新
        self.edit_id = data['id']
    
    def get_connection_data(self):
        """获取连接数据"""
        return {
            'name': self.name_edit.text().strip(),
            'host': self.host_edit.text().strip(),
            'port': self.port_spin.value(),
            'username': self.username_edit.text().strip(),
            'password': self.password_edit.text(),
            'encoding': self.encoding_combo.currentText()
        }