# -*- coding: utf-8 -*-
"""
FTP客户端主窗口
"""
import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeView, QTreeView, QToolBar, QAction, QStatusBar, QMessageBox,
    QFileDialog, QMenu, QInputDialog, QLabel, QPushButton, QComboBox,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QApplication
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem

from ..core.ftp_client import FTPClient
from ..core.transfer_manager import TransferManager, TransferStatus
from ..models.ftp_connection import FTPConnection
from ..models.database import Database
from .connection_dialog import ConnectionDialog
from .transfer_dialog import TransferDialog


class ConnectWorker(QThread):
    """连接工作线程"""
    finished = pyqtSignal(bool, str)  # 成功/失败, 消息
    
    def __init__(self, ftp_client, conn_data):
        super().__init__()
        self.ftp_client = ftp_client
        self.conn_data = conn_data
    
    def run(self):
        try:
            print("ConnectWorker: 开始连接...")  # 调试
            self.ftp_client.connect()
            print("ConnectWorker: 连接成功，开始登录...")  # 调试
            self.ftp_client.login(
                username=self.conn_data.get('username', 'anonymous'),
                password=self.conn_data.get('password', '')
            )
            print("ConnectWorker: 登录成功")  # 调试
            self.finished.emit(True, "连接成功")
        except Exception as e:
            print(f"ConnectWorker: 错误={str(e)}")  # 调试
            import traceback
            traceback.print_exc()
            self.finished.emit(False, str(e))


class ListWorker(QThread):
    """列表工作线程"""
    finished = pyqtSignal(bool, list, str)  # 成功/失败, 列表, 消息
    
    def __init__(self, ftp_client):
        super().__init__()
        self.ftp_client = ftp_client
    
    def run(self):
        try:
            print("ListWorker: 开始获取PWD...")  # 调试
            current_path = self.ftp_client.pwd()
            print(f"ListWorker: PWD结果={current_path}")  # 调试
            print("ListWorker: 开始获取LIST...")  # 调试
            items = self.ftp_client.list()
            print(f"ListWorker: 获取到{len(items)}个项目")  # 调试
            for item in items[:5]:  # 只打印前5个
                print(f"  - {item['name']} ({'目录' if item['is_dir'] else '文件'})")
            self.finished.emit(True, items, current_path)
        except Exception as e:
            print(f"ListWorker: 错误={str(e)}")  # 调试
            import traceback
            traceback.print_exc()
            self.finished.emit(False, [], str(e))


class CwdWorker(QThread):
    """切换目录工作线程"""
    finished = pyqtSignal(bool, str)  # 成功/失败, 消息
    
    def __init__(self, ftp_client, path):
        super().__init__()
        self.ftp_client = ftp_client
        self.path = path
    
    def run(self):
        try:
            self.ftp_client.cwd(self.path)
            self.finished.emit(True, "切换成功")
        except Exception as e:
            self.finished.emit(False, str(e))


class MainWindow(QMainWindow):
    """FTP客户端主窗口"""
    
    def __init__(self):
        super().__init__()
        
        # 初始化变量
        self.ftp_client = None
        self.transfer_manager = TransferManager()
        self.current_remote_path = ""
        self.current_local_path = os.path.expanduser("~")
        
        # 初始化数据库
        self.init_database()
        
        # 设置窗口
        self.setWindowTitle("FTP客户端")
        self.setMinimumSize(1000, 700)
        
        # 创建界面
        self.create_menu_bar()
        self.create_tool_bar()
        self.create_central_widget()
        self.create_status_bar()
        
        # 加载保存的连接
        self.load_connections()
        
        # 定时更新传输状态
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_transfer_status)
        self.timer.start(500)
    
    def init_database(self):
        """初始化数据库"""
        try:
            db = Database()
            db.init_database()
        except Exception as e:
            QMessageBox.critical(self, "数据库错误", f"数据库初始化失败: {str(e)}")
    
    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        
        connect_action = QAction("连接(&C)", self)
        connect_action.setShortcut("Ctrl+Shift+C")
        connect_action.triggered.connect(self.show_connection_dialog)
        file_menu.addAction(connect_action)
        
        disconnect_action = QAction("断开连接(&D)", self)
        disconnect_action.triggered.connect(self.disconnect)
        file_menu.addAction(disconnect_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 传输菜单
        transfer_menu = menubar.addMenu("传输(&T)")
        
        upload_action = QAction("上传文件(&U)", self)
        upload_action.setShortcut("Ctrl+U")
        upload_action.triggered.connect(self.upload_files)
        transfer_menu.addAction(upload_action)
        
        download_action = QAction("下载文件(&D)", self)
        download_action.setShortcut("Ctrl+D")
        download_action.triggered.connect(self.download_files)
        transfer_menu.addAction(download_action)
        
        transfer_menu.addSeparator()
        
        resume_action = QAction("恢复传输(&R)", self)
        resume_action.triggered.connect(self.show_resume_dialog)
        transfer_menu.addAction(resume_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        
        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_tool_bar(self):
        """创建工具栏"""
        toolbar = self.addToolBar("主工具栏")
        toolbar.setMovable(False)
        
        # 连接按钮
        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self.show_connection_dialog)
        toolbar.addWidget(self.connect_btn)
        
        # 断开连接按钮
        self.disconnect_btn = QPushButton("断开")
        self.disconnect_btn.clicked.connect(self.disconnect)
        self.disconnect_btn.setEnabled(False)
        toolbar.addWidget(self.disconnect_btn)
        
        toolbar.addSeparator()
        
        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_remote_list)
        self.refresh_btn.setEnabled(False)
        toolbar.addWidget(self.refresh_btn)
        
        # 上传按钮
        self.upload_btn = QPushButton("上传")
        self.upload_btn.clicked.connect(self.upload_files)
        self.upload_btn.setEnabled(False)
        toolbar.addWidget(self.upload_btn)
        
        # 下载按钮
        self.download_btn = QPushButton("下载")
        self.download_btn.clicked.connect(self.download_files)
        self.download_btn.setEnabled(False)
        toolbar.addWidget(self.download_btn)
        
        toolbar.addSeparator()
        
        # 连接选择下拉框
        self.connection_combo = QComboBox()
        self.connection_combo.setMinimumWidth(200)
        self.connection_combo.currentIndexChanged.connect(self.on_connection_selected)
        toolbar.addWidget(self.connection_combo)
        
        # 管理连接按钮
        manage_btn = QPushButton("管理")
        manage_btn.clicked.connect(self.manage_connections)
        toolbar.addWidget(manage_btn)
    
    def create_central_widget(self):
        """创建中心部件"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 本地文件列表
        local_widget = QWidget()
        local_layout = QVBoxLayout(local_widget)
        local_layout.setContentsMargins(0, 0, 0, 0)
        
        local_label = QLabel("本地文件")
        local_layout.addWidget(local_label)
        
        self.local_tree = QTreeWidget()
        self.local_tree.setHeaderLabels(["名称", "大小", "修改时间"])
        self.local_tree.setColumnWidth(0, 200)
        self.local_tree.itemDoubleClicked.connect(self.on_local_item_double_clicked)
        self.local_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.local_tree.customContextMenuRequested.connect(self.show_local_context_menu)
        local_layout.addWidget(self.local_tree)
        
        # 本地路径导航
        local_nav = QHBoxLayout()
        self.local_path_label = QLabel(self.current_local_path)
        local_nav.addWidget(QLabel("路径:"))
        local_nav.addWidget(self.local_path_label)
        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self.browse_local_folder)
        local_nav.addWidget(btn_browse)
        local_layout.addLayout(local_nav)
        
        splitter.addWidget(local_widget)
        
        # 远程文件列表
        remote_widget = QWidget()
        remote_layout = QVBoxLayout(remote_widget)
        remote_layout.setContentsMargins(0, 0, 0, 0)
        
        remote_label = QLabel("远程文件")
        remote_layout.addWidget(remote_label)
        
        self.remote_tree = QTreeWidget()
        self.remote_tree.setHeaderLabels(["名称", "大小", "类型", "权限"])
        self.remote_tree.setColumnWidth(0, 200)
        self.remote_tree.itemDoubleClicked.connect(self.on_remote_item_double_clicked)
        self.remote_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.remote_tree.customContextMenuRequested.connect(self.show_remote_context_menu)
        remote_layout.addWidget(self.remote_tree)
        
        # 远程路径导航
        remote_nav = QHBoxLayout()
        self.remote_path_label = QLabel("/")
        remote_nav.addWidget(QLabel("路径:"))
        remote_nav.addWidget(self.remote_path_label)
        remote_layout.addLayout(remote_nav)
        
        splitter.addWidget(remote_widget)
        
        # 传输队列
        transfer_widget = QWidget()
        transfer_layout = QVBoxLayout(transfer_widget)
        transfer_layout.setContentsMargins(0, 0, 0, 0)
        
        transfer_label = QLabel("传输队列")
        transfer_layout.addWidget(transfer_label)
        
        self.transfer_tree = QTreeWidget()
        self.transfer_tree.setHeaderLabels(["文件名", "进度", "状态", "大小"])
        self.transfer_tree.setColumnWidth(0, 200)
        transfer_layout.addWidget(self.transfer_tree)
        
        splitter.addWidget(transfer_widget)
        
        # 设置分割比例
        splitter.setSizes([333, 333, 334])
        
        layout.addWidget(splitter)
        
        # 刷新本地文件列表
        self.refresh_local_list()
    
    def create_status_bar(self):
        """创建状态栏"""
        self.statusBar().showMessage("就绪")
    
    def load_connections(self):
        """加载保存的连接"""
        conn_model = FTPConnection()
        connections = conn_model.get_all()
        
        self.connection_combo.clear()
        self.connection_combo.addItem("选择连接...", None)
        
        for conn in connections:
            self.connection_combo.addItem(f"{conn['name']} ({conn['host']})", conn['id'])
    
    def on_connection_selected(self, index):
        """连接选择改变"""
        conn_id = self.connection_combo.currentData()
        if conn_id:
            self.connect_to_server(conn_id)
    
    def show_connection_dialog(self):
        """显示连接对话框"""
        dialog = ConnectionDialog(self)
        if dialog.exec_():
            conn_data = dialog.get_connection_data()
            self.connect_with_data(conn_data)
    
    def connect_with_data(self, conn_data):
        """使用连接数据连接服务器"""
        self.statusBar().showMessage(f"正在连接 {conn_data['host']}...")
        
        # 创建FTP客户端
        self.ftp_client = FTPClient(
            host=conn_data['host'],
            port=conn_data.get('port', 21),
            encoding=conn_data.get('encoding', 'utf-8')
        )
        
        # 设置日志回调
        self.ftp_client.set_log_callback(self.log_message)
        
        # 使用工作线程连接
        self.connect_worker = ConnectWorker(self.ftp_client, conn_data)
        self.connect_worker.finished.connect(self.on_connect_finished)
        self.connect_worker.start()
    
    def on_connect_finished(self, success, message):
        """连接完成回调"""
        if success:
            self.on_connected()
            self.refresh_remote_list()
            self.statusBar().showMessage("连接成功")
        else:
            QMessageBox.critical(self, "连接失败", message)
            self.statusBar().showMessage("连接失败")
            self.ftp_client = None
    
    def connect_to_server(self, conn_id):
        """连接到服务器"""
        conn_model = FTPConnection()
        conn_data = conn_model.get_by_id(conn_id)
        
        if conn_data:
            self.connect_with_data(conn_data)
    
    def disconnect(self):
        """断开连接"""
        if self.ftp_client:
            try:
                self.ftp_client.quit()
            except:
                pass
            self.ftp_client = None
        
        self.on_disconnected()
        self.statusBar().showMessage("已断开连接")
    
    def on_connected(self):
        """连接成功后更新界面"""
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.upload_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
        
        # 清空远程列表
        self.remote_tree.clear()
    
    def on_disconnected(self):
        """断开连接后更新界面"""
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.upload_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        
        self.remote_tree.clear()
        self.remote_path_label.setText("/")
    
    def log_message(self, message):
        """记录日志消息"""
        self.statusBar().showMessage(message[:100])
    
    def refresh_local_list(self):
        """刷新本地文件列表"""
        self.local_tree.clear()
        
        try:
            # 添加上级目录
            parent_item = QTreeWidgetItem(["..", "", ""])
            parent_item.setData(0, Qt.UserRole, "parent")
            self.local_tree.addTopLevelItem(parent_item)
            
            # 列出当前目录
            items = os.listdir(self.current_local_path)
            for item in items:
                full_path = os.path.join(self.current_local_path, item)
                try:
                    is_dir = os.path.isdir(full_path)
                    size = 0 if is_dir else os.path.getsize(full_path)
                    mtime = os.path.getmtime(full_path)
                    
                    tree_item = QTreeWidgetItem([
                        item,
                        "" if is_dir else self.format_size(size),
                        self.format_time(mtime)
                    ])
                    tree_item.setData(0, Qt.UserRole, full_path)
                    tree_item.setData(0, Qt.UserRole + 1, "dir" if is_dir else "file")
                    
                    if is_dir:
                        tree_item.setIcon(0, self.style().standardIcon(self.style().SP_DirIcon))
                    else:
                        tree_item.setIcon(0, self.style().standardIcon(self.style().SP_FileIcon))
                    
                    self.local_tree.addTopLevelItem(tree_item)
                except:
                    pass
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法访问目录: {str(e)}")
        
        self.local_path_label.setText(self.current_local_path)
    
    def refresh_remote_list(self):
        """刷新远程文件列表"""
        if not self.ftp_client:
            return
        
        self.remote_tree.clear()
        self.statusBar().showMessage("正在获取目录列表...")
        
        # 使用工作线程获取列表
        self.list_worker = ListWorker(self.ftp_client)
        self.list_worker.finished.connect(self.on_list_finished)
        self.list_worker.start()
    
    def on_list_finished(self, success, items, path_or_error):
        """列表获取完成回调"""
        if success:
            self.current_remote_path = path_or_error
            self.remote_path_label.setText(self.current_remote_path)
            
            # 添加上级目录
            parent_item = QTreeWidgetItem(["..", "", "", ""])
            parent_item.setData(0, Qt.UserRole, "parent")
            self.remote_tree.addTopLevelItem(parent_item)
            
            for item in items:
                if item.get('is_link'):
                    item_type = "链接"
                elif item['is_dir']:
                    item_type = "目录"
                else:
                    item_type = "文件"
                tree_item = QTreeWidgetItem([
                    item['name'],
                    "" if item['is_dir'] else self.format_size(item['size']),
                    item_type,
                    item.get('permissions', '')
                ])
                tree_item.setData(0, Qt.UserRole, item['name'])
                tree_item.setData(0, Qt.UserRole + 1, "dir" if item['is_dir'] else "file")
                
                if item['is_dir']:
                    tree_item.setIcon(0, self.style().standardIcon(self.style().SP_DirIcon))
                else:
                    tree_item.setIcon(0, self.style().standardIcon(self.style().SP_FileIcon))
                
                self.remote_tree.addTopLevelItem(tree_item)
            
            self.statusBar().showMessage(f"目录: {self.current_remote_path}")
        else:
            QMessageBox.warning(self, "错误", f"无法列出目录: {path_or_error}")
            self.statusBar().showMessage("获取目录失败")
    
    def on_local_item_double_clicked(self, item, column):
        """本地文件双击事件"""
        item_type = item.data(0, Qt.UserRole + 1)
        path = item.data(0, Qt.UserRole)
        
        if item_type == "parent":
            # 返回上级目录
            self.current_local_path = os.path.dirname(self.current_local_path)
            self.refresh_local_list()
        elif item_type == "dir":
            # 进入目录
            self.current_local_path = path
            self.refresh_local_list()
    
    def on_remote_item_double_clicked(self, item, column):
        """远程文件双击事件"""
        if not self.ftp_client:
            return
        
        item_type = item.data(0, Qt.UserRole + 1)
        name = item.data(0, Qt.UserRole)
        
        if item_type == "parent":
            # 返回上级目录
            self.cwd_worker = CwdWorker(self.ftp_client, "..")
            self.cwd_worker.finished.connect(self.on_cwd_finished)
            self.cwd_worker.start()
        elif item_type == "dir":
            # 进入目录
            self.cwd_worker = CwdWorker(self.ftp_client, name)
            self.cwd_worker.finished.connect(self.on_cwd_finished)
            self.cwd_worker.start()
    
    def on_cwd_finished(self, success, message):
        """目录切换完成回调"""
        if success:
            self.refresh_remote_list()
        else:
            QMessageBox.warning(self, "错误", message)
    
    def show_local_context_menu(self, pos):
        """显示本地文件右键菜单"""
        item = self.local_tree.itemAt(pos)
        if not item:
            return
        
        menu = QMenu()
        
        upload_action = menu.addAction("上传")
        upload_action.triggered.connect(lambda: self.upload_selected_file(item))
        
        menu.exec_(self.local_tree.viewport().mapToGlobal(pos))
    
    def show_remote_context_menu(self, pos):
        """显示远程文件右键菜单"""
        if not self.ftp_client:
            return
        
        item = self.remote_tree.itemAt(pos)
        if not item:
            return
        
        item_type = item.data(0, Qt.UserRole + 1)
        name = item.data(0, Qt.UserRole)
        
        menu = QMenu()
        
        if item_type == "file":
            download_action = menu.addAction("下载")
            download_action.triggered.connect(lambda: self.download_selected_file(item))
            
            menu.addSeparator()
        
        delete_action = menu.addAction("删除")
        delete_action.triggered.connect(lambda: self.delete_remote_item(item))
        
        rename_action = menu.addAction("重命名")
        rename_action.triggered.connect(lambda: self.rename_remote_item(item))
        
        menu.exec_(self.remote_tree.viewport().mapToGlobal(pos))
    
    def upload_selected_file(self, item):
        """上传选中的文件"""
        item_type = item.data(0, Qt.UserRole + 1)
        path = item.data(0, Qt.UserRole)
        
        if item_type == "file":
            self.upload_file(path)
    
    def upload_files(self):
        """选择文件上传"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择要上传的文件", self.current_local_path
        )
        
        for file in files:
            self.upload_file(file)
    
    def upload_file(self, local_path):
        """上传单个文件"""
        if not self.ftp_client:
            QMessageBox.warning(self, "错误", "请先连接服务器")
            return
        
        filename = os.path.basename(local_path)
        remote_path = f"{self.current_remote_path}/{filename}".replace("//", "/")
        
        # 创建传输任务
        task = self.transfer_manager.create_upload_task(
            self.ftp_client, local_path, remote_path
        )
        
        # 显示传输对话框并启动传输
        dialog = TransferDialog(self, task)
        dialog.show()
        task.start()
    
    def download_selected_file(self, item):
        """下载选中的文件"""
        name = item.data(0, Qt.UserRole)
        remote_path = f"{self.current_remote_path}/{name}".replace("//", "/")
        local_path = os.path.join(self.current_local_path, name)
        
        self.download_file(remote_path, local_path)
    
    def download_files(self):
        """下载选中的文件"""
        selected = self.remote_tree.selectedItems()
        for item in selected:
            item_type = item.data(0, Qt.UserRole + 1)
            if item_type == "file":
                name = item.data(0, Qt.UserRole)
                remote_path = f"{self.current_remote_path}/{name}".replace("//", "/")
                local_path = os.path.join(self.current_local_path, name)
                self.download_file(remote_path, local_path)
    
    def download_file(self, remote_path, local_path):
        """下载单个文件"""
        if not self.ftp_client:
            QMessageBox.warning(self, "错误", "请先连接服务器")
            return
        
        # 检查文件是否已存在
        if os.path.exists(local_path):
            reply = QMessageBox.question(
                self, "确认",
                f"文件 {os.path.basename(local_path)} 已存在，是否覆盖？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        try:
            # 创建传输任务
            task = self.transfer_manager.create_download_task(
                self.ftp_client, remote_path, local_path
            )
            
            dialog = TransferDialog(self, task)
            dialog.show()
            task.start()
            
        except Exception as e:
            QMessageBox.critical(self, "下载错误", str(e))
    
    def delete_remote_item(self, item):
        """删除远程文件或目录"""
        if not self.ftp_client:
            return
        
        item_type = item.data(0, Qt.UserRole + 1)
        name = item.data(0, Qt.UserRole)
        
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除 {name} 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                if item_type == "dir":
                    self.ftp_client.rmd(name)
                else:
                    self.ftp_client.dele(name)
                self.refresh_remote_list()
            except Exception as e:
                QMessageBox.warning(self, "删除失败", str(e))
    
    def rename_remote_item(self, item):
        """重命名远程文件"""
        if not self.ftp_client:
            return
        
        old_name = item.data(0, Qt.UserRole)
        
        new_name, ok = QInputDialog.getText(
            self, "重命名", "新名称:", text=old_name
        )
        
        if ok and new_name:
            try:
                self.ftp_client.rename(old_name, new_name)
                self.refresh_remote_list()
            except Exception as e:
                QMessageBox.warning(self, "重命名失败", str(e))
    
    def browse_local_folder(self):
        """浏览本地文件夹"""
        folder = QFileDialog.getExistingDirectory(
            self, "选择文件夹", self.current_local_path
        )
        if folder:
            self.current_local_path = folder
            self.refresh_local_list()
    
    def show_resume_dialog(self):
        """显示恢复传输对话框"""
        if not self.ftp_client:
            QMessageBox.warning(self, "错误", "请先连接服务器")
            return
        
        # 加载未完成的任务
        tasks = self.transfer_manager.load_incomplete_tasks(self.ftp_client)
        
        if not tasks:
            QMessageBox.information(self, "提示", "没有可恢复的传输任务")
            return
        
        # 显示任务列表
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("恢复传输")
        dialog.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        list_widget = QListWidget()
        for task in tasks:
            progress = f"{task.transferred}/{task.file_size}" if task.file_size > 0 else "未知"
            list_widget.addItem(f"{task.transfer_type}: {os.path.basename(task.local_path)} ({progress})")
            list_widget.item(list_widget.count() - 1).setData(Qt.UserRole, task.task_id)
        
        layout.addWidget(list_widget)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec_() == QDialog.Accepted:
            current = list_widget.currentItem()
            if current:
                task_id = current.data(Qt.UserRole)
                task = self.transfer_manager.get_task(task_id)
                if task:
                    dialog = TransferDialog(self, task)
                    dialog.show()
                    task.resume()
    
    def manage_connections(self):
        """管理连接"""
        dialog = ConnectionDialog(self, manage_mode=True)
        dialog.exec_()
        self.load_connections()
    
    def update_transfer_status(self):
        """更新传输状态"""
        # 更新传输队列显示
        self.transfer_tree.clear()
        
        for task_id, task in self.transfer_manager.tasks.items():
            progress = f"{task.transferred}/{task.file_size}" if task.file_size > 0 else "未知"
            status = task.status.value
            size = self.format_size(task.file_size) if task.file_size > 0 else "未知"
            
            item = QTreeWidgetItem([
                os.path.basename(task.local_path),
                progress,
                status,
                size
            ])
            self.transfer_tree.addTopLevelItem(item)
    
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self, "关于",
            "FTP客户端\n\n"
            "功能:\n"
            "- FTP文件上传/下载\n"
            "- 断点续传\n"
            "- 图形化界面\n\n"
            "使用Socket实现FTP协议"
        )
    
    def format_size(self, size):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"
    
    def format_time(self, timestamp):
        """格式化时间"""
        from datetime import datetime
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 断开连接
        if self.ftp_client:
            try:
                self.ftp_client.quit()
            except:
                pass
        
        # 关闭数据库连接
        try:
            db = Database()
            db.close()
        except:
            pass
        
        event.accept()