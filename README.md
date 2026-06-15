# FTP客户端

基于Python + PyQt5实现的FTP客户端，支持断点续传功能。

## 功能特性

- 图形化界面操作
- FTP文件上传/下载
- 断点续传功能
- 连接配置管理
- 文件浏览和管理

## 技术栈

- **GUI框架**: PyQt5
- **数据库**: MySQL (PyMySQL)
- **网络**: Socket编程实现FTP协议

## 安装依赖

```bash
pip install -r requirements.txt
```

## 数据库配置

1. 确保MySQL服务已启动
2. 修改 `ftp_client/config.py` 中的数据库配置
3. 首次运行会自动创建数据库和表

## 运行程序

```bash
cd ftp_client
python main.py
```

## 项目结构

```
ftp_client/
├── config.py           # 配置文件
├── main.py            # 主程序入口
├── __init__.py        # 包初始化
├── core/              # 核心模块
│   ├── ftp_client.py  # FTP协议实现
│   └── transfer_manager.py  # 传输管理
├── models/            # 数据模型
│   ├── database.py    # 数据库连接
│   ├── transfer_record.py  # 传输记录
│   └── ftp_connection.py   # 连接配置
└── gui/               # 图形界面
    ├── main_window.py  # 主窗口
    ├── connection_dialog.py  # 连接对话框
    └── transfer_dialog.py    # 传输进度对话框
```

## 使用说明

1. 点击"连接"按钮或从下拉框选择已保存的连接
2. 输入FTP服务器地址、端口、用户名和密码
3. 连接成功后，左侧显示本地文件，右侧显示远程文件
4. 双击目录可进入，双击".."可返回上级
5. 右键文件可选择上传/下载/删除/重命名
6. 传输过程中可暂停，支持断点续传