#!/usr/bin/env python3
"""
备份功能测试模块
"""
import os
import sys
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from python_sql_backup.config.config_manager import ConfigManager
from python_sql_backup.backup.backup_manager import BackupManager


class TestBackupManager(unittest.TestCase):
    """备份管理器测试类"""

    def setUp(self):
        """测试前准备"""
        # 模拟配置管理器
        self.config = MagicMock()
        self.config.get.side_effect = self._mock_config_get
        self.config.get_section.return_value = {
            'host': 'localhost',
            'port': '3306',
            'user': 'testuser',
            'password': 'testpassword'
        }
        
        # 测试目录
        self.test_backup_dir = '/tmp/mysql_backup_test'
        if not os.path.exists(self.test_backup_dir):
            os.makedirs(self.test_backup_dir)
            
        # 初始化备份管理器
        self.backup_manager = BackupManager(self.config)
        self.backup_manager.backup_dir = self.test_backup_dir
        
    def tearDown(self):
        """测试后清理"""
        # 可以选择删除测试目录
        pass
        
    def _mock_config_get(self, section, key, fallback=None):
        """模拟配置获取函数"""
        if section == 'BACKUP' and key == 'backup_dir':
            return self.test_backup_dir
        elif section == 'BACKUP' and key == 'retention_days':
            return '7'
        elif section == 'BACKUP' and key == 'backup_format':
            return '%Y%m%d_%H%M%S'
        elif section == 'BACKUP' and key == 'threads':
            return '2'
        elif section == 'BACKUP' and key == 'compress':
            return 'true'
        return fallback
        
    @patch('subprocess.run')
    def test_full_backup(self, mock_run):
        """测试全量备份功能"""
        # 模拟子进程执行成功
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process
        
        # 执行备份
        result = self.backup_manager.create_full_backup()
        
        # 验证结果
        self.assertTrue(result['success'])
        self.assertIn('backup_path', result)
        
        # 验证命令是否正确构建
        args, kwargs = mock_run.call_args
        cmd = args[0]
        self.assertIn('xtrabackup', cmd)
        self.assertIn('--backup', cmd)
        
    @patch('subprocess.run')
    def test_incremental_backup(self, mock_run):
        """测试增量备份功能"""
        # 模拟子进程执行成功
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process
        
        # 模拟基础备份路径
        base_dir = os.path.join(self.test_backup_dir, 'full_20250101_120000')
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
            
        # 执行增量备份
        result = self.backup_manager.create_incremental_backup(base_dir)
        
        # 验证结果
        self.assertTrue(result['success'])
        self.assertIn('backup_path', result)
        
        # 验证命令是否正确构建
        args, kwargs = mock_run.call_args
        cmd = args[0]
        self.assertIn('xtrabackup', cmd)
        self.assertIn('--backup', cmd)
        self.assertIn('--incremental-basedir', ' '.join(cmd))
        
    def test_list_backups(self):
        """测试列出备份功能"""
        # 创建模拟备份目录
        full_dir = os.path.join(self.test_backup_dir, 'full_20250101_120000')
        inc_dir = os.path.join(full_dir, 'inc')
        inc1_dir = os.path.join(inc_dir, 'inc_20250102_120000')
        
        os.makedirs(full_dir, exist_ok=True)
        os.makedirs(inc1_dir, exist_ok=True)
        
        # 测试列出备份
        backups = self.backup_manager.list_backups()
        
        # 验证结果
        self.assertGreaterEqual(len(backups), 1)
        self.assertEqual(backups[0]['type'], 'full')
        self.assertEqual(backups[0]['path'], full_dir)
        
        
if __name__ == '__main__':
    unittest.main()