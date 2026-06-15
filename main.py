# -*- coding: utf-8 -*-
"""
FTP客户端主程序入口
"""
import sys
import os

# 获取项目根目录（main.py所在目录的父目录）
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

# 添加父目录到sys.path，使相对导入正常工作
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# 同时添加当前目录，确保可以在ftp_client目录下运行
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from PyQt5.QtWidgets import QApplication
from ftp_client.gui.main_window import MainWindow


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setApplicationName("FTP客户端")
    app.setApplicationVersion("1.0.0")
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    # 运行应用
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()