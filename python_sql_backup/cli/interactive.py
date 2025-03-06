"""
交互式助手模块，为用户提供引导式的备份和恢复操作体验。
"""
import os
import sys
import click
import datetime
from typing import List, Optional, Dict, Any, Tuple

from python_sql_backup.config.config_manager import ConfigManager
from python_sql_backup.backup.backup_manager import BackupManager
from python_sql_backup.recovery.recovery_manager import RecoveryManager
from python_sql_backup.utils.common import format_size, get_directory_size


class InteractiveAssistant:
    """交互式助手类，引导用户完成备份和恢复操作"""

    def __init__(self, config_manager: ConfigManager):
        """
        初始化交互式助手
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config = config_manager
        self.backup_manager = BackupManager(config_manager)
        self.recovery_manager = RecoveryManager(config_manager)
    
    def start_backup_assistant(self) -> None:
        """启动备份操作助手"""
        click.clear()
        click.echo(click.style("=== MySQL 备份助手 ===", fg='green', bold=True))
        click.echo("此助手将引导您完成MySQL数据库的备份操作。\n")
        
        # 自动清理过期备份
        click.echo("正在检查和清理过期备份...")
        try:
            self.backup_manager.clean_old_backups(dry_run=False)
            click.echo(click.style("✓ 过期备份清理完成", fg='green'))
        except Exception as e:
            click.echo(click.style(f"! 清理过期备份时出错: {e}", fg='yellow'))
        
        # 选择备份类型
        backup_type = click.prompt(
            "请选择备份类型",
            type=click.Choice(['full', 'incremental', 'binlog']),
            default='full'
        )
        
        if backup_type == 'full':
            self._handle_full_backup()
        elif backup_type == 'incremental':
            self._handle_incremental_backup()
        elif backup_type == 'binlog':
            self._handle_binlog_backup()
    
    def _handle_full_backup(self) -> None:
        """处理全量备份操作"""
        click.echo("\n=== 全量备份 ===")
        
        # 询问是否需要指定数据库和表
        use_specific_tables = click.confirm("是否需要只备份特定数据库的特定表？", default=False)
        
        tables = None
        if use_specific_tables:
            # 首先选择数据库
            database = click.prompt("请输入要备份的数据库名称")
            
            # 然后选择表
            tables_input = click.prompt(
                "请输入要备份的表名(多个表用逗号分隔，输入'*'表示备份该数据库的所有表)",
                default='*'
            )
            
            if tables_input == '*':
                tables = [f"{database}.*"]
            else:
                tables = [f"{database}.{table.strip()}" for table in tables_input.split(',')]
        
        try:
            click.echo("开始执行全量备份...")
            backup_path = self.backup_manager.create_full_backup(tables=tables)
            
            click.echo(click.style("\n✓ 全量备份创建成功！", fg='green', bold=True))
            click.echo(f"  备份路径: {backup_path}")
            click.echo(f"  备份大小: {format_size(get_directory_size(backup_path))}")
        except Exception as e:
            click.echo(click.style(f"\n✗ 备份失败: {e}", fg='red', bold=True))
    
    def _handle_incremental_backup(self) -> None:
        """处理增量备份操作"""
        click.echo("\n=== 增量备份 ===")
        
        # 获取可用的全量备份列表
        available_backups = self._get_available_backups(full_only=True)
        
        if not available_backups:
            click.echo(click.style("没有找到可用的全量备份，无法创建增量备份。请先创建全量备份。", fg='yellow'))
            return
        
        # 显示可用备份
        self._display_available_backups(available_backups)
        
        # 选择基础备份
        selected_index = click.prompt(
            "请选择要基于哪个备份创建增量备份（输入编号）",
            type=int,
            default=1
        )
        
        if selected_index < 1 or selected_index > len(available_backups):
            click.echo(click.style("无效的选择", fg='red'))
            return
        
        base_backup = available_backups[selected_index - 1][2]
        
        # 询问是否需要指定数据库和表
        use_specific_tables = click.confirm("是否需要只备份特定数据库的特定表？", default=False)
        
        tables = None
        if use_specific_tables:
            # 首先选择数据库
            database = click.prompt("请输入要备份的数据库名称")
            
            # 然后选择表
            tables_input = click.prompt(
                "请输入要备份的表名(多个表用逗号分隔，输入'*'表示备份该数据库的所有表)",
                default='*'
            )
            
            if tables_input == '*':
                tables = [f"{database}.*"]
            else:
                tables = [f"{database}.{table.strip()}" for table in tables_input.split(',')]
        
        try:
            click.echo("开始执行增量备份...")
            backup_path = self.backup_manager.create_incremental_backup(base_backup, tables=tables)
            
            click.echo(click.style("\n✓ 增量备份创建成功！", fg='green', bold=True))
            click.echo(f"  备份路径: {backup_path}")
            click.echo(f"  备份大小: {format_size(get_directory_size(backup_path))}")
        except Exception as e:
            click.echo(click.style(f"\n✗ 备份失败: {e}", fg='red', bold=True))
    
    def _handle_binlog_backup(self) -> None:
        """处理二进制日志备份操作"""
        click.echo("\n=== 二进制日志备份 ===")
        
        try:
            click.echo("开始执行二进制日志备份...")
            backup_path = self.backup_manager.backup_binlog()
            
            click.echo(click.style("\n✓ 二进制日志备份创建成功！", fg='green', bold=True))
            click.echo(f"  备份路径: {backup_path}")
            click.echo(f"  备份大小: {format_size(get_directory_size(backup_path))}")
        except Exception as e:
            click.echo(click.style(f"\n✗ 备份失败: {e}", fg='red', bold=True))
    
    def start_recovery_assistant(self) -> None:
        """启动恢复操作助手"""
        click.clear()
        click.echo(click.style("=== MySQL 恢复助手 ===", fg='green', bold=True))
        click.echo("此助手将引导您完成MySQL数据库的恢复操作。\n")
        
        # 选择恢复类型
        recovery_type = click.prompt(
            "请选择恢复类型",
            type=click.Choice(['full', 'incremental', 'point-in-time', 'binlog']),
            default='full'
        )
        
        if recovery_type == 'full':
            self._handle_full_recovery()
        elif recovery_type == 'incremental':
            self._handle_incremental_recovery()
        elif recovery_type == 'point-in-time':
            self._handle_point_in_time_recovery()
        elif recovery_type == 'binlog':
            self._handle_binlog_recovery()
    
    def _handle_full_recovery(self) -> None:
        """处理全量恢复操作"""
        click.echo("\n=== 全量恢复 ===")
        
        # 获取可用的全量备份列表
        available_backups = self._get_available_backups(full_only=True)
        
        if not available_backups:
            click.echo(click.style("没有找到可用的全量备份", fg='yellow'))
            return
        
        # 显示可用备份
        self._display_available_backups(available_backups)
        
        # 选择全量备份
        selected_index = click.prompt(
            "请选择要恢复的全量备份（输入编号）",
            type=int,
            default=1
        )
        
        if selected_index < 1 or selected_index > len(available_backups):
            click.echo(click.style("无效的选择", fg='red'))
            return
        
        backup_path = available_backups[selected_index - 1][2]
        
        # 是否备份现有数据
        backup_existing = click.confirm("是否在恢复前备份现有数据？", default=True)
        
        # 询问是否需要指定数据库和表
        use_specific_tables = click.confirm("是否需要只恢复特定数据库的特定表？", default=False)
        
        tables = None
        if use_specific_tables:
            # 首先选择数据库
            database = click.prompt("请输入要恢复的数据库名称")
            
            # 然后选择表
            tables_input = click.prompt(
                "请输入要恢复的表名(多个表用逗号分隔，输入'*'表示恢复该数据库的所有表)",
                default='*'
            )
            
            if tables_input == '*':
                tables = [f"{database}.*"]
            else:
                tables = [f"{database}.{table.strip()}" for table in tables_input.split(',')]
        
        # 最终确认
        if not click.confirm(
            click.style("警告: 此操作将覆盖现有数据。确定要继续吗？", fg='yellow', bold=True),
            default=False
        ):
            click.echo("操作已取消")
            return
        
        try:
            click.echo("开始执行全量恢复...")
            self.recovery_manager.restore_full_backup(backup_path, backup_existing=backup_existing, specific_tables=tables)
            
            click.echo(click.style("\n✓ 全量恢复完成！", fg='green', bold=True))
        except Exception as e:
            click.echo(click.style(f"\n✗ 恢复失败: {e}", fg='red', bold=True))
    
    def _handle_incremental_recovery(self) -> None:
        """处理增量恢复操作"""
        click.echo("\n=== 增量恢复 ===")
        
        # 获取可用的全量备份列表
        full_backups = self._get_available_backups(full_only=True)
        
        if not full_backups:
            click.echo(click.style("没有找到可用的全量备份", fg='yellow'))
            return
        
        # 显示可用的全量备份
        click.echo("可用的全量备份:")
        self._display_available_backups(full_backups)
        
        # 选择全量备份
        selected_index = click.prompt(
            "请选择要作为基础的全量备份（输入编号）",
            type=int,
            default=1
        )
        
        if selected_index < 1 or selected_index > len(full_backups):
            click.echo(click.style("无效的选择", fg='red'))
            return
        
        full_backup_path = full_backups[selected_index - 1][2]
        
        # 获取可用的增量备份列表
        incremental_backups = self._get_incremental_backups(full_backup_path)
        
        if not incremental_backups:
            click.echo(click.style(f"没有找到与所选全量备份相关的增量备份", fg='yellow'))
            return
        
        # 显示可用的增量备份
        click.echo("\n可用的增量备份:")
        for i, (backup_time, path) in enumerate(incremental_backups, 1):
            click.echo(f"  {i}. {backup_time} - {path}")
        
        # 选择要应用的增量备份
        selected_indices = click.prompt(
            "请选择要应用的增量备份编号（多个用逗号分隔，按时间顺序）",
            default="1"
        )
        
        try:
            selected_indices = [int(idx.strip()) for idx in selected_indices.split(',')]
            incremental_paths = []
            
            for idx in selected_indices:
                if idx < 1 or idx > len(incremental_backups):
                    click.echo(click.style(f"无效的选择: {idx}", fg='red'))
                    return
                incremental_paths.append(incremental_backups[idx - 1][1])
            
            # 是否备份现有数据
            backup_existing = click.confirm("是否在恢复前备份现有数据？", default=True)
            
            # 询问是否需要指定数据库和表
            use_specific_tables = click.confirm("是否需要只恢复特定数据库的特定表？", default=False)
            
            tables = None
            if use_specific_tables:
                # 首先选择数据库
                database = click.prompt("请输入要恢复的数据库名称")
                
                # 然后选择表
                tables_input = click.prompt(
                    "请输入要恢复的表名(多个表用逗号分隔，输入'*'表示恢复该数据库的所有表)",
                    default='*'
                )
                
                if tables_input == '*':
                    tables = [f"{database}.*"]
                else:
                    tables = [f"{database}.{table.strip()}" for table in tables_input.split(',')]
            
            # 最终确认
            if not click.confirm(
                click.style("警告: 此操作将覆盖现有数据。确定要继续吗？", fg='yellow', bold=True),
                default=False
            ):
                click.echo("操作已取消")
                return
            
            # 执行恢复操作
            click.echo("开始执行增量恢复...")
            self.recovery_manager.restore_incremental_backup(
                full_backup_path,
                incremental_paths,
                backup_existing=backup_existing,
                specific_tables=tables
            )
            
            click.echo(click.style("\n✓ 增量恢复完成！", fg='green', bold=True))
        except ValueError as e:
            click.echo(click.style(f"请输入有效的编号列表: {e}", fg='red'))
            return
        except Exception as e:
            click.echo(click.style(f"\n✗ 恢复失败: {e}", fg='red', bold=True))
    
    def _handle_point_in_time_recovery(self) -> None:
        """处理时间点恢复操作"""
        click.echo("\n=== 时间点恢复 ===")
        
        # 获取时间范围
        start_time_str = click.prompt(
            "请输入恢复的起始时间点 (格式: YYYY-MM-DD HH:MM:SS)",
            default=datetime.datetime.now().strftime("%Y-%m-%d 00:00:00")
        )
        
        end_time_str = click.prompt(
            "请输入恢复的结束时间点 (格式: YYYY-MM-DD HH:MM:SS)",
            default=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        try:
            start_time = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
            end_time = datetime.datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
            
            if end_time <= start_time:
                click.echo(click.style("结束时间必须晚于起始时间", fg='red'))
                return
            
            # 是否备份现有数据
            backup_existing = click.confirm("是否在恢复前备份现有数据？", default=True)
            
            # 询问是否需要指定数据库和表
            use_specific_tables = click.confirm("是否需要只恢复特定数据库的特定表？", default=False)
            
            tables = None
            if use_specific_tables:
                # 首先选择数据库
                database = click.prompt("请输入要恢复的数据库名称")
                
                # 然后选择表
                tables_input = click.prompt(
                    "请输入要恢复的表名(多个表用逗号分隔，输入'*'表示恢复该数据库的所有表)",
                    default='*'
                )
                
                if tables_input == '*':
                    tables = [f"{database}.*"]
                else:
                    tables = [f"{database}.{table.strip()}" for table in tables_input.split(',')]
            
            # 最终确认
            if not click.confirm(
                click.style("警告: 此操作将覆盖现有数据。确定要继续吗？", fg='yellow', bold=True),
                default=False
            ):
                click.echo("操作已取消")
                return
            
            # 执行恢复操作
            click.echo("开始执行时间点恢复...")
            self.recovery_manager.restore_to_point_in_time(
                start_time,
                end_time,
                backup_existing=backup_existing,
                specific_tables=tables
            )
            
            click.echo(click.style("\n✓ 时间点恢复完成！", fg='green', bold=True))
        except ValueError as e:
            click.echo(click.style(f"日期格式无效: {e}", fg='red'))
        except Exception as e:
            click.echo(click.style(f"\n✗ 恢复失败: {e}", fg='red', bold=True))
    
    def _handle_binlog_recovery(self) -> None:
        """处理二进制日志恢复操作"""
        click.echo("\n=== 二进制日志恢复 ===")
        
        # 获取可用的二进制日志备份
        binlog_backups = self._get_available_backups(binlog_only=True)
        
        if not binlog_backups:
            click.echo(click.style("没有找到可用的二进制日志备份", fg='yellow'))
            return
        
        # 显示可用的二进制日志备份
        click.echo("可用的二进制日志备份:")
        self._display_available_backups(binlog_backups)
        
        # 选择要恢复的二进制日志备份
        selected_indices = click.prompt(
            "请选择要应用的二进制日志备份编号（多个用逗号分隔，按时间顺序）",
            default="1"
        )
        
        try:
            selected_indices = [int(idx.strip()) for idx in selected_indices.split(',')]
            binlog_paths = []
            
            for idx in selected_indices:
                if idx < 1 or idx > len(binlog_backups):
                    click.echo(click.style(f"无效的选择: {idx}", fg='red'))
                    return
                binlog_paths.append(binlog_backups[idx - 1][2])
            
            # 获取时间范围
            use_time_range = click.confirm("是否需要指定时间范围？", default=True)
            
            start_time = None
            end_time = None
            if use_time_range:
                start_time_str = click.prompt(
                    "请输入恢复的起始时间点 (格式: YYYY-MM-DD HH:MM:SS)",
                    default=datetime.datetime.now().strftime("%Y-%m-%d 00:00:00")
                )
                
                end_time_str = click.prompt(
                    "请输入恢复的结束时间点 (格式: YYYY-MM-DD HH:MM:SS)",
                    default=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                
                start_time = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
                end_time = datetime.datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
                
                if end_time <= start_time:
                    click.echo(click.style("结束时间必须晚于起始时间", fg='red'))
                    return
            
            # 询问是否需要指定数据库和表
            use_specific_tables = click.confirm("是否需要只恢复特定数据库的特定表？", default=False)
            
            tables = None
            if use_specific_tables:
                # 首先选择数据库
                database = click.prompt("请输入要恢复的数据库名称")
                
                # 然后选择表
                tables_input = click.prompt(
                    "请输入要恢复的表名(多个表用逗号分隔，输入'*'表示恢复该数据库的所有表)",
                    default='*'
                )
                
                if tables_input == '*':
                    tables = [f"{database}.*"]
                else:
                    tables = [f"{database}.{table.strip()}" for table in tables_input.split(',')]
            
            # 最终确认
            if not click.confirm(
                click.style("警告: 此操作可能会修改现有数据。确定要继续吗？", fg='yellow', bold=True),
                default=False
            ):
                click.echo("操作已取消")
                return
            
            # 执行恢复操作
            click.echo("开始应用二进制日志...")
            self.recovery_manager.apply_binlog(
                binlog_paths,
                start_time=start_time,
                end_time=end_time,
                tables=tables
            )
            
            click.echo(click.style("\n✓ 二进制日志应用完成！", fg='green', bold=True))
        except ValueError as e:
            click.echo(click.style(f"输入无效: {e}", fg='red'))
        except Exception as e:
            click.echo(click.style(f"\n✗ 恢复失败: {e}", fg='red', bold=True))
    
    def _get_available_backups(self, full_only: bool = False, binlog_only: bool = False) -> List[Tuple[str, str, str, str, int]]:
        """
        获取可用的备份列表
        
        Args:
            full_only: 是否只获取全量备份
            binlog_only: 是否只获取二进制日志备份
            
        Returns:
            备份列表，每项包含(类型, 名称, 路径, 创建时间, 大小)
        """
        backup_dir = self.backup_manager.backup_dir
        
        if not os.path.exists(backup_dir):
            return []
        
        # 获取所有备份目录
        backups = []
        for item in os.listdir(backup_dir):
            full_path = os.path.join(backup_dir, item)
            if os.path.isdir(full_path):
                # 根据过滤条件筛选备份类型
                if full_only and not item.startswith('full_'):
                    continue
                if binlog_only and not item.startswith('binlog_'):
                    continue
                
                if item.startswith(('full_', 'binlog_', 'pre_restore_backup_')):
                    # 获取备份类型
                    backup_type = '全量备份' if item.startswith('full_') else \
                                '二进制日志备份' if item.startswith('binlog_') else \
                                '恢复前备份'
                    
                    # 获取创建时间
                    ctime = os.path.getctime(full_path)
                    creation_time = datetime.datetime.fromtimestamp(ctime).strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 获取大小
                    size = get_directory_size(full_path)
                    
                    backups.append((backup_type, item, full_path, creation_time, size))
        
        # 按创建时间排序（最新的在前）
        backups.sort(key=lambda x: x[3], reverse=True)
        
        return backups
    
    def _get_incremental_backups(self, full_backup_path: str) -> List[Tuple[str, str]]:
        """
        获取与指定全量备份相关的增量备份
        
        Args:
            full_backup_path: 全量备份路径
            
        Returns:
            增量备份列表，每项包含(创建时间, 路径)
        """
        incremental_dir = os.path.join(full_backup_path, 'inc')
        
        if not os.path.exists(incremental_dir):
            return []
        
        result = []
        for item in os.listdir(incremental_dir):
            if item.startswith('inc_'):
                full_path = os.path.join(incremental_dir, item)
                if os.path.isdir(full_path):
                    # 获取创建时间
                    ctime = os.path.getctime(full_path)
                    creation_time = datetime.datetime.fromtimestamp(ctime).strftime('%Y-%m-%d %H:%M:%S')
                    
                    result.append((creation_time, full_path))
        
        # 按创建时间排序（最早的在前）
        result.sort(key=lambda x: x[0])
        
        return result
    
    def _display_available_backups(self, backups: List[Tuple[str, str, str, str, int]]) -> None:
        """
        显示可用的备份列表
        
        Args:
            backups: 备份列表，每项包含(类型, 名称, 路径, 创建时间, 大小)
        """
        if not backups:
            click.echo("没有找到可用的备份")
            return
        
        click.echo("可用的备份:")
        for i, (backup_type, name, path, creation_time, size) in enumerate(backups, 1):
            click.echo(f"  {i}. {backup_type}: {name}")
            click.echo(f"     创建时间: {creation_time}")
            click.echo(f"     路径: {path}")
            click.echo(f"     大小: {format_size(size)}") 