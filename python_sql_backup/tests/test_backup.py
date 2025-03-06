#!/usr/bin/env python3
"""
备份功能测试模块
"""
import os
import sys
import shutil
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from python_sql_backup.config.config_manager import ConfigManager
from python_sql_backup.backup.backup_manager import BackupManager


class TestBackupManager(unittest.TestCase):
    """备份管理器测试类"""

    def setUp(self):
        """测试前准备"""
        # 读取测试配置文件
        test_config_path = os.path.join(os.path.dirname(__file__), 'test_config.ini')
        if not os.path.exists(test_config_path):
            raise FileNotFoundError(f"测试配置文件不存在: {test_config_path}")
            
        self.config = ConfigManager(test_config_path)
        
        # 测试目录
        self.test_backup_dir = self.config.get('BACKUP', 'backup_dir')
        if not os.path.exists(self.test_backup_dir):
            os.makedirs(self.test_backup_dir)
            
        # 初始化备份管理器
        self.backup_manager = BackupManager(self.config)
        
        # 创建测试数据库和表
        self._create_test_data()
        
    def tearDown(self):
        """测试后清理"""
        # 清理测试数据库
        self._cleanup_test_data()
        
        # 清理测试备份目录
        if os.path.exists(self.test_backup_dir):
            shutil.rmtree(self.test_backup_dir)
            
    def _create_test_data(self):
        """创建测试数据"""
        import mysql.connector
        
        db_config = self.config.get_section('DATABASE')
        connection = mysql.connector.connect(**db_config)
        
        try:
            with connection.cursor() as cursor:
                # 创建测试数据库
                cursor.execute("CREATE DATABASE IF NOT EXISTS test_backup")
                cursor.execute("USE test_backup")
                
                # 创建测试表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS test_table (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 插入测试数据
                cursor.execute("""
                    INSERT INTO test_table (name) VALUES 
                    ('test1'), ('test2'), ('test3')
                """)
                
            connection.commit()
        finally:
            connection.close()
            
    def _cleanup_test_data(self):
        """清理测试数据"""
        import mysql.connector
        
        db_config = self.config.get_section('DATABASE')
        connection = mysql.connector.connect(**db_config)
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("DROP DATABASE IF EXISTS test_backup")
            connection.commit()
        finally:
            connection.close()
        
    def test_full_backup(self):
        """测试全量备份功能"""
        # 执行备份
        result = self.backup_manager.create_full_backup()
        
        # 验证结果
        self.assertTrue(result['success'])
        self.assertIn('backup_path', result)
        
        # 验证备份文件是否存在
        backup_path = result['backup_path']
        self.assertTrue(os.path.exists(backup_path))
        
        # 验证备份内容
        xtrabackup_info_path = os.path.join(backup_path, 'xtrabackup_info')
        self.assertTrue(os.path.exists(xtrabackup_info_path))
        
    def test_incremental_backup(self):
        """测试增量备份功能"""
        # 先创建全量备份
        full_result = self.backup_manager.create_full_backup()
        self.assertTrue(full_result['success'])
        
        # 修改测试数据
        self._modify_test_data()
        
        # 执行增量备份
        inc_result = self.backup_manager.create_incremental_backup(full_result['backup_path'])
        
        # 验证结果
        self.assertTrue(inc_result['success'])
        self.assertIn('backup_path', inc_result)
        
        # 验证增量备份文件是否存在
        inc_path = inc_result['backup_path']
        self.assertTrue(os.path.exists(inc_path))
        
        # 验证增量备份内容
        xtrabackup_info_path = os.path.join(inc_path, 'xtrabackup_info')
        self.assertTrue(os.path.exists(xtrabackup_info_path))
        
    def _modify_test_data(self):
        """修改测试数据用于增量备份测试"""
        import mysql.connector
        
        db_config = self.config.get_section('DATABASE')
        connection = mysql.connector.connect(**db_config)
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("USE test_backup")
                cursor.execute("""
                    INSERT INTO test_table (name) VALUES 
                    ('test4'), ('test5')
                """)
            connection.commit()
        finally:
            connection.close()
        
    def test_list_backups(self):
        """测试列出备份功能"""
        # 创建一些测试备份
        self.backup_manager.create_full_backup()
        
        # 测试列出备份
        backups = self.backup_manager.list_backups()
        
        # 验证结果
        self.assertGreaterEqual(len(backups), 1)
        self.assertEqual(backups[0]['type'], 'full')
        
    def test_clean_old_backups(self):
        """测试清理旧备份功能"""
        # 创建一些测试备份
        self.backup_manager.create_full_backup()
        
        # 修改备份文件的时间戳使其显示为旧备份
        backup_list = self.backup_manager.list_backups()
        for backup in backup_list:
            old_time = datetime.now().timestamp() - (8 * 24 * 60 * 60)  # 8天前
            os.utime(backup['path'], (old_time, old_time))
        
        # 设置保留期为7天
        self.backup_manager.retention_days = 7
        
        # 执行清理
        self.backup_manager.clean_old_backups(dry_run=False)
        
        # 验证旧备份已被删除
        remaining_backups = self.backup_manager.list_backups()
        self.assertEqual(len(remaining_backups), 0)
        
    def test_backup_specific_tables(self):
        """测试指定表的备份功能"""
        # 执行指定表的备份
        tables = ['test_backup.test_table']
        result = self.backup_manager.create_full_backup(tables=tables)
        
        # 验证结果
        self.assertTrue(result['success'])
        self.assertIn('backup_path', result)
        
        # 验证备份文件是否存在
        backup_path = result['backup_path']
        self.assertTrue(os.path.exists(backup_path))
        
        # 验证备份内容
        xtrabackup_info_path = os.path.join(backup_path, 'xtrabackup_info')
        self.assertTrue(os.path.exists(xtrabackup_info_path))
        
if __name__ == '__main__':
    unittest.main()