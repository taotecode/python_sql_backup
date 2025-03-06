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
  * 基于时间范围的恢复（支持指定起始和结束时间）
  * 单独的二进制日志恢复
  * 指定表恢复（需指定数据库）
* 在恢复前自动备份现有数据
* 基于配置文件的设置管理
* 自动清理过期备份
* 完整的命令行界面，支持交互操作
* 交互式助手，引导用户完成备份和恢复操作
* 支持按年/月/日组织备份目录结构
* 支持将备份压缩为tar.gz格式
* 支持Docker环境中的MySQL操作
* 可打包为独立的可执行文件，支持多种CPU架构

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
# MySQL数据库连接设置
host = localhost
port = 3306
user = root
password = your_password_here
socket = /var/lib/mysql/mysql.sock

[BACKUP]
# 备份存储目录
backup_dir = /var/backups/mysql
# 备份保留天数
retention_days = 365
# 备份目录名称的时间戳格式
backup_format = %Y%m%d_%H%M%S
# 备份/恢复操作的并行线程数
threads = 4
# 是否使用压缩
compress = true
# 是否使用年/月/日目录结构
use_dated_dirs = true
# 是否在备份后将备份文件压缩为tar.gz
archive_after_backup = true
# 是否在创建新备份前自动清理过期备份
auto_clean = true

[BINLOG]
# 二进制日志目录
binlog_dir = /var/log/mysql
# 二进制日志格式
binlog_format = ROW
# 二进制日志保留天数
binlog_retention_days = 7

[DOCKER]
# Docker设置（仅在Docker环境中运行MySQL时需要）
# MySQL容器ID或名称
container_id = 
# 是否使用Docker命令操作MySQL
use_docker = false
```

## 使用方法 (Usage)

### 交互式助手 (Interactive Assistant)

最简单的使用方式是启动交互式助手，它将引导您完成备份和恢复操作：

```bash
# 启动交互式助手
python-sql-backup

# 或者使用交互式命令
python-sql-backup interactive
```

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
python-sql-backup backup full --tables "db1.table1,db1.table2"

# 创建全量备份（不自动清理旧备份）
python-sql-backup backup full --no-clean

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
python-sql-backup restore full /path/to/full_backup --tables "db1.table1,db1.table2"

# 使用增量备份恢复
python-sql-backup restore incremental \
    --full /path/to/full_backup \
    --incremental /path/to/inc1 \
    --incremental /path/to/inc2

# 恢复到指定时间点
python-sql-backup restore point-in-time --start-time "2023-01-01 12:00:00"

# 恢复指定时间范围的数据
python-sql-backup restore point-in-time \
    --start-time "2023-01-01 12:00:00" \
    --end-time "2023-01-02 01:00:00"

# 单独应用二进制日志
python-sql-backup restore binlog /path/to/binlog_backup \
    --start-time "2023-01-01 12:00:00" \
    --end-time "2023-01-01 13:00:00"
```

## 备份文件结构 (Backup Structure)

当使用默认的年/月/日目录结构时，备份将以以下结构存储：

```
/var/backups/mysql/
├── 2023/                           # 年份目录
│   ├── 01/                         # 月份目录
│   │   ├── 01/                     # 日期目录
│   │   │   ├── full_20230101_120000/          # 全量备份
│   │   │   │   ├── <backup_files>
│   │   │   │   ├── metadata.txt               # 元数据文件
│   │   │   │   └── inc/                       # 增量备份目录
│   │   │   │       ├── inc_20230101_130000/   # 第1个增量备份
│   │   │   │       └── inc_20230101_140000/   # 第2个增量备份
│   │   │   └── binlog_20230101_120000/        # 二进制日志备份
│   │   └── 02/                     # 另一个日期目录
│   │       └── full_20230102_120000.tar.gz    # 压缩的全量备份
│   └── 02/                         # 另一个月份目录
└── 2022/                           # 另一个年份目录
```

当禁用年/月/日目录结构时，备份将直接存储在备份根目录中：

```
/var/backups/mysql/
├── full_20230101_120000/           # 全量备份
│   ├── <backup_files>
│   ├── metadata.txt                # 元数据文件
│   └── inc/                        # 增量备份目录
│       ├── inc_20230102_120000/    # 第1个增量备份
│       └── inc_20230103_120000/    # 第2个增量备份
├── full_20230110_120000.tar.gz     # 压缩的全量备份
└── binlog_20230101_120000/         # 二进制日志备份
```

## 定时备份 (Scheduled Backups)

您可以使用cron或其他调度工具设置定时备份：

### Linux/macOS (cron)

```bash
# 编辑crontab
crontab -e

# 添加以下行以每天凌晨2点执行全量备份
0 2 * * * /path/to/python-sql-backup backup full

# 每6小时执行一次增量备份（基于最新的全量备份）
0 */6 * * * /path/to/python-sql-backup backup incremental --base $(/path/to/python-sql-backup backup list | grep "全量备份" | head -n 1 | awk '{print $3}')

# 每小时备份一次二进制日志
0 * * * * /path/to/python-sql-backup backup binlog

# 每周日凌晨3点清理过期备份
0 3 * * 0 /path/to/python-sql-backup backup clean
```

### Windows (Task Scheduler)

在Windows上，您可以使用Task Scheduler创建类似的定时任务。

## Docker环境支持 (Docker Support)

如果您在Docker容器中运行MySQL，可以通过以下方式配置：

1. 在配置文件中设置Docker相关选项：
```ini
[DOCKER]
container_id = your_mysql_container_id_or_name
use_docker = true
```

2. 或者通过环境变量设置：
```bash
export MYSQL_CONTAINER_ID=your_mysql_container_id_or_name
```

## 本地测试指南 (Testing Guide)

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
# 创建测试数据库
mysql -u root -p -e "CREATE DATABASE test_recovery;"
mysql -u root -p -e "USE test_recovery; CREATE TABLE test (id INT, data VARCHAR(100));"
mysql -u root -p -e "USE test_recovery; INSERT INTO test VALUES (1, 'test data');"

# 执行全量备份
python -m python_sql_backup backup full

# 查看备份列表
python -m python_sql_backup backup list

# 修改数据
mysql -u root -p -e "USE test_recovery; UPDATE test SET data = 'modified data' WHERE id = 1;"

# 恢复备份
python -m python_sql_backup restore full /path/to/backup

# 验证数据
mysql -u root -p -e "USE test_recovery; SELECT * FROM test;"
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



## 贡献 (Contributing)

欢迎贡献代码、报告问题或提出改进建议。请遵循以下步骤：

1. Fork 仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 许可证 (License)

本项目采用 MIT 许可证 - 详情请参阅 [LICENSE](LICENSE) 文件。

## 更新日志 (Changelog)

有关版本更新的详细信息，请参阅 [CHANGELOG.md](CHANGELOG.md) 文件。
