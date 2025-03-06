"""
Backup manager module for MySQL backup operations using XtraBackup.
"""
import os
import time
import shutil
import logging
import subprocess
import tarfile
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Union

from python_sql_backup.config.config_manager import ConfigManager
from python_sql_backup.utils.common import ensure_dir, get_mysql_connection


class BackupManager:
    """
    Class to handle MySQL backup operations using XtraBackup.
    """
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize the backup manager.
        
        Args:
            config_manager: Instance of ConfigManager.
        """
        self.config = config_manager
        self.backup_dir = self.config.get('BACKUP', 'backup_dir')
        self.retention_days = int(self.config.get('BACKUP', 'retention_days', fallback='365'))
        self.backup_format = self.config.get('BACKUP', 'backup_format', fallback='%Y%m%d_%H%M%S')
        self.threads = int(self.config.get('BACKUP', 'threads', fallback='4'))
        self.compress = self.config.get('BACKUP', 'compress', fallback='true').lower() == 'true'
        self.use_dated_dirs = self.config.get('BACKUP', 'use_dated_dirs', fallback='true').lower() == 'true'
        
        # Ensure backup directory exists
        ensure_dir(self.backup_dir)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(self.backup_dir, 'backup.log')),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('BackupManager')
    
    def _get_backup_path(self, backup_type: str) -> str:
        """
        Generate the backup path based on current time and backup type.
        
        Args:
            backup_type: Type of backup ('full', 'incremental', 'binlog').
            
        Returns:
            Path to store the backup.
        """
        now = datetime.now()
        timestamp = now.strftime(self.backup_format)
        
        if self.use_dated_dirs:
            # 使用年/月/日结构
            year_dir = os.path.join(self.backup_dir, str(now.year))
            month_dir = os.path.join(year_dir, f"{now.month:02d}")
            day_dir = os.path.join(month_dir, f"{now.day:02d}")
            
            # 确保目录存在
            ensure_dir(day_dir)
            
            # 返回路径: backup_dir/year/month/day/type_timestamp
            return os.path.join(day_dir, f"{backup_type}_{timestamp}")
        else:
            # 使用旧的目录结构
            return os.path.join(self.backup_dir, f"{backup_type}_{timestamp}")
    
    def _get_backup_command(
        self, 
        backup_type: str, 
        target_dir: str, 
        incremental_basedir: Optional[str] = None,
        tables: Optional[List[str]] = None
    ) -> List[str]:
        """
        Generate the XtraBackup command for backup.
        
        Args:
            backup_type: Type of backup ('full', 'incremental').
            target_dir: Directory to store the backup.
            incremental_basedir: Base directory for incremental backup.
            tables: List of tables to backup (for partial backup).
            
        Returns:
            Command list to execute.
        """
        db_config = self.config.get_section('DATABASE')
        
        # Base command
        cmd = ['xtrabackup', '--backup', '--target-dir=' + target_dir]
        
        # Add authentication
        cmd.extend([
            f'--host={db_config.get("host", "localhost")}',
            f'--port={db_config.get("port", "3306")}',
            f'--user={db_config.get("user", "root")}'
        ])
        
        if 'password' in db_config and db_config['password']:
            cmd.append(f'--password={db_config["password"]}')
        
        if 'socket' in db_config and db_config['socket']:
            cmd.append(f'--socket={db_config["socket"]}')
        
        # Add backup-specific options
        if backup_type == 'incremental' and incremental_basedir:
            cmd.append(f'--incremental-basedir={incremental_basedir}')
        
        # Add compression if enabled
        if self.compress:
            cmd.append('--compress')
        
        # Add parallel threads
        cmd.append(f'--parallel={self.threads}')
        
        # Add specific tables if provided
        if tables:
            for table in tables:
                cmd.append(f'--tables={table}')
        
        return cmd
    
    def _compress_backup(self, backup_path: str) -> str:
        """
        压缩备份目录为tar.gz格式
        
        Args:
            backup_path: 备份目录路径
            
        Returns:
            压缩文件路径
        """
        tar_path = f"{backup_path}.tar.gz"
        self.logger.info(f"压缩备份目录 {backup_path} 到 {tar_path}")
        
        try:
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(backup_path, arcname=os.path.basename(backup_path))
            
            # 删除原备份目录
            shutil.rmtree(backup_path)
            self.logger.info(f"备份压缩完成，已删除原目录 {backup_path}")
            
            return tar_path
        except Exception as e:
            self.logger.error(f"备份压缩失败: {e}")
            # 如果压缩失败，保留原目录
            if os.path.exists(tar_path):
                os.remove(tar_path)
            
            return backup_path
    
    def create_full_backup(self, tables: Optional[List[str]] = None) -> str:
        """
        Create a full backup of the MySQL database.
        
        Args:
            tables: Optional list of tables to backup. If None, all tables are backed up.
            
        Returns:
            Path to the created backup.
        """
        # 在备份前先执行清理操作
        self.clean_old_backups()
        
        backup_path = self._get_backup_path('full')
        
        # Ensure directory doesn't exist
        if os.path.exists(backup_path):
            self.logger.error(f"Backup directory {backup_path} already exists")
            raise FileExistsError(f"Backup directory {backup_path} already exists")
        
        ensure_dir(backup_path)
        
        try:
            self.logger.info(f"Starting full backup to {backup_path}")
            
            # Create the backup command
            cmd = self._get_backup_command('full', backup_path, tables=tables)
            
            # Run the backup command
            self.logger.debug(f"Executing command: {' '.join(cmd)}")
            process = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Log the output
            self.logger.debug(f"Command output: {process.stdout}")
            
            # Create a metadata file
            self._create_metadata_file(backup_path, 'full', tables=tables)
            
            # 在配置开启的情况下将备份压缩为tar.gz
            if self.config.get('BACKUP', 'archive_after_backup', fallback='false').lower() == 'true':
                backup_path = self._compress_backup(backup_path)
            
            self.logger.info(f"Full backup completed successfully at {backup_path}")
            return backup_path
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Full backup failed: {e}")
            self.logger.error(f"Error output: {e.stderr}")
            
            # Clean up the failed backup
            if os.path.exists(backup_path):
                shutil.rmtree(backup_path)
            
            raise RuntimeError(f"Full backup failed: {e}")
    
    def create_incremental_backup(
        self, 
        base_backup: str,
        tables: Optional[List[str]] = None
    ) -> str:
        """
        Create an incremental backup based on a previous backup.
        
        Args:
            base_backup: Path to the base backup.
            tables: Optional list of tables to backup. If None, all tables are backed up.
            
        Returns:
            Path to the created incremental backup.
        """
        # 在备份前先执行清理操作
        self.clean_old_backups()
        
        if not os.path.exists(base_backup):
            self.logger.error(f"Base backup {base_backup} does not exist")
            raise FileNotFoundError(f"Base backup {base_backup} does not exist")
        
        # 如果是压缩文件，需要先解压
        if base_backup.endswith('.tar.gz'):
            uncompressed_path = self._uncompress_backup(base_backup)
            base_backup = uncompressed_path
        
        timestamp = datetime.now().strftime(self.backup_format)
        
        # Determine if the base is a full or incremental backup
        is_full = os.path.basename(base_backup).startswith('full_')
        parent_dir = os.path.dirname(base_backup)
        
        if is_full:
            # If base is a full backup, create first incremental in a subdirectory
            backup_dir = os.path.join(base_backup, 'inc')
            ensure_dir(backup_dir)
            backup_path = os.path.join(backup_dir, f'inc_{timestamp}')
        else:
            # If base is an incremental backup, create the next incremental in the same directory
            backup_dir = os.path.dirname(base_backup)
            backup_path = os.path.join(backup_dir, f'inc_{timestamp}')
        
        # Ensure directory doesn't exist
        if os.path.exists(backup_path):
            self.logger.error(f"Backup directory {backup_path} already exists")
            raise FileExistsError(f"Backup directory {backup_path} already exists")
        
        ensure_dir(backup_path)
        
        try:
            self.logger.info(f"Starting incremental backup to {backup_path} based on {base_backup}")
            
            # Create the backup command
            cmd = self._get_backup_command('incremental', backup_path, incremental_basedir=base_backup, tables=tables)
            
            # Run the backup command
            self.logger.debug(f"Executing command: {' '.join(cmd)}")
            process = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Log the output
            self.logger.debug(f"Command output: {process.stdout}")
            
            # Create a metadata file
            self._create_metadata_file(backup_path, 'incremental', base_backup=base_backup, tables=tables)
            
            # 在配置开启的情况下将备份压缩为tar.gz
            if self.config.get('BACKUP', 'archive_after_backup', fallback='false').lower() == 'true':
                backup_path = self._compress_backup(backup_path)
            
            self.logger.info(f"Incremental backup completed successfully at {backup_path}")
            return backup_path
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Incremental backup failed: {e}")
            self.logger.error(f"Error output: {e.stderr}")
            
            # Clean up the failed backup
            if os.path.exists(backup_path):
                shutil.rmtree(backup_path)
            
            raise RuntimeError(f"Incremental backup failed: {e}")
    
    def _uncompress_backup(self, backup_path: str) -> str:
        """
        解压缩tar.gz格式的备份
        
        Args:
            backup_path: 压缩文件路径
            
        Returns:
            解压后的目录路径
        """
        if not backup_path.endswith('.tar.gz'):
            return backup_path
        
        extract_path = backup_path[:-7]  # 移除 .tar.gz
        self.logger.info(f"解压备份 {backup_path} 到 {extract_path}")
        
        try:
            with tarfile.open(backup_path, "r:gz") as tar:
                tar.extractall(path=os.path.dirname(extract_path))
            
            self.logger.info(f"备份解压完成: {extract_path}")
            return extract_path
        except Exception as e:
            self.logger.error(f"备份解压失败: {e}")
            raise RuntimeError(f"备份解压失败: {e}")
    
    def backup_binlog(self) -> str:
        """
        Backup the binary logs.
        
        Returns:
            Path to the backed up binary logs.
        """
        # 在备份前先执行清理操作
        self.clean_old_backups()
        
        binlog_config = self.config.get_section('BINLOG')
        binlog_dir = binlog_config.get('binlog_dir', '/var/log/mysql')
        
        if not os.path.exists(binlog_dir):
            self.logger.error(f"Binlog directory {binlog_dir} does not exist")
            raise FileNotFoundError(f"Binlog directory {binlog_dir} does not exist")
        
        backup_path = self._get_backup_path('binlog')
        
        # Ensure directory doesn't exist
        if os.path.exists(backup_path):
            self.logger.error(f"Backup directory {backup_path} already exists")
            raise FileExistsError(f"Backup directory {backup_path} already exists")
        
        ensure_dir(backup_path)
        
        try:
            self.logger.info(f"Starting binlog backup to {backup_path}")
            
            # Get the list of binary logs
            connection = get_mysql_connection(self.config)
            with connection.cursor() as cursor:
                cursor.execute("SHOW BINARY LOGS")
                binlogs = cursor.fetchall()
            
            # Copy each binary log file
            for binlog in binlogs:
                binlog_name = binlog[0]
                binlog_path = os.path.join(binlog_dir, binlog_name)
                
                if os.path.exists(binlog_path):
                    self.logger.debug(f"Copying binary log {binlog_path} to {backup_path}")
                    shutil.copy2(binlog_path, backup_path)
                else:
                    self.logger.warning(f"Binary log {binlog_path} does not exist, skipping")
            
            # Create a metadata file
            self._create_metadata_file(backup_path, 'binlog')
            
            # 在配置开启的情况下将备份压缩为tar.gz
            if self.config.get('BACKUP', 'archive_after_backup', fallback='false').lower() == 'true':
                backup_path = self._compress_backup(backup_path)
            
            self.logger.info(f"Binlog backup completed successfully at {backup_path}")
            return backup_path
            
        except Exception as e:
            self.logger.error(f"Binlog backup failed: {e}")
            
            # Clean up the failed backup
            if os.path.exists(backup_path):
                shutil.rmtree(backup_path)
            
            raise RuntimeError(f"Binlog backup failed: {e}")
    
    def _create_metadata_file(
        self, 
        backup_path: str, 
        backup_type: str,
        base_backup: Optional[str] = None,
        tables: Optional[List[str]] = None
    ) -> None:
        """
        Create a metadata file for the backup.
        
        Args:
            backup_path: Path to the backup directory.
            backup_type: Type of backup ('full', 'incremental', 'binlog').
            base_backup: Base backup for incremental backups.
            tables: List of tables included in the backup.
        """
        metadata = {
            'backup_type': backup_type,
            'timestamp': datetime.now().isoformat(),
            'base_backup': base_backup,
            'tables': tables,
            'mysql_version': self._get_mysql_version(),
            'xtrabackup_version': self._get_xtrabackup_version()
        }
        
        metadata_path = os.path.join(backup_path, 'metadata.txt')
        with open(metadata_path, 'w') as f:
            for key, value in metadata.items():
                if value is not None:
                    f.write(f"{key}: {value}\n")
    
    def _get_mysql_version(self) -> str:
        """
        Get the MySQL server version.
        
        Returns:
            MySQL server version.
        """
        try:
            connection = get_mysql_connection(self.config)
            with connection.cursor() as cursor:
                cursor.execute("SELECT VERSION()")
                version = cursor.fetchone()[0]
            return version
        except Exception as e:
            self.logger.warning(f"Could not get MySQL version: {e}")
            return "unknown"
    
    def _get_xtrabackup_version(self) -> str:
        """
        Get the XtraBackup version.
        
        Returns:
            XtraBackup version.
        """
        try:
            process = subprocess.run(['xtrabackup', '--version'], check=True, capture_output=True, text=True)
            return process.stdout.strip()
        except Exception as e:
            self.logger.warning(f"Could not get XtraBackup version: {e}")
            return "unknown"
    
    def find_latest_full_backup(self) -> Optional[str]:
        """
        Find the latest full backup.
        
        Returns:
            Path to the latest full backup, or None if no full backup exists.
        """
        full_backups = self._find_backups('full')
        
        if not full_backups:
            return None
        
        # Sort by creation time (newest first)
        full_backups.sort(key=lambda x: os.path.getctime(x[1]), reverse=True)
        
        # 返回路径
        return full_backups[0][1]
    
    def _find_backups(self, backup_type: str = None) -> List[Tuple[str, str]]:
        """
        在所有备份目录中查找指定类型的备份
        
        Args:
            backup_type: 备份类型 ('full', 'incremental', 'binlog')，如果为None则查找所有类型
            
        Returns:
            备份列表，每项为 (备份名称, 完整路径)
        """
        backups = []
        
        # 递归遍历备份目录
        for root, dirs, files in os.walk(self.backup_dir):
            # 检查tar.gz文件
            for file in files:
                if file.endswith('.tar.gz'):
                    # 提取备份类型
                    if backup_type is not None and not file.startswith(f"{backup_type}_"):
                        continue
                    backups.append((file, os.path.join(root, file)))
            
            # 检查目录
            for dir_name in dirs:
                if backup_type is not None and not dir_name.startswith(f"{backup_type}_"):
                    continue
                
                # 找到匹配的备份目录
                if dir_name.startswith(('full_', 'incremental_', 'binlog_')):
                    full_path = os.path.join(root, dir_name)
                    backups.append((dir_name, full_path))
        
        return backups
    
    def find_backups_for_timestamp(self, start_time: datetime, end_time: Optional[datetime] = None) -> Tuple[str, List[str], List[str]]:
        """
        Find the appropriate backups for point-in-time recovery.
        
        Args:
            start_time: Start timestamp for recovery.
            end_time: End timestamp for recovery, defaults to start_time if not provided.
            
        Returns:
            Tuple of (full backup path, list of incremental backup paths, list of relevant binlog paths).
            Paths are ordered chronologically.
        """
        target_time = end_time or start_time
        
        # 查找所有备份
        full_backups = self._find_backups('full')
        binlog_backups = self._find_backups('binlog')
        
        # 按创建时间排序
        full_backups.sort(key=lambda x: os.path.getctime(x[1]))
        binlog_backups.sort(key=lambda x: os.path.getctime(x[1]))
        
        # 找到最适合的全量备份
        suitable_full = None
        for name, path in reversed(full_backups):
            backup_time = datetime.fromtimestamp(os.path.getctime(path))
            if backup_time <= target_time:
                suitable_full = path
                # 如果是压缩文件，解压它
                if path.endswith('.tar.gz'):
                    suitable_full = self._uncompress_backup(path)
                break
        
        if not suitable_full:
            raise ValueError(f"No full backup found before the target time {target_time}")
        
        # 找到增量备份
        suitable_incrementals = []
        
        # 检查全量备份目录中的增量备份
        inc_dir = os.path.join(suitable_full, 'inc')
        if os.path.exists(inc_dir) and os.path.isdir(inc_dir):
            for item in os.listdir(inc_dir):
                if item.startswith('inc_'):
                    inc_path = os.path.join(inc_dir, item)
                    if os.path.isdir(inc_path):
                        backup_time = datetime.fromtimestamp(os.path.getctime(inc_path))
                        if backup_time <= target_time:
                            suitable_incrementals.append(inc_path)
        
        # 按创建时间排序
        suitable_incrementals.sort(key=os.path.getctime)
        
        # 找到相关的二进制日志备份
        suitable_binlogs = []
        full_backup_time = datetime.fromtimestamp(os.path.getctime(suitable_full))
        
        # 二进制日志备份需要在start_time和end_time范围内
        for name, path in binlog_backups:
            backup_time = datetime.fromtimestamp(os.path.getctime(path))
            # 如果备份时间在start_time和end_time之间，就包含它
            if start_time <= backup_time <= target_time:
                # 如果是压缩文件，解压它
                if path.endswith('.tar.gz'):
                    path = self._uncompress_backup(path)
                suitable_binlogs.append(path)
            # 如果备份时间在全量备份之前但在start_time之后，也包含它
            elif full_backup_time <= backup_time <= start_time:
                # 如果是压缩文件，解压它
                if path.endswith('.tar.gz'):
                    path = self._uncompress_backup(path)
                suitable_binlogs.append(path)
        
        return suitable_full, suitable_incrementals, suitable_binlogs
    
    def clean_old_backups(self, dry_run: bool = False) -> None:
        """
        清理过期的备份

        Args:
            dry_run: 如果为True，只显示将要删除的备份但不实际删除
        """
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)
        deleted_count = 0
        
        self.logger.info(f"Cleaning up backups older than {cutoff_time}")
        
        if dry_run:
            self.logger.info("DRY RUN: Backups will not be actually deleted")
        
        # 查找所有备份
        all_backups = []
        all_backups.extend(self._find_backups('full'))
        all_backups.extend(self._find_backups('binlog'))
        
        # 按创建时间排序（最旧的在前）
        all_backups.sort(key=lambda x: os.path.getctime(x[1]))
        
        for name, path in all_backups:
            backup_time = datetime.fromtimestamp(os.path.getctime(path))
            
            if backup_time < cutoff_time:
                self.logger.info(f"{'Would delete' if dry_run else 'Deleting'} old backup: {path}")
                if not dry_run:
                    try:
                        if os.path.isdir(path):
                            shutil.rmtree(path)
                        else:
                            os.remove(path)
                        deleted_count += 1
                    except Exception as e:
                        self.logger.error(f"Failed to delete backup {path}: {e}")
        
        self.logger.info(f"Cleanup completed. {'Would have deleted' if dry_run else 'Deleted'} {deleted_count} old backups.")
