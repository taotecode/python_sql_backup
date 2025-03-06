# Python MySQL Backup & Recovery Tool

一个基于 Python 3.10 和 Percona XtraBackup 的 MySQL 数据库备份和恢复工具，支持全量备份、增量备份、二进制日志备份和按时间点恢复。

A MySQL database backup and recovery tool based on Python 3.10 and Percona XtraBackup, supporting full backup, incremental backup, binary log backup, and point-in-time recovery.

## 特性 (Features)

* 支持 MySQL 5.7 及更高版本
* 通过 Percona XtraBackup 执行高效的热备份（不锁表）
* 提供多种备份方式：
  * 全量备份
  * 增量备份
  * 二进制日志备份
* 灵活的恢复选项：
  * 全量恢复
  * 增量恢复
  * 基于时间点的恢复
  * 指定表恢复
* 在恢复前自动备份现有数据
* 基于配置文件的设置管理
* 自动清理过期备份
* 完整的命令行界面，支持交互操作
* 可打包为独立的 Linux 可执行文件

## 系统要求 (Requirements)

* Python 3.10 或更高版本
* MySQL 5.7 或更高版本
* Percona XtraBackup 8.0 或更高版本
* 支持的操作系统：Windows, macOS, Linux

### 前置依赖 (Dependencies)

* mysql-connector-python
* click
* configparser
* tabulate
* colorama
* tqdm

要安装 Percona XtraBackup，请参考[官方安装文档](https://docs.percona.com/percona-xtrabackup/8.0/installation.html)。

## 安装 (Installation)

### 从源代码安装 (From Source)

```bash
# 克隆仓库
git clone https://github.com/yourusername/python_sql_backup.git
cd python_sql_backup

# 安装依赖
pip install -r requirements.txt

# 安装工具
pip install -e .
```

### 使用可执行文件 (Using Executable)

你可以使用 PyInstaller 构建一个独立的可执行文件：

```bash
# 安装依赖
pip install -r requirements.txt
pip install pyinstaller

# 使用交互式构建助手
python build_guide.py

# 或使用命令行直接构建
python build_executable.py --target-platform [windows|macos|linux] --target-arch [x86|x86_64|arm64]
```

构建完成后，可执行文件将位于 `dist/python-sql-backup/` 目录下。

## 配置 (Configuration)

该工具使用 INI 格式的配置文件。你可以通过以下位置提供配置文件：

1. 通过命令行参数 `--config` 指定
2. 当前工作目录下的 `config.ini`
3. 用户目录下的 `~/.python_sql_backup/config.ini`
4. 系统级别的 `/etc/python_sql_backup/config.ini`

配置文件示例 (`config.ini.example`):

```ini
[DATABASE]
host = localhost
port = 3306
user = root
password = your_password_here
socket = /var/lib/mysql/mysql.sock

[BACKUP]
backup_dir = /var/backups/mysql
retention_days = 365
backup_format = %Y%m%d_%H%M%S
threads = 4
compress = true

[BINLOG]
binlog_dir = /var/log/mysql
binlog_format = ROW
binlog_retention_days = 7
```

## 使用方法 (Usage)

### 基本命令 (Basic Commands)

```bash
# 显示帮助信息
python-sql-backup --help

# 使用指定配置文件
python-sql-backup --config /path/to/config.ini

# 查看子命令帮助
python-sql-backup backup --help
python-sql-backup restore --help
```

### 备份操作 (Backup Operations)

```bash
# 创建全量备份
python-sql-backup backup full

# 创建全量备份（仅指定表）
python-sql-backup backup full --tables "db1.table1,db2.table2"

# 创建增量备份
python-sql-backup backup incremental --base /path/to/full_backup

# 备份二进制日志
python-sql-backup backup binlog

# 列出所有可用备份
python-sql-backup backup list

# 清理旧备份（基于配置中的保留天数）
python-sql-backup backup clean

# 清理指定天数前的备份
python-sql-backup backup clean --days 30

# 模拟清理（不实际删除）
python-sql-backup backup clean --dry-run
```

### 恢复操作 (Restore Operations)

```bash
# 从全量备份恢复
python-sql-backup restore full /path/to/full_backup

# 从全量备份恢复（不备份现有数据）
python-sql-backup restore full /path/to/full_backup --no-backup-existing

# 从全量备份恢复（仅恢复指定表）
python-sql-backup restore full /path/to/full_backup --tables "db1.table1,db2.table2"

# 使用增量备份恢复
python-sql-backup restore incremental \
    --full /path/to/full_backup \
    --incremental /path/to/inc1 \
    --incremental /path/to/inc2

# 恢复到指定时间点
python-sql-backup restore point-in-time --timestamp "2023-01-01 12:00:00"
```

## 备份文件结构 (Backup Structure)

备份将以以下结构存储在配置的 `backup_dir` 目录中：

```
/var/backups/mysql/
├── full_20230101_120000/          # 全量备份
│   ├── <backup_files>
│   ├── metadata.txt               # 元数据文件
│   └── inc/                       # 增量备份目录
│       ├── inc_20230102_120000/   # 第1个增量备份
│       └── inc_20230103_120000/   # 第2个增量备份
├── full_20230110_120000/          # 另一个全量备份
└── binlog_20230101_120000/        # 二进制日志备份
```

## 本地测试指南
为了验证工具功能，您可以按照以下步骤进行本地测试：

### 环境准备
1. 安装MySQL服务器和Percona XtraBackup
2. 创建测试数据库和表
3. 在配置文件 `config.ini` 中设置正确的连接信息

### 测试脚本
项目包含了一系列测试脚本，可用于验证功能：

```bash
# 运行所有测试
cd python_sql_backup
python -m unittest discover -s tests

# 运行特定测试
python -m unittest tests.test_backup
python -m unittest tests.test_recovery
```

### 手动功能测试

1. 备份测试：

```bash
# 创建配置文件
cp config.ini.example config.ini
# 编辑配置文件设置

# 执行全量备份
python -m python_sql_backup backup full

# 查看备份列表
python -m python_sql_backup backup list
```

2. 恢复测试：

```bash
# 创建配置文件
cp config.ini.example config.ini
# 编辑配置文件设置

# 执行全量备份
python -m python_sql_backup backup full

# 查看备份列表
python -m python_sql_backup backup list
```

3. 增量备份测试：

```bash
# 基于全量备份创建增量备份
python -m python_sql_backup backup incremental --base /path/to/full_backup

# 恢复测试
python -m python_sql_backup restore incremental --full /path/to/full_backup --incremental /path/to/inc_backup
```

### 常见问题排查

1. 权限问题：确保MySQL用户有足够权限执行备份和恢复
2. XtraBackup错误：检查XtraBackup版本是否与MySQL版本兼容
3. 备份路径：确保备份目录有足够的磁盘空间和写入权限

## 构建独立可执行文件 (Building Standalone Executable)

```bash
# 安装 PyInstaller
pip install pyinstaller

# 构建可执行文件
pyinstaller python_sql_backup.spec
```

构建完成后，可执行文件将位于 `dist/python-sql-backup/` 目录下。

## 最佳实践 (Best Practices)

### 备份策略 (Backup Strategy)

1. 定期执行全量备份（例如每周一次）
2. 在全量备份之间执行增量备份（例如每日）
3. 定期测试恢复过程，确保备份有效
4. 将备份存储在与源数据库不同的物理机器上
5. 监控备份过程并设置告警机制
6. 根据业务需求设置合适的保留期

### 安全考虑 (Security Considerations)

1. 在配置文件中使用安全的权限设置（如 `chmod 600 config.ini`）
2. 使用具有受限权限的 MySQL 用户进行备份
3. 确保备份目录具有适当的权限
4. 考虑对备份进行加密

## 常见问题 (Troubleshooting)

### MySQL 连接问题 (MySQL Connection Issues)

确保在配置文件中指定了正确的 MySQL 连接参数，包括主机、端口、用户名和密码。

### 权限问题 (Permission Issues)

备份和恢复操作通常需要以 root 或具有适当权限的用户运行。确保用户有权访问 MySQL 数据目录。

### XtraBackup 不可用 (XtraBackup Not Available)

确保已安装 Percona XtraBackup 并且可以在系统 PATH 中找到。

## 项目结构 (Project Structure)

```
python_sql_backup/
├── python_sql_backup/            # 主要包
│   ├── __init__.py
│   ├── __main__.py               # 主入口点
│   ├── backup/                   # 备份模块
│   │   ├── __init__.py
│   │   └── backup_manager.py
│   ├── cli/                      # 命令行接口
│   │   ├── __init__.py
│   │   └── commands.py
│   ├── config/                   # 配置管理
│   │   ├── __init__.py
│   │   └── config_manager.py
│   ├── recovery/                 # 恢复模块
│   │   ├── __init__.py
│   │   └── recovery_manager.py
│   └── utils/                    # 实用工具
│       ├── __init__.py
│       └── common.py
├── requirements.txt              # 依赖列表
├── setup.py                      # 安装脚本
├── python_sql_backup.spec        # PyInstaller 规范文件
├── config.ini.example            # 示例配置文件
└── README.md                     # 文档
```

## 贡献 (Contributing)

欢迎贡献！请随时提交问题报告或功能请求。

## 许可证 (License)

本项目采用 MIT 许可证。详情请参阅 LICENSE 文件。
