#!/usr/bin/env python3
"""
恢复功能测试模块
"""
import os
import sys
import shutil
import unittest
from datetime import datetime, timedelta
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from python_sql_backup.config.config_manager import ConfigManager
from python_sql_backup.backup.backup_manager import BackupManager
from python_sql_backup.recovery.recovery_manager import RecoveryManager


class TestRecoveryManager(unittest.TestCase):
    """恢复管理器测试类"""

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
            
        # 初始化备份和恢复管理器
        self.backup_manager = BackupManager(self.config)
        self.recovery_manager = RecoveryManager(self.config)
        
        # 创建测试数据库和表
        self._create_test_data()
        
        # 创建测试备份
        self.full_backup_result = self.backup_manager.create_full_backup()
        
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
                cursor.execute("CREATE DATABASE IF NOT EXISTS test_recovery")
                cursor.execute("USE test_recovery")
                
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
                cursor.execute("DROP DATABASE IF EXISTS test_recovery")
            connection.commit()
        finally:
            connection.close()
            
    def _get_table_data(self):
        """获取测试表数据"""
        import mysql.connector
        
        db_config = self.config.get_section('DATABASE')
        connection = mysql.connector.connect(**db_config)
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("USE test_recovery")
                cursor.execute("SELECT id, name FROM test_table ORDER BY id")
                return cursor.fetchall()
        finally:
            connection.close()
            
    def test_restore_full_backup(self):
        """测试全量恢复功能"""
        # 修改原始数据
        self._modify_test_data()
        original_data = self._get_table_data()
        
        # 执行恢复
        self.recovery_manager.restore_full_backup(
            self.full_backup_result['backup_path'],
            backup_existing=True
        )
        
        # 验证数据是否恢复
        restored_data = self._get_table_data()
        self.assertNotEqual(original_data, restored_data)
        self.assertEqual(len(restored_data), 3)  # 初始的3条记录
        
    def test_restore_incremental_backup(self):
        """测试增量恢复功能"""
        # 创建增量备份前的数据修改
        self._modify_test_data()
        
        # 创建增量备份
        inc_result = self.backup_manager.create_incremental_backup(
            self.full_backup_result['backup_path']
        )
        
        # 再次修改数据
        self._modify_test_data_again()
        original_data = self._get_table_data()
        
        # 执行增量恢复
        self.recovery_manager.restore_incremental_backup(
            self.full_backup_result['backup_path'],
            [inc_result['backup_path']],
            backup_existing=True
        )
        
        # 验证数据是否恢复到增量备份时的状态
        restored_data = self._get_table_data()
        self.assertNotEqual(original_data, restored_data)
        self.assertEqual(len(restored_data), 5)  # 初始3条 + 增量前新增2条
        
    def test_restore_specific_tables(self):
        """测试指定表恢复功能"""
        # 修改原始数据
        self._modify_test_data()
        original_data = self._get_table_data()
        
        # 执行指定表的恢复
        self.recovery_manager.restore_full_backup(
            self.full_backup_result['backup_path'],
            backup_existing=True,
            specific_tables=['test_recovery.test_table']
        )
        
        # 验证数据是否恢复
        restored_data = self._get_table_data()
        self.assertNotEqual(original_data, restored_data)
        self.assertEqual(len(restored_data), 3)  # 初始的3条记录
        
    def _modify_test_data(self):
        """修改测试数据"""
        import mysql.connector
        
        db_config = self.config.get_section('DATABASE')
        connection = mysql.connector.connect(**db_config)
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("USE test_recovery")
                cursor.execute("""
                    INSERT INTO test_table (name) VALUES 
                    ('test4'), ('test5')
                """)
            connection.commit()
        finally:
            connection.close()
            
    def _modify_test_data_again(self):
        """再次修改测试数据"""
        import mysql.connector
        
        db_config = self.config.get_section('DATABASE')
        connection = mysql.connector.connect(**db_config)
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("USE test_recovery")
                cursor.execute("""
                    INSERT INTO test_table (name) VALUES 
                    ('test6'), ('test7')
                """)
                cursor.execute("UPDATE test_table SET name = 'modified' WHERE id = 1")
            connection.commit()
        finally:
            connection.close()
            
    def test_point_in_time_recovery(self):
        """测试时间点恢复功能"""
        # 记录开始时间
        start_time = datetime.now()
        
        # 等待1秒以确保时间戳不同
        time.sleep(1)
        
        # 修改数据并创建增量备份
        self._modify_test_data()
        inc_result = self.backup_manager.create_incremental_backup(
            self.full_backup_result['backup_path']
        )
        
        # 等待1秒
        time.sleep(1)
        
        # 记录中间时间点
        middle_time = datetime.now()
        
        # 等待1秒
        time.sleep(1)
        
        # 再次修改数据
        self._modify_test_data_again()
        
        # 等待1秒
        time.sleep(1)
        
        # 记录结束时间
        end_time = datetime.now()
        
        # 执行时间点恢复到middle_time
        self.recovery_manager.restore_to_point_in_time(
            start_time,
            middle_time,
            backup_existing=True
        )
        
        # 验证数据是否恢复到middle_time时的状态
        restored_data = self._get_table_data()
        self.assertEqual(len(restored_data), 5)  # 初始3条 + 第一次修改的2条
        
if __name__ == '__main__':
    unittest.main()