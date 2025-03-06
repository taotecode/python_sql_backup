"""
Main entry point for MySQL backup and recovery tool.
"""
import sys
from python_sql_backup.cli.commands import cli
from python_sql_backup.cli.interactive import InteractiveAssistant
from python_sql_backup.config.config_manager import ConfigManager

def main():
    """
    Main entry point function.
    """
    # 检查是否有命令行参数
    if len(sys.argv) > 1:
        # 如果有参数，使用命令行接口
        cli()
    else:
        # 如果没有参数，启动交互式助手
        print("启动交互式助手...")
        config_manager = ConfigManager()
        assistant = InteractiveAssistant(config_manager)
        
        # 选择操作类型
        operation_type = input("请选择操作类型 [backup/restore] (默认: backup): ").strip().lower()
        if not operation_type or operation_type == 'backup':
            assistant.start_backup_assistant()
        else:
            assistant.start_recovery_assistant()

if __name__ == '__main__':
    main()
