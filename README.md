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
pip install PyQt5 PyMySQL
```

## 数据库配置

1. 确保MySQL服务已启动
2. 修改 `ftp_client/config.py` 中的数据库配置
```
   DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '你的MySQL密码',  # 改这里
    'database': 'ftp_client',
    'charset': 'utf8mb4'
}
```
4. 首次运行会自动创建数据库和表

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
7. 目前测试连接的公共FTP平台为
``` 
服务器地址	ftp.dlptest.com 
端口	21 (FTP默认端口) 
用户名	dlpuser 
密码	rNrKYTX9g7z3RgJRmxWuGHbeu
```
重要提醒：这个服务器的密码会定期更改。上面提供的密码是搜索资料中的最新版本，如果连接失败，建议直接访问它的官网 https://dlptest.com/ftp-test/ 获取最新密码，另外如果连接不上可以多试几次，退出重新启动程序之类的，这个问题貌似是因为公共平台的问题，对流量有限制，或者尝试不使用校园网
