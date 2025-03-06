"""
Command-line interface for MySQL backup and recovery.
"""
import os
import sys
import time
import click
import logging
from datetime import datetime
from typing import List, Optional, Tuple

from python_sql_backup.config.config_manager import ConfigManager
from python_sql_backup.backup.backup_manager import BackupManager
from python_sql_backup.recovery.recovery_manager import RecoveryManager
from python_sql_backup.cli.interactive import InteractiveAssistant
from python_sql_backup.utils.common import (
    ensure_dir, get_directory_size, format_size, is_tool_available, parse_table_filter
)


# Create a ConfigManager instance
config_manager = None


def initialize_config(config_file: Optional[str] = None) -> None:
    """
    Initialize the configuration manager.
    
    Args:
        config_file: Path to the configuration file.
    """
    global config_manager
    config_manager = ConfigManager(config_file)


def check_prerequisites() -> bool:
    """
    Check if all prerequisites are met.
    
    Returns:
        True if all prerequisites are met, False otherwise.
    """
    required_tools = ['xtrabackup', 'mysql', 'mysqlbinlog']
    missing_tools = []
    
    for tool in required_tools:
        if not is_tool_available(tool):
            missing_tools.append(tool)
    
    if missing_tools:
        click.echo(click.style(
            f"Error: The following required tools are missing: {', '.join(missing_tools)}",
            fg='red'
        ))
        click.echo("Please install the missing tools and try again.")
        return False
    
    return True


@click.group()
@click.option(
    '--config', '-c',
    type=click.Path(exists=False),
    help='Path to the configuration file.'
)
@click.version_option()
def cli(config: str) -> None:
    """
    MySQL backup and recovery tool using XtraBackup.
    
    This tool provides functionality for full, incremental, and binary log backups,
    as well as full, incremental, point-in-time, and table-specific recovery.
    """
    # Initialize configuration
    initialize_config(config)
    
    # Check prerequisites
    if not check_prerequisites():
        sys.exit(1)


@cli.command('interactive')
def interactive_mode() -> None:
    """
    Start the interactive assistant.
    """
    click.echo(click.style("Starting interactive assistant...", fg='green'))
    
    # 创建交互式助手
    assistant = InteractiveAssistant(config_manager)
    
    # 选择操作类型
    operation_type = click.prompt(
        "请选择操作类型",
        type=click.Choice(['backup', 'restore']),
        default='backup'
    )
    
    if operation_type == 'backup':
        assistant.start_backup_assistant()
    else:
        assistant.start_recovery_assistant()


@cli.group()
def backup() -> None:
    """
    Backup operations.
    """
    pass


@backup.command('full')
@click.option(
    '--tables', '-t',
    help='Comma-separated list of tables to backup (db.table format).'
)
@click.option(
    '--no-clean',
    is_flag=True,
    help='Do not clean old backups before creating a new one.'
)
def backup_full(tables: Optional[str] = None, no_clean: bool = False) -> None:
    """
    Create a full backup of the MySQL database.
    """
    table_list = parse_table_filter(tables) if tables else None
    
    try:
        backup_manager = BackupManager(config_manager)
        
        # 如果需要清理旧备份
        if not no_clean and config_manager.get('BACKUP', 'auto_clean', fallback='true').lower() == 'true':
            click.echo("Cleaning old backups before creating a new one...")
            backup_manager.clean_old_backups(dry_run=False)
        
        backup_path = backup_manager.create_full_backup(tables=table_list)
        
        click.echo(click.style(f"Full backup created successfully at:", fg='green'))
        click.echo(f"  {backup_path}")
        click.echo(f"  Size: {format_size(get_directory_size(backup_path))}")
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)


@backup.command('incremental')
@click.option(
    '--base', '-b',
    required=True,
    help='Path to the base backup (full or incremental).'
)
@click.option(
    '--tables', '-t',
    help='Comma-separated list of tables to backup (db.table format).'
)
@click.option(
    '--no-clean',
    is_flag=True,
    help='Do not clean old backups before creating a new one.'
)
def backup_incremental(base: str, tables: Optional[str] = None, no_clean: bool = False) -> None:
    """
    Create an incremental backup based on a previous backup.
    """
    table_list = parse_table_filter(tables) if tables else None
    
    try:
        backup_manager = BackupManager(config_manager)
        
        # 如果需要清理旧备份
        if not no_clean and config_manager.get('BACKUP', 'auto_clean', fallback='true').lower() == 'true':
            click.echo("Cleaning old backups before creating a new one...")
            backup_manager.clean_old_backups(dry_run=False)
        
        backup_path = backup_manager.create_incremental_backup(base, tables=table_list)
        
        click.echo(click.style(f"Incremental backup created successfully at:", fg='green'))
        click.echo(f"  {backup_path}")
        click.echo(f"  Size: {format_size(get_directory_size(backup_path))}")
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)


@backup.command('binlog')
@click.option(
    '--no-clean',
    is_flag=True,
    help='Do not clean old backups before creating a new one.'
)
def backup_binlog(no_clean: bool = False) -> None:
    """
    Backup binary logs.
    """
    try:
        backup_manager = BackupManager(config_manager)
        
        # 如果需要清理旧备份
        if not no_clean and config_manager.get('BACKUP', 'auto_clean', fallback='true').lower() == 'true':
            click.echo("Cleaning old backups before creating a new one...")
            backup_manager.clean_old_backups(dry_run=False)
        
        backup_path = backup_manager.backup_binlog()
        
        click.echo(click.style(f"Binary log backup created successfully at:", fg='green'))
        click.echo(f"  {backup_path}")
        click.echo(f"  Size: {format_size(get_directory_size(backup_path))}")
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)


@backup.command('list')
def list_backups() -> None:
    """
    List all available backups.
    """
    backup_manager = BackupManager(config_manager)
    backup_dir = backup_manager.backup_dir
    
    if not os.path.exists(backup_dir):
        click.echo(f"No backups found in {backup_dir}")
        return
    
    # 使用新的查找备份方法
    full_backups = backup_manager._find_backups('full')
    binlog_backups = backup_manager._find_backups('binlog')
    
    all_backups = []
    all_backups.extend([(name, path, '全量备份') for name, path in full_backups])
    all_backups.extend([(name, path, '二进制日志备份') for name, path in binlog_backups])
    
    # 按创建时间排序（最新的在前）
    all_backups.sort(key=lambda x: os.path.getctime(x[1]), reverse=True)
    
    if not all_backups:
        click.echo(f"No backups found in {backup_dir}")
        return
    
    # Display backups
    click.echo(click.style(f"Backups in {backup_dir}:", fg='green'))
    for name, path, backup_type in all_backups:
        ctime = os.path.getctime(path)
        creation_time = datetime.fromtimestamp(ctime).strftime('%Y-%m-%d %H:%M:%S')
        size = get_directory_size(path) if os.path.isdir(path) else os.path.getsize(path)
        
        click.echo(f"  {backup_type}: {name}")
        click.echo(f"    Path: {path}")
        click.echo(f"    Created: {creation_time}")
        click.echo(f"    Size: {format_size(size)}")
        
        # 检查增量备份
        if backup_type == '全量备份' and os.path.isdir(path):
            inc_dir = os.path.join(path, 'inc')
            if os.path.exists(inc_dir) and os.path.isdir(inc_dir):
                incremental_backups = []
                
                for inc_item in os.listdir(inc_dir):
                    if inc_item.startswith('inc_'):
                        inc_path = os.path.join(inc_dir, inc_item)
                        if os.path.isdir(inc_path):
                            inc_ctime = os.path.getctime(inc_path)
                            inc_creation_time = datetime.fromtimestamp(inc_ctime).strftime('%Y-%m-%d %H:%M:%S')
                            inc_size = get_directory_size(inc_path)
                            incremental_backups.append((inc_item, inc_path, inc_creation_time, inc_size))
                
                # Sort incrementals by creation time
                incremental_backups.sort(key=lambda x: x[2])
                
                if incremental_backups:
                    click.echo(f"    增量备份:")
                    for inc_name, inc_path, inc_time, inc_size in incremental_backups:
                        click.echo(f"      {inc_name}")
                        click.echo(f"        Path: {inc_path}")
                        click.echo(f"        Created: {inc_time}")
                        click.echo(f"        Size: {format_size(inc_size)}")
        
        click.echo()  # Add an empty line between backups


@backup.command('clean')
@click.option(
    '--days', '-d',
    type=int,
    help='Delete backups older than the specified number of days.'
)
@click.option(
    '--dry-run', is_flag=True,
    help='Show what would be deleted without actually deleting anything.'
)
def clean_backups(days: Optional[int] = None, dry_run: bool = False) -> None:
    """
    Clean up old backups based on retention policy.
    """
    backup_manager = BackupManager(config_manager)
    
    # Use configured retention period if not specified
    retention_days = days if days is not None else backup_manager.retention_days
    
    click.echo(f"Cleaning up backups older than {retention_days} days...")
    if dry_run:
        click.echo(click.style("DRY RUN: No backups will be deleted", fg='yellow'))
    
    try:
        backup_manager.clean_old_backups(dry_run=dry_run)
        
        if dry_run:
            click.echo(click.style("Dry run completed. No backups were deleted.", fg='green'))
        else:
            click.echo(click.style("Backup cleanup completed successfully.", fg='green'))
    except Exception as e:
        click.echo(click.style(f"Error during backup cleanup: {e}", fg='red'))
        sys.exit(1)


@cli.group()
def restore() -> None:
    """
    Restore operations.
    """
    pass


@restore.command('full')
@click.argument('backup_path', type=click.Path(exists=True))
@click.option(
    '--no-backup-existing', is_flag=True,
    help='Do not backup existing data before restoration.'
)
@click.option(
    '--tables', '-t',
    help='Comma-separated list of tables to restore (db.table format).'
)
@click.confirmation_option(
    prompt='This will overwrite existing MySQL data. Are you sure?'
)
def restore_full(
    backup_path: str,
    no_backup_existing: bool = False,
    tables: Optional[str] = None
) -> None:
    """
    Restore a full backup.
    """
    table_list = parse_table_filter(tables) if tables else None
    backup_existing = not no_backup_existing
    
    try:
        recovery_manager = RecoveryManager(config_manager)
        recovery_manager.restore_full_backup(backup_path, backup_existing, table_list)
        
        click.echo(click.style(f"Full backup restored successfully from {backup_path}", fg='green'))
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)


@restore.command('incremental')
@click.option(
    '--full', '-f',
    required=True,
    help='Path to the full backup.'
)
@click.option(
    '--incremental', '-i',
    required=True,
    multiple=True,
    help='Path to incremental backup(s), can be specified multiple times in chronological order.'
)
@click.option(
    '--no-backup-existing', is_flag=True,
    help='Do not backup existing data before restoration.'
)
@click.option(
    '--tables', '-t',
    help='Comma-separated list of tables to restore (db.table format).'
)
@click.confirmation_option(
    prompt='This will overwrite existing MySQL data. Are you sure?'
)
def restore_incremental(
    full: str,
    incremental: List[str],
    no_backup_existing: bool = False,
    tables: Optional[str] = None
) -> None:
    """
    Restore a full backup with incremental backups.
    """
    table_list = parse_table_filter(tables) if tables else None
    backup_existing = not no_backup_existing
    
    try:
        recovery_manager = RecoveryManager(config_manager)
        recovery_manager.restore_incremental_backup(full, list(incremental), backup_existing, table_list)
        
        click.echo(click.style(f"Incremental backup restored successfully", fg='green'))
        click.echo(f"Full backup: {full}")
        for i, inc in enumerate(incremental):
            click.echo(f"Incremental backup {i+1}: {inc}")
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)


@restore.command('point-in-time')
@click.option(
    '--start-time', '-s',
    required=True,
    help='Start timestamp for recovery (YYYY-MM-DD HH:MM:SS format).'
)
@click.option(
    '--end-time', '-e',
    help='End timestamp for recovery (YYYY-MM-DD HH:MM:SS format). If not provided, will use start-time.'
)
@click.option(
    '--no-backup-existing', is_flag=True,
    help='Do not backup existing data before restoration.'
)
@click.option(
    '--tables', 
    help='Comma-separated list of tables to restore (db.table format).'
)
@click.confirmation_option(
    prompt='This will overwrite existing MySQL data. Are you sure?'
)
def restore_point_in_time(
    start_time: str,
    end_time: Optional[str] = None,
    no_backup_existing: bool = False,
    tables: Optional[str] = None
) -> None:
    """
    Restore database to a specific point in time range.
    """
    try:
        # Parse the timestamps
        start_datetime = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
        end_datetime = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S') if end_time else None
        
        if end_datetime and end_datetime <= start_datetime:
            click.echo(click.style(f"Error: End time must be later than start time", fg='red'))
            sys.exit(1)
        
        table_list = parse_table_filter(tables) if tables else None
        backup_existing = not no_backup_existing
        
        recovery_manager = RecoveryManager(config_manager)
        recovery_manager.restore_to_point_in_time(start_datetime, end_datetime, backup_existing, table_list)
        
        if end_datetime:
            click.echo(click.style(f"Point-in-time recovery from {start_time} to {end_time} completed successfully", fg='green'))
        else:
            click.echo(click.style(f"Point-in-time recovery to {start_time} completed successfully", fg='green'))
    except ValueError:
        click.echo(click.style(f"Error: Invalid timestamp format. Use YYYY-MM-DD HH:MM:SS", fg='red'))
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)


@restore.command('binlog')
@click.argument('binlog_paths', nargs=-1, type=click.Path(exists=True))
@click.option(
    '--start-time', '-s',
    help='Start timestamp for recovery (YYYY-MM-DD HH:MM:SS format).'
)
@click.option(
    '--end-time', '-e',
    help='End timestamp for recovery (YYYY-MM-DD HH:MM:SS format).'
)
@click.option(
    '--tables', 
    help='Comma-separated list of tables to restore (db.table format).'
)
@click.confirmation_option(
    prompt='This will modify your database. Are you sure?'
)
def restore_binlog(
    binlog_paths: List[str],
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    tables: Optional[str] = None
) -> None:
    """
    Apply binary logs to the database.
    """
    if not binlog_paths:
        click.echo(click.style("Error: No binlog paths provided", fg='red'))
        sys.exit(1)
    
    try:
        # Parse the timestamps
        start_datetime = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S') if start_time else None
        end_datetime = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S') if end_time else None
        
        if start_datetime and end_datetime and end_datetime <= start_datetime:
            click.echo(click.style(f"Error: End time must be later than start time", fg='red'))
            sys.exit(1)
        
        table_list = parse_table_filter(tables) if tables else None
        
        recovery_manager = RecoveryManager(config_manager)
        recovery_manager.apply_binlog(list(binlog_paths), start_datetime, end_datetime, table_list)
        
        click.echo(click.style(f"Binary logs applied successfully", fg='green'))
    except ValueError:
        click.echo(click.style(f"Error: Invalid timestamp format. Use YYYY-MM-DD HH:MM:SS", fg='red'))
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)


if __name__ == '__main__':
    cli()
