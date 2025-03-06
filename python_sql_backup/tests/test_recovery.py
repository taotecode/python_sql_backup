#!/usr/bin/env python3
"""
恢复功能测试模块
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from python_sql_backup.config.config_manager import ConfigManager
from python_sql_backup.recovery.recovery_manager import RecoveryManager


class TestRecoveryManager(unittest.TestCase):
    """恢复管理器测试类"""

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
            
        # 模拟备份路径
        self.full_backup_path = os.path.join(self.test_backup_dir, 'full_20250101_120000')
        if not os.path.exists(self.full_backup_path):
            os.makedirs(self.full_backup_path)
            
        # 初始化恢复管理器
        self.recovery_manager = RecoveryManager(self.config)
        
    def _mock_config_get(self, section, key, fallback=None):
        """模拟配置获取函数"""
        if section == 'BACKUP' and key == 'backup_dir':
            return self.test_backup_dir
        elif section == 'BACKUP' and key == 'threads':
            return '2'
        return fallback
        
    @patch('subprocess.run')
    def test_prepare_backup(self, mock_run):
        """测试准备备份功能"""
        # 模拟子进程执行成功
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process
        
        # 执行准备备份
        self.recovery_manager._prepare_backup(self.full_backup_path)
        
        # 验证命令是否正确构建
        args, kwargs = mock_run.call_args
        cmd = args[0]
        self.assertIn('xtrabackup', cmd)
        self.assertIn('--prepare', cmd)
        
    @patch('subprocess.run')
    def test_restore_full(self, mock_run):
        """测试全量恢复功能"""
        # 模拟子进程执行成功
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process
        
        # 执行恢复
        result = self.recovery_manager.restore_full_backup(
            self.full_backup_path,
            backup_existing=True
        )
        
        # 验证结果
        self.assertTrue(result['success'])
        
        # 验证命令是否正确构建
        called_cmds = [call[0][0] for call in mock_run.call_args_list]
        
        # 应该有prepare和restore两个命令
        prepare_cmd_found = False
        restore_cmd_found = False
        
        for cmd in called_cmds:
            if '--prepare' in cmd:
                prepare_cmd_found = True
            if '--copy-back' in cmd:
                restore_cmd_found = True
                
        self.assertTrue(prepare_cmd_found)
        self.assertTrue(restore_cmd_found)


if __name__ == '__main__':
    unittest.main()