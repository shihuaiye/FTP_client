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
pip install PyQt5 PyMySQL pyftpdlib
```

## 数据库配置

1. 确保MySQL服务已启动
2. 修改 `config.py` 中的数据库配置：

```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '你的MySQL密码',  # 改这里
    'database': 'ftp_client',
    'charset': 'utf8mb4'
}
```

3. 首次运行会自动创建数据库和表

## 使用本地FTP服务器测试

### 1. 安装 pyftpdlib

```powershell
pip install pyftpdlib
```

### 2. 创建测试目录

测试目录 `ftp_test` 会在首次启动服务器时自动创建。

### 3. 启动FTP服务器

打开一个**新的PowerShell窗口**，运行：

```powershell
cd E:\network\ftp_client
python ftp_server.py
```

服务器会显示：
```
==================================================
本地FTP测试服务器
==================================================

FTP根目录: E:\network\ftp_client\ftp_test

服务器配置:
  地址: 127.0.0.1:21
  用户名: test
  密码: 123456
  匿名用户: anonymous (只读)

按 Ctrl+C 停止服务器
==================================================
```

### 4. 运行FTP客户端

在**另一个PowerShell窗口**运行：

```powershell
cd E:\network\ftp_client
python main.py
```

### 5. 连接本地服务器

在连接对话框中输入：

- **主机**：`localhost` 或 `127.0.0.1`
- **端口**：`21`
- **用户名**：`test`
- **密码**：`123456`



### 6. 测试功能

- **下载**：右键远程文件，选择下载
- **上传**：选择本地文件，右键上传
- **断点续传**：暂停后恢复

### 注意事项

- pyftpdlib 默认匿名用户只允许下载
- 使用 `test` 用户（密码 `123456`）可完整测试上传、下载、删除功能

## 项目结构

```
ftp_client/
├── config.py           # 配置文件
├── main.py            # 主程序入口
├── ftp_server.py      # 本地FTP测试服务器
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

