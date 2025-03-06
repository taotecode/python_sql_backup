"""
Recovery manager module for MySQL recovery operations using XtraBackup.
"""
import os
import time
import shutil
import logging
import subprocess
import tarfile
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Union

from python_sql_backup.config.config_manager import ConfigManager
from python_sql_backup.utils.common import ensure_dir, get_mysql_connection


class RecoveryManager:
    """
    Class to handle MySQL recovery operations using XtraBackup.
    """
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize the recovery manager.
        
        Args:
            config_manager: Instance of ConfigManager.
        """
        self.config = config_manager
        self.backup_dir = self.config.get('BACKUP', 'backup_dir')
        self.threads = int(self.config.get('BACKUP', 'threads', fallback='4'))
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(self.backup_dir, 'recovery.log')),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('RecoveryManager')
    
    def _prepare_backup(self, backup_path: str, apply_log_only: bool = False) -> None:
        """
        Prepare a backup for restoration.
        
        Args:
            backup_path: Path to the backup.
            apply_log_only: Whether to use --apply-log-only (for incremental prepare).
        """
        # 如果是压缩文件，先解压
        if backup_path.endswith('.tar.gz'):
            backup_path = self._uncompress_backup(backup_path)
        
        cmd = ['xtrabackup', '--prepare', f'--target-dir={backup_path}']
        
        if apply_log_only:
            cmd.append('--apply-log-only')
        
        cmd.append(f'--parallel={self.threads}')
        
        self.logger.info(f"Preparing backup at {backup_path}")
        self.logger.debug(f"Executing command: {' '.join(cmd)}")
        
        try:
            process = subprocess.run(cmd, check=True, capture_output=True, text=True)
            self.logger.debug(f"Command output: {process.stdout}")
            self.logger.info(f"Backup preparation completed successfully for {backup_path}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Backup preparation failed: {e}")
            self.logger.error(f"Error output: {e.stderr}")
            raise RuntimeError(f"Backup preparation failed: {e}")
    
    def _prepare_incremental_backup(self, full_backup_path: str, incremental_paths: List[str]) -> None:
        """
        Prepare a full backup with incremental backups.
        
        Args:
            full_backup_path: Path to the full backup.
            incremental_paths: List of incremental backup paths, in chronological order.
        """
        # 如果是压缩文件，先解压
        if full_backup_path.endswith('.tar.gz'):
            full_backup_path = self._uncompress_backup(full_backup_path)
        
        # First, prepare the full backup with --apply-log-only
        self._prepare_backup(full_backup_path, apply_log_only=True)
        
        # Then, apply each incremental backup, one by one
        for i, inc_path in enumerate(incremental_paths):
            self.logger.info(f"Applying incremental backup {i+1}/{len(incremental_paths)}: {inc_path}")
            
            # 如果是压缩文件，先解压
            if inc_path.endswith('.tar.gz'):
                inc_path = self._uncompress_backup(inc_path)
            
            # For all but the last incremental, use --apply-log-only
            apply_log_only = i < len(incremental_paths) - 1
            
            cmd = [
                'xtrabackup', '--prepare',
                f'--target-dir={full_backup_path}',
                f'--incremental-dir={inc_path}'
            ]
            
            if apply_log_only:
                cmd.append('--apply-log-only')
            
            cmd.append(f'--parallel={self.threads}')
            
            self.logger.debug(f"Executing command: {' '.join(cmd)}")
            
            try:
                process = subprocess.run(cmd, check=True, capture_output=True, text=True)
                self.logger.debug(f"Command output: {process.stdout}")
                self.logger.info(f"Incremental backup applied successfully: {inc_path}")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to apply incremental backup: {e}")
                self.logger.error(f"Error output: {e.stderr}")
                raise RuntimeError(f"Failed to apply incremental backup: {e}")
    
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
    
    def _backup_existing_data(self, target_dir: Optional[str] = None) -> str:
        """
        Back up existing MySQL data directory before restoration.
        
        Args:
            target_dir: Custom directory to store the backup. If None, a default is used.
            
        Returns:
            Path to the backup of the existing data.
        """
        db_config = self.config.get_section('DATABASE')
        
        # Try to determine the data directory
        connection = get_mysql_connection(self.config)
        with connection.cursor() as cursor:
            cursor.execute("SELECT @@datadir")
            datadir = cursor.fetchone()[0]
        
        # Create a backup directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if target_dir:
            backup_path = target_dir
        else:
            # 使用年/月/日结构
            now = datetime.now()
            year_dir = os.path.join(self.backup_dir, str(now.year))
            month_dir = os.path.join(year_dir, f"{now.month:02d}")
            day_dir = os.path.join(month_dir, f"{now.day:02d}")
            
            # 确保目录存在
            ensure_dir(day_dir)
            
            backup_path = os.path.join(day_dir, f'pre_restore_backup_{timestamp}')
        
        ensure_dir(backup_path)
        
        self.logger.info(f"Backing up existing MySQL data directory {datadir} to {backup_path}")
        
        # Shutdown MySQL
        self.logger.info("Stopping MySQL service")
        try:
            # 尝试使用systemctl停止MySQL
            try:
                subprocess.run(['systemctl', 'stop', 'mysql'], check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError:
                # 如果systemctl失败，尝试使用service命令
                try:
                    subprocess.run(['service', 'mysql', 'stop'], check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError:
                    # 如果service命令也失败，尝试使用Docker命令
                    try:
                        # 检查是否在Docker环境中
                        container_id = os.environ.get('MYSQL_CONTAINER_ID')
                        if container_id:
                            subprocess.run(['docker', 'stop', container_id], check=True, capture_output=True, text=True)
                        else:
                            raise RuntimeError("无法确定MySQL容器ID")
                    except Exception:
                        raise RuntimeError("无法停止MySQL服务")
        except Exception as e:
            self.logger.error(f"Failed to stop MySQL service: {e}")
            raise RuntimeError(f"Failed to stop MySQL service: {e}")
        
        try:
            # Copy the data directory
            for item in os.listdir(datadir):
                src = os.path.join(datadir, item)
                dst = os.path.join(backup_path, item)
                
                if os.path.isdir(src):
                    self.logger.debug(f"Copying directory {src} to {dst}")
                    shutil.copytree(src, dst)
                else:
                    self.logger.debug(f"Copying file {src} to {dst}")
                    shutil.copy2(src, dst)
            
            self.logger.info(f"Successfully backed up existing data to {backup_path}")
            return backup_path
            
        except Exception as e:
            self.logger.error(f"Failed to backup existing data: {e}")
            
            # Start MySQL again
            try:
                # 尝试使用systemctl启动MySQL
                try:
                    subprocess.run(['systemctl', 'start', 'mysql'], check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError:
                    # 如果systemctl失败，尝试使用service命令
                    try:
                        subprocess.run(['service', 'mysql', 'start'], check=True, capture_output=True, text=True)
                    except subprocess.CalledProcessError:
                        # 如果service命令也失败，尝试使用Docker命令
                        try:
                            # 检查是否在Docker环境中
                            container_id = os.environ.get('MYSQL_CONTAINER_ID')
                            if container_id:
                                subprocess.run(['docker', 'start', container_id], check=True, capture_output=True, text=True)
                            else:
                                raise RuntimeError("无法确定MySQL容器ID")
                        except Exception:
                            raise RuntimeError("无法启动MySQL服务")
            except Exception as e2:
                self.logger.error(f"Failed to restart MySQL service: {e2}")
            
            raise RuntimeError(f"Failed to backup existing data: {e}")
    
    def _restore_backup(
        self, 
        prepared_backup_path: str, 
        specific_tables: Optional[List[str]] = None
    ) -> None:
        """
        Restore a prepared backup.
        
        Args:
            prepared_backup_path: Path to the prepared backup.
            specific_tables: List of specific tables to restore.
        """
        db_config = self.config.get_section('DATABASE')
        
        # Try to determine the data directory
        connection = get_mysql_connection(self.config)
        with connection.cursor() as cursor:
            cursor.execute("SELECT @@datadir")
            datadir = cursor.fetchone()[0]
        
        # Build the command
        cmd = ['xtrabackup', '--copy-back', f'--target-dir={prepared_backup_path}']
        
        if specific_tables:
            for table in specific_tables:
                cmd.append(f'--tables={table}')
        
        self.logger.info(f"Restoring backup from {prepared_backup_path} to {datadir}")
        
        # Shutdown MySQL if it's running
        try:
            # 尝试使用systemctl检查MySQL状态
            try:
                subprocess.run(['systemctl', 'status', 'mysql'], check=True, capture_output=True, text=True)
                self.logger.info("MySQL is running. Stopping the service.")
                subprocess.run(['systemctl', 'stop', 'mysql'], check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError:
                # 如果systemctl失败，尝试使用service命令
                try:
                    subprocess.run(['service', 'mysql', 'status'], check=True, capture_output=True, text=True)
                    self.logger.info("MySQL is running. Stopping the service.")
                    subprocess.run(['service', 'mysql', 'stop'], check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError:
                    # 如果service命令也失败，尝试使用Docker命令
                    try:
                        # 检查是否在Docker环境中
                        container_id = os.environ.get('MYSQL_CONTAINER_ID')
                        if container_id:
                            # 检查容器状态
                            result = subprocess.run(['docker', 'inspect', '--format={{.State.Running}}', container_id], 
                                                  check=True, capture_output=True, text=True)
                            if result.stdout.strip() == 'true':
                                self.logger.info("MySQL container is running. Stopping the container.")
                                subprocess.run(['docker', 'stop', container_id], check=True, capture_output=True, text=True)
                        else:
                            self.logger.info("MySQL is not running. Proceeding with restoration.")
                    except Exception:
                        self.logger.info("MySQL is not running. Proceeding with restoration.")
        except Exception as e:
            self.logger.error(f"Error checking MySQL status: {e}")
            self.logger.info("Proceeding with restoration assuming MySQL is not running.")
        
        try:
            # Execute the restore command
            self.logger.debug(f"Executing command: {' '.join(cmd)}")
            process = subprocess.run(cmd, check=True, capture_output=True, text=True)
            self.logger.debug(f"Command output: {process.stdout}")
            
            # Fix permissions
            self.logger.info("Fixing permissions on the data directory")
            subprocess.run(['chown', '-R', 'mysql:mysql', datadir], check=True)
            
            # Start MySQL service
            self.logger.info("Starting MySQL service")
            # 尝试使用systemctl启动MySQL
            try:
                subprocess.run(['systemctl', 'start', 'mysql'], check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError:
                # 如果systemctl失败，尝试使用service命令
                try:
                    subprocess.run(['service', 'mysql', 'start'], check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError:
                    # 如果service命令也失败，尝试使用Docker命令
                    try:
                        # 检查是否在Docker环境中
                        container_id = os.environ.get('MYSQL_CONTAINER_ID')
                        if container_id:
                            subprocess.run(['docker', 'start', container_id], check=True, capture_output=True, text=True)
                        else:
                            raise RuntimeError("无法确定MySQL容器ID")
                    except Exception:
                        raise RuntimeError("无法启动MySQL服务")
            
            self.logger.info("Restoration completed successfully")
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Restoration failed: {e}")
            self.logger.error(f"Error output: {e.stderr}")
            raise RuntimeError(f"Restoration failed: {e}")
    
    def _apply_binlog(
        self, 
        binlog_paths: List[str], 
        start_time: Optional[datetime] = None, 
        end_time: Optional[datetime] = None,
        tables: Optional[List[str]] = None
    ) -> None:
        """
        Apply binary logs for point-in-time recovery.
        
        Args:
            binlog_paths: List of paths to binlog backup directories.
            start_time: Start time for recovery.
            end_time: End time for recovery.
            tables: List of specific tables to recover.
        """
        if not binlog_paths:
            self.logger.info("No binary logs to apply")
            return
        
        # Collect all binary log files
        binlog_files = []
        for binlog_dir in binlog_paths:
            # 如果是压缩文件，先解压
            if binlog_dir.endswith('.tar.gz'):
                binlog_dir = self._uncompress_backup(binlog_dir)
                
            for item in os.listdir(binlog_dir):
                if item.endswith('.000001') or item.endswith('.000002') or item.startswith('mysql-bin.'):  # Common binlog suffixes
                    binlog_files.append(os.path.join(binlog_dir, item))
        
        if not binlog_files:
            self.logger.info("No binary log files found in the provided directories")
            return
        
        # Sort by modification time
        binlog_files.sort(key=os.path.getmtime)
        
        # Create a command file for mysqlbinlog
        cmd_file = os.path.join(self.backup_dir, 'binlog_replay.sql')
        with open(cmd_file, 'w') as f:
            f.write("-- Binary log replay generated by python_sql_backup\n")
            
            # Add SET statements for specific tables if needed
            if tables:
                table_filter = '|'.join(tables)
                f.write(f"SET @binlog_filter = '{table_filter}';\n")
            
            f.write("SET sql_log_bin = 0;\n")  # Disable binary logging during replay
        
        try:
            # Build mysqlbinlog command
            cmd = ['mysqlbinlog']
            
            if start_time:
                cmd.append(f"--start-datetime='{start_time.strftime('%Y-%m-%d %H:%M:%S')}'")
            
            if end_time:
                cmd.append(f"--stop-datetime='{end_time.strftime('%Y-%m-%d %H:%M:%S')}'")
            
            if tables:
                # 提取数据库名称
                databases = set()
                for table in tables:
                    if '.' in table:
                        db_name = table.split('.')[0]
                        if db_name != '*':
                            databases.add(db_name)
                
                if databases:
                    cmd.append(f"--database={','.join(databases)}")
            
            # Add all binlog files
            cmd.extend(binlog_files)
            
            # Redirect output to the command file
            cmd.append(f">> {cmd_file}")
            
            # Execute mysqlbinlog
            self.logger.info(f"Generating SQL from binary logs with command: {' '.join(cmd)}")
            process = subprocess.run(' '.join(cmd), shell=True, check=True, capture_output=True, text=True)
            
            # Apply the generated SQL
            db_config = self.config.get_section('DATABASE')
            mysql_cmd = [
                'mysql',
                f"--host={db_config.get('host', 'localhost')}",
                f"--port={db_config.get('port', '3306')}",
                f"--user={db_config.get('user', 'root')}"
            ]
            
            if 'password' in db_config and db_config['password']:
                mysql_cmd.append(f"--password={db_config['password']}")
            
            mysql_cmd.append(f"< {cmd_file}")
            
            self.logger.info("Applying binary log changes to the database")
            process = subprocess.run(' '.join(mysql_cmd), shell=True, check=True, capture_output=True, text=True)
            
            self.logger.info("Binary log application completed successfully")
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Binary log application failed: {e}")
            self.logger.error(f"Error output: {e.stderr}")
            raise RuntimeError(f"Binary log application failed: {e}")
        finally:
            # Clean up the command file
            if os.path.exists(cmd_file):
                os.remove(cmd_file)
    
    def restore_full_backup(
        self, 
        backup_path: str, 
        backup_existing: bool = True,
        specific_tables: Optional[List[str]] = None
    ) -> None:
        """
        Restore a full backup.
        
        Args:
            backup_path: Path to the full backup.
            backup_existing: Whether to backup existing data before restoration.
            specific_tables: List of specific tables to restore.
        """
        if not os.path.exists(backup_path):
            self.logger.error(f"Backup path {backup_path} does not exist")
            raise FileNotFoundError(f"Backup path {backup_path} does not exist")
        
        self.logger.info(f"Starting restoration of full backup from {backup_path}")
        
        try:
            # Backup existing data if requested
            if backup_existing:
                self._backup_existing_data()
            
            # Prepare the backup
            self._prepare_backup(backup_path)
            
            # Restore the backup
            self._restore_backup(backup_path, specific_tables=specific_tables)
            
            self.logger.info("Full backup restoration completed successfully")
            
        except Exception as e:
            self.logger.error(f"Full backup restoration failed: {e}")
            raise
    
    def restore_incremental_backup(
        self, 
        full_backup_path: str, 
        incremental_paths: List[str],
        backup_existing: bool = True,
        specific_tables: Optional[List[str]] = None
    ) -> None:
        """
        Restore a full backup with incremental backups.
        
        Args:
            full_backup_path: Path to the full backup.
            incremental_paths: List of incremental backup paths, in chronological order.
            backup_existing: Whether to backup existing data before restoration.
            specific_tables: List of specific tables to restore.
        """
        if not os.path.exists(full_backup_path):
            self.logger.error(f"Full backup path {full_backup_path} does not exist")
            raise FileNotFoundError(f"Full backup path {full_backup_path} does not exist")
        
        for path in incremental_paths:
            if not os.path.exists(path):
                self.logger.error(f"Incremental backup path {path} does not exist")
                raise FileNotFoundError(f"Incremental backup path {path} does not exist")
        
        self.logger.info(f"Starting restoration of full backup with {len(incremental_paths)} incremental backups")
        
        try:
            # Backup existing data if requested
            if backup_existing:
                self._backup_existing_data()
            
            # Create a copy of the full backup to work with
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            tmp_restore_path = os.path.join(self.backup_dir, f'tmp_restore_{timestamp}')
            
            # 如果是压缩文件，先解压
            if full_backup_path.endswith('.tar.gz'):
                full_backup_path = self._uncompress_backup(full_backup_path)
            
            self.logger.info(f"Creating a copy of the full backup to {tmp_restore_path}")
            shutil.copytree(full_backup_path, tmp_restore_path)
            
            # Prepare the backup with incrementals
            self._prepare_incremental_backup(tmp_restore_path, incremental_paths)
            
            # Restore the prepared backup
            self._restore_backup(tmp_restore_path, specific_tables=specific_tables)
            
            # Clean up the temporary directory
            self.logger.info(f"Cleaning up temporary directory {tmp_restore_path}")
            shutil.rmtree(tmp_restore_path)
            
            self.logger.info("Incremental backup restoration completed successfully")
            
        except Exception as e:
            self.logger.error(f"Incremental backup restoration failed: {e}")
            raise
    
    def restore_to_point_in_time(
        self, 
        start_time: datetime,
        end_time: Optional[datetime] = None,
        backup_existing: bool = True,
        specific_tables: Optional[List[str]] = None
    ) -> None:
        """
        Restore database to a specific point in time.
        
        Args:
            start_time: Start timestamp for recovery.
            end_time: End timestamp for recovery, defaults to start_time if not provided.
            backup_existing: Whether to backup existing data before restoration.
            specific_tables: List of specific tables to restore.
        """
        from python_sql_backup.backup.backup_manager import BackupManager
        
        backup_manager = BackupManager(self.config)
        target_time = end_time or start_time
        
        # Find the appropriate backups for point-in-time recovery
        try:
            full_backup, incrementals, binlogs = backup_manager.find_backups_for_timestamp(start_time, target_time)
        except ValueError as e:
            self.logger.error(f"Could not find suitable backups: {e}")
            raise
        
        self.logger.info(f"Found {len(incrementals)} incremental backups and {len(binlogs)} binlog backups for point-in-time recovery from {start_time} to {target_time}")
        
        try:
            # Restore the full and incremental backups
            if incrementals:
                self.restore_incremental_backup(full_backup, incrementals, backup_existing, specific_tables)
            else:
                self.restore_full_backup(full_backup, backup_existing, specific_tables)
            
            # Apply binary logs up to the target time
            self._apply_binlog(binlogs, start_time=start_time, end_time=target_time, tables=specific_tables)
            
            self.logger.info(f"Point-in-time recovery from {start_time} to {target_time} completed successfully")
            
        except Exception as e:
            self.logger.error(f"Point-in-time recovery failed: {e}")
            raise
    
    def apply_binlog(
        self,
        binlog_paths: List[str],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tables: Optional[List[str]] = None
    ) -> None:
        """
        单独应用二进制日志，不进行XtraBackup恢复
        
        Args:
            binlog_paths: 二进制日志备份路径列表
            start_time: 开始时间
            end_time: 结束时间
            tables: 要恢复的表列表
        """
        self.logger.info(f"Starting binlog application from {len(binlog_paths)} binlog backups")
        
        if start_time and end_time and end_time <= start_time:
            self.logger.error("End time must be later than start time")
            raise ValueError("End time must be later than start time")
        
        try:
            # 应用二进制日志
            self._apply_binlog(binlog_paths, start_time=start_time, end_time=end_time, tables=tables)
            
            self.logger.info("Binlog application completed successfully")
            
        except Exception as e:
            self.logger.error(f"Binlog application failed: {e}")
            raise
