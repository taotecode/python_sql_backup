"""
Backup manager module for MySQL backup operations using XtraBackup.
"""
import os
import time
import shutil
import logging
import subprocess
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
    
    def create_full_backup(self, tables: Optional[List[str]] = None) -> str:
        """
        Create a full backup of the MySQL database.
        
        Args:
            tables: Optional list of tables to backup. If None, all tables are backed up.
            
        Returns:
            Path to the created backup.
        """
        timestamp = datetime.now().strftime(self.backup_format)
        backup_path = os.path.join(self.backup_dir, f'full_{timestamp}')
        
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
        if not os.path.exists(base_backup):
            self.logger.error(f"Base backup {base_backup} does not exist")
            raise FileNotFoundError(f"Base backup {base_backup} does not exist")
        
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
            
            self.logger.info(f"Incremental backup completed successfully at {backup_path}")
            return backup_path
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Incremental backup failed: {e}")
            self.logger.error(f"Error output: {e.stderr}")
            
            # Clean up the failed backup
            if os.path.exists(backup_path):
                shutil.rmtree(backup_path)
            
            raise RuntimeError(f"Incremental backup failed: {e}")
    
    def backup_binlog(self) -> str:
        """
        Backup the binary logs.
        
        Returns:
            Path to the backed up binary logs.
        """
        binlog_config = self.config.get_section('BINLOG')
        binlog_dir = binlog_config.get('binlog_dir', '/var/log/mysql')
        
        if not os.path.exists(binlog_dir):
            self.logger.error(f"Binlog directory {binlog_dir} does not exist")
            raise FileNotFoundError(f"Binlog directory {binlog_dir} does not exist")
        
        timestamp = datetime.now().strftime(self.backup_format)
        backup_path = os.path.join(self.backup_dir, f'binlog_{timestamp}')
        
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
        full_backups = []
        
        # Find all full backup directories
        for item in os.listdir(self.backup_dir):
            if item.startswith('full_'):
                full_path = os.path.join(self.backup_dir, item)
                if os.path.isdir(full_path):
                    full_backups.append(full_path)
        
        if not full_backups:
            return None
        
        # Sort by creation time (newest first)
        return sorted(full_backups, key=os.path.getctime, reverse=True)[0]
    
    def find_backups_for_timestamp(self, target_time: datetime) -> Tuple[str, List[str], List[str]]:
        """
        Find the appropriate backups for point-in-time recovery.
        
        Args:
            target_time: Target timestamp for recovery.
            
        Returns:
            Tuple of (full backup path, list of incremental backup paths, list of relevant binlog paths).
            Paths are ordered chronologically.
        """
        # Find all full and incremental backups
        full_backups = []
        incremental_backups = []
        binlog_backups = []
        
        for item in os.listdir(self.backup_dir):
            full_path = os.path.join(self.backup_dir, item)
            if not os.path.isdir(full_path):
                continue
                
            if item.startswith('full_'):
                full_backups.append(full_path)
            elif item.startswith('binlog_'):
                binlog_backups.append(full_path)
        
        # Sort by creation time
        full_backups.sort(key=os.path.getctime)
        binlog_backups.sort(key=os.path.getctime)
        
        # Find the most recent full backup before the target time
        suitable_full = None
        for backup in reversed(full_backups):
            backup_time = datetime.fromtimestamp(os.path.getctime(backup))
            if backup_time <= target_time:
                suitable_full = backup
                break
        
        if not suitable_full:
            raise ValueError(f"No full backup found before the target time {target_time}")
        
        # Find all incremental backups after the full backup and before the target time
        suitable_incrementals = []
        
        # Look for incremental backups within the full backup directory
        inc_dir = os.path.join(suitable_full, 'inc')
        if os.path.exists(inc_dir) and os.path.isdir(inc_dir):
            for item in os.listdir(inc_dir):
                if item.startswith('inc_'):
                    inc_path = os.path.join(inc_dir, item)
                    if os.path.isdir(inc_path):
                        backup_time = datetime.fromtimestamp(os.path.getctime(inc_path))
                        if backup_time <= target_time:
                            suitable_incrementals.append(inc_path)
        
        # Sort incrementals by creation time
        suitable_incrementals.sort(key=os.path.getctime)
        
        # Find relevant binlog backups
        suitable_binlogs = []
        full_backup_time = datetime.fromtimestamp(os.path.getctime(suitable_full))
        
        for backup in binlog_backups:
            backup_time = datetime.fromtimestamp(os.path.getctime(backup))
            if full_backup_time <= backup_time <= target_time:
                suitable_binlogs.append(backup)
        
        return suitable_full, suitable_incrementals, suitable_binlogs
    
    def clean_old_backups(self) -> None:
        """
        Clean up old backups based on retention policy.
        """
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)
        deleted_count = 0
        
        self.logger.info(f"Cleaning up backups older than {cutoff_time}")
        
        for item in os.listdir(self.backup_dir):
            full_path = os.path.join(self.backup_dir, item)
            if not os.path.isdir(full_path):
                continue
                
            # Check if it's a backup directory
            if item.startswith(('full_', 'binlog_')):
                mtime = datetime.fromtimestamp(os.path.getctime(full_path))
                
                if mtime < cutoff_time:
                    self.logger.info(f"Deleting old backup: {full_path}")
                    try:
                        shutil.rmtree(full_path)
                        deleted_count += 1
                    except Exception as e:
                        self.logger.error(f"Failed to delete backup {full_path}: {e}")
        
        self.logger.info(f"Cleanup completed. Deleted {deleted_count} old backups.")
