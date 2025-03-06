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
def backup_full(tables: Optional[str] = None) -> None:
    """
    Create a full backup of the MySQL database.
    """
    table_list = parse_table_filter(tables) if tables else None
    
    try:
        backup_manager = BackupManager(config_manager)
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
def backup_incremental(base: str, tables: Optional[str] = None) -> None:
    """
    Create an incremental backup based on a previous backup.
    """
    table_list = parse_table_filter(tables) if tables else None
    
    try:
        backup_manager = BackupManager(config_manager)
        backup_path = backup_manager.create_incremental_backup(base, tables=table_list)
        
        click.echo(click.style(f"Incremental backup created successfully at:", fg='green'))
        click.echo(f"  {backup_path}")
        click.echo(f"  Size: {format_size(get_directory_size(backup_path))}")
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)


@backup.command('binlog')
def backup_binlog() -> None:
    """
    Backup binary logs.
    """
    try:
        backup_manager = BackupManager(config_manager)
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
    
    # Get all backup directories
    backups = []
    for item in os.listdir(backup_dir):
        full_path = os.path.join(backup_dir, item)
        if os.path.isdir(full_path):
            if item.startswith(('full_', 'binlog_', 'pre_restore_backup_')):
                # Get backup type from the directory name
                backup_type = 'Full' if item.startswith('full_') else \
                              'Binary Log' if item.startswith('binlog_') else \
                              'Pre-restore'
                
                # Get creation time
                ctime = os.path.getctime(full_path)
                creation_time = datetime.fromtimestamp(ctime).strftime('%Y-%m-%d %H:%M:%S')
                
                # Get size
                size = get_directory_size(full_path)
                
                backups.append((backup_type, item, full_path, creation_time, size))
    
    # Sort by creation time (newest first)
    backups.sort(key=lambda x: x[3], reverse=True)
    
    if not backups:
        click.echo(f"No backups found in {backup_dir}")
        return
    
    # Display backups
    click.echo(click.style(f"Backups in {backup_dir}:", fg='green'))
    for backup_type, name, path, creation_time, size in backups:
        click.echo(f"  {backup_type} Backup: {name}")
        click.echo(f"    Path: {path}")
        click.echo(f"    Created: {creation_time}")
        click.echo(f"    Size: {format_size(size)}")
        
        # Check for incremental backups if it's a full backup
        if backup_type == 'Full':
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
                    click.echo(f"    Incremental Backups:")
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
    backup_dir = backup_manager.backup_dir
    
    # Use configured retention period if not specified
    retention_days = days if days is not None else backup_manager.retention_days
    
    click.echo(f"Cleaning up backups older than {retention_days} days...")
    if dry_run:
        click.echo(click.style("DRY RUN: No backups will be deleted", fg='yellow'))
    
    cutoff_time = datetime.now().timestamp() - (retention_days * 24 * 60 * 60)
    deleted_count = 0
    skipped_count = 0
    
    # Find all backup directories to delete
    to_delete = []
    for item in os.listdir(backup_dir):
        full_path = os.path.join(backup_dir, item)
        if not os.path.isdir(full_path):
            continue
            
        # Only process backup directories
        if item.startswith(('full_', 'binlog_', 'pre_restore_backup_')):
            mtime = os.path.getctime(full_path)
            
            if mtime < cutoff_time:
                to_delete.append((item, full_path, datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')))
            else:
                skipped_count += 1
    
    # Sort by creation time (oldest first)
    to_delete.sort(key=lambda x: os.path.getctime(x[1]))
    
    # Display and delete backups
    if to_delete:
        for name, path, ctime in to_delete:
            size = format_size(get_directory_size(path))
            click.echo(f"Deleting: {name} (Created: {ctime}, Size: {size})")
            
            if not dry_run:
                try:
                    import shutil
                    shutil.rmtree(path)
                    deleted_count += 1
                except Exception as e:
                    click.echo(click.style(f"  Error deleting {path}: {e}", fg='red'))
    
    # Summary
    if not to_delete:
        click.echo("No backups found to delete.")
    else:
        if dry_run:
            click.echo(click.style(f"Would delete {len(to_delete)} backup(s), keeping {skipped_count} backup(s).", fg='yellow'))
        else:
            click.echo(click.style(f"Deleted {deleted_count} backup(s), kept {skipped_count} backup(s).", fg='green'))


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
    '--timestamp', '-t',
    required=True,
    help='Target timestamp for recovery (YYYY-MM-DD HH:MM:SS format).'
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
    timestamp: str,
    no_backup_existing: bool = False,
    tables: Optional[str] = None
) -> None:
    """
    Restore database to a specific point in time.
    """
    try:
        # Parse the timestamp
        target_time = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        
        table_list = parse_table_filter(tables) if tables else None
        backup_existing = not no_backup_existing
        
        recovery_manager = RecoveryManager(config_manager)
        recovery_manager.restore_to_point_in_time(target_time, backup_existing, table_list)
        
        click.echo(click.style(f"Point-in-time recovery to {timestamp} completed successfully", fg='green'))
    except ValueError:
        click.echo(click.style(f"Error: Invalid timestamp format. Use YYYY-MM-DD HH:MM:SS", fg='red'))
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)


if __name__ == '__main__':
    cli()
