"""
Common utility functions for MySQL backup and recovery.
"""
import os
import re
import logging
import mysql.connector
from typing import Dict, Any, Optional, List

from python_sql_backup.config.config_manager import ConfigManager


def ensure_dir(directory: str) -> None:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        directory: Path to the directory.
    """
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def get_mysql_connection(config: ConfigManager):
    """
    Get a MySQL connection based on the configuration.
    
    Args:
        config: Configuration manager instance.
        
    Returns:
        MySQL connection object.
    """
    db_config = config.get_section('DATABASE')
    
    connection_params = {
        'host': db_config.get('host', 'localhost'),
        'port': int(db_config.get('port', '3306')),
        'user': db_config.get('user', 'root')
    }
    
    if 'password' in db_config and db_config['password']:
        connection_params['password'] = db_config['password']
    
    if 'socket' in db_config and db_config['socket']:
        connection_params['unix_socket'] = db_config['socket']
    
    return mysql.connector.connect(**connection_params)


def parse_table_filter(table_filter: str) -> List[str]:
    """
    Parse table filter expression into a list of table patterns.
    
    Args:
        table_filter: Table filter expression, e.g., "db1.table1,db2.*"
        
    Returns:
        List of table patterns.
    """
    if not table_filter:
        return []
        
    # Split by comma and remove whitespace
    return [pattern.strip() for pattern in table_filter.split(',')]


def match_table(table_name: str, patterns: List[str]) -> bool:
    """
    Check if a table name matches any of the patterns.
    
    Args:
        table_name: Full table name (db.table).
        patterns: List of patterns to match against.
        
    Returns:
        True if the table matches any pattern, False otherwise.
    """
    if not patterns:
        return True  # If no patterns, match everything
    
    for pattern in patterns:
        # Handle wildcard patterns
        if '.' in pattern:
            db, table = pattern.split('.')
            if '.' in table_name:
                t_db, t_table = table_name.split('.')
                if (db == '*' or db == t_db) and (table == '*' or table == t_table):
                    return True
        else:
            # Pattern without db part
            if pattern == table_name or (pattern == '*' and '.' in table_name):
                return True
    
    return False


def sanitize_filename(name: str) -> str:
    """
    Sanitize a filename by removing invalid characters.
    
    Args:
        name: Original filename.
        
    Returns:
        Sanitized filename.
    """
    # Replace characters that are invalid in filenames
    return re.sub(r'[<>:"/\\|?*]', '_', name)


def format_size(size_bytes: int) -> str:
    """
    Format a size in bytes to human-readable format.
    
    Args:
        size_bytes: Size in bytes.
        
    Returns:
        Human-readable size string.
    """
    if size_bytes == 0:
        return "0 B"
        
    # Define units and their respective sizes
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    size = float(size_bytes)
    i = 0
    
    while size >= 1024.0 and i < len(units) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.2f} {units[i]}"


def get_directory_size(path: str) -> int:
    """
    Get the total size of a directory in bytes.
    
    Args:
        path: Path to the directory.
        
    Returns:
        Total size in bytes.
    """
    total_size = 0
    
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            if os.path.exists(file_path):
                total_size += os.path.getsize(file_path)
    
    return total_size


def is_tool_available(name: str) -> bool:
    """
    Check if a command-line tool is available.
    
    Args:
        name: Name of the tool.
        
    Returns:
        True if the tool is available, False otherwise.
    """
    from shutil import which
    return which(name) is not None


def setup_logger(name: str, log_file: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """
    Set up a logger.
    
    Args:
        name: Name of the logger.
        log_file: Path to the log file.
        level: Logging level.
        
    Returns:
        Logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Create file handler if log_file is provided
    if log_file:
        ensure_dir(os.path.dirname(log_file))
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger
