#!/usr/bin/env python3
"""
交互式构建指南脚本 - MySQL备份工具

该脚本提供了一个交互式界面，引导用户完成MySQL备份工具可执行文件的构建过程。
它简化了构建参数的选择，并提供了对构建过程的实时反馈。
"""

import os
import sys
import platform
import subprocess
import time
from typing import List, Dict, Optional, Tuple

# 定义颜色代码（用于终端彩色输出）
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def clear_screen():
    """清除终端屏幕"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """打印指南标题"""
    clear_screen()
    print(f"{Colors.HEADER}{Colors.BOLD}MySQL备份工具 - 构建助手{Colors.ENDC}")
    print(f"{Colors.BOLD}{'=' * 50}{Colors.ENDC}")
    print("该助手将引导您完成MySQL备份工具可执行文件的构建过程。\n")


def print_step(step_num: int, total_steps: int, title: str):
    """打印步骤标题"""
    print(f"{Colors.BLUE}{Colors.BOLD}步骤 {step_num}/{total_steps}: {title}{Colors.ENDC}")
    print(f"{Colors.BLUE}{'-' * 50}{Colors.ENDC}")


def get_user_choice(prompt: str, options: List[str], allow_custom: bool = False) -> str:
    """
    获取用户选择
    
    Args:
        prompt: 提示信息
        options: 选项列表
        allow_custom: 是否允许自定义输入
        
    Returns:
        用户选择
    """
    while True:
        print(f"\n{prompt}")
        
        for i, option in enumerate(options, 1):
            print(f"  {i}. {option}")
            
        if allow_custom:
            print(f"  c. 自定义输入")
            
        choice = input("\n请输入您的选择 [1-{0}{1}]: ".format(
            len(options), ", c" if allow_custom else ""
        )).strip().lower()
        
        if choice == 'c' and allow_custom:
            custom_value = input("请输入自定义值: ").strip()
            return custom_value
            
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(options):
                return options[choice_idx]
        except ValueError:
            pass
            
        print(f"{Colors.RED}无效选择，请重试。{Colors.ENDC}")


def check_dependencies() -> bool:
    """
    检查是否已安装所有必要的依赖项
    
    Returns:
        如果所有依赖项都已安装则返回True，否则返回False
    """
    print(f"\n{Colors.BOLD}检查依赖项...{Colors.ENDC}")
    
    # 检查PyInstaller
    try:
        subprocess.run(
            [sys.executable, '-m', 'PyInstaller', '--version'],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(f"{Colors.GREEN}✓ PyInstaller 已安装{Colors.ENDC}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"{Colors.RED}✗ PyInstaller 未安装{Colors.ENDC}")
        install = input("是否要安装 PyInstaller? (y/n): ").strip().lower()
        if install == 'y':
            try:
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', 'pyinstaller'],
                    check=True
                )
                print(f"{Colors.GREEN}✓ PyInstaller 已安装{Colors.ENDC}")
            except subprocess.CalledProcessError:
                print(f"{Colors.RED}安装 PyInstaller 失败{Colors.ENDC}")
                return False
        else:
            return False
    
    # 检查其他依赖项
    requirements_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'requirements.txt')
    if os.path.exists(requirements_file):
        print(f"\n{Colors.BOLD}检查项目依赖项...{Colors.ENDC}")
        try:
            subprocess.run(
                [sys.executable, '-m', 'pip', 'check'],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print(f"{Colors.GREEN}✓ 所有依赖项已安装{Colors.ENDC}")
        except subprocess.CalledProcessError:
            print(f"{Colors.YELLOW}⚠ 一些依赖项可能缺失或存在冲突{Colors.ENDC}")
            install = input("是否要安装项目依赖项? (y/n): ").strip().lower()
            if install == 'y':
                try:
                    subprocess.run(
                        [sys.executable, '-m', 'pip', 'install', '-r', requirements_file],
                        check=True
                    )
                    print(f"{Colors.GREEN}✓ 所有依赖项已安装{Colors.ENDC}")
                except subprocess.CalledProcessError:
                    print(f"{Colors.RED}安装依赖项失败{Colors.ENDC}")
                    return False
    
    return True


def select_platform() -> str:
    """
    选择目标平台
    
    Returns:
        所选平台
    """
    current_platform = platform.system().lower()
    if current_platform == 'darwin':
        current_platform = 'macOS'
    elif current_platform == 'windows':
        current_platform = 'Windows'
    else:
        current_platform = 'Linux'
        
    platforms = ['Windows', 'macOS', 'Linux', '所有平台']
    prompt = f"选择目标平台 (当前系统: {current_platform}):"
    choice = get_user_choice(prompt, platforms)
    
    if choice == '所有平台':
        return 'all'
    return choice.lower()


def select_architecture(platform_choice: str) -> str:
    """
    选择目标架构
    
    Args:
        platform_choice: 所选平台
        
    Returns:
        所选架构
    """
    if platform_choice == 'all':
        return 'all'
        
    current_arch = platform.machine().lower()
    if current_arch in ['i386', 'i686']:
        current_arch = 'x86'
    elif current_arch in ['x86_64', 'amd64']:
        current_arch = 'x86_64'
    elif current_arch in ['arm64', 'aarch64']:
        current_arch = 'arm64'
    else:
        current_arch = 'x86_64'  # 默认值
        
    arch_options = {
        'windows': ['x86', 'x86_64', 'arm64', '所有架构'],
        'macos': ['x86_64', 'arm64', '所有架构'],
        'linux': ['x86', 'x86_64', 'arm64', '所有架构']
    }
    
    options = arch_options.get(platform_choice, ['x86_64', 'arm64', '所有架构'])
    prompt = f"选择目标架构 (当前架构: {current_arch}):"
    choice = get_user_choice(prompt, options)
    
    if choice == '所有架构':
        return 'all'
    return choice


def select_output_directory() -> str:
    """
    选择输出目录
    
    Returns:
        输出目录路径
    """
    default_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist')
    prompt = f"选择输出目录 (默认: {default_dir}):"
    options = [default_dir, '当前目录', '用户主目录']
    choice = get_user_choice(prompt, options, allow_custom=True)
    
    if choice == '当前目录':
        return os.getcwd()
    elif choice == '用户主目录':
        return os.path.expanduser('~')
    else:
        return choice


def select_build_options() -> Dict[str, bool]:
    """
    选择构建选项
    
    Returns:
        构建选项字典
    """
    options = {
        'clean': False,
        'verbose': False
    }
    
    print(f"\n{Colors.BOLD}附加构建选项:{Colors.ENDC}")
    
    # 清理选项
    clean = input("是否在构建前清理构建目录? (y/n, 默认: n): ").strip().lower()
    options['clean'] = clean == 'y'
    
    # 详细输出选项
    verbose = input("是否启用详细输出? (y/n, 默认: n): ").strip().lower()
    options['verbose'] = verbose == 'y'
    
    return options


def run_build(
    platform_choice: str,
    arch_choice: str,
    output_dir: str,
    options: Dict[str, bool]
) -> bool:
    """
    运行构建过程
    
    Args:
        platform_choice: 目标平台
        arch_choice: 目标架构
        output_dir: 输出目录
        options: 构建选项
        
    Returns:
        如果构建成功则返回True，否则返回False
    """
    print(f"\n{Colors.BOLD}准备构建...{Colors.ENDC}")
    
    # 构建命令
    cmd = [sys.executable, 'build_executable.py']
    
    if platform_choice != 'all':
        cmd.extend(['--target-platform', platform_choice])
    else:
        cmd.append('--all')
        
    if arch_choice != 'all' and platform_choice != 'all':
        cmd.extend(['--target-arch', arch_choice])
        
    cmd.extend(['--output-dir', output_dir])
    
    if options['clean']:
        cmd.append('--clean')
        
    if options['verbose']:
        cmd.append('--verbose')
    
    # 显示命令
    print(f"{Colors.BOLD}执行命令:{Colors.ENDC}")
    print(f"  {' '.join(cmd)}")
    
    # 确认
    print(f"\n{Colors.YELLOW}注意: 构建过程可能需要几分钟时间。{Colors.ENDC}")
    confirm = input("是否继续? (y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消构建。")
        return False
    
    print(f"\n{Colors.BOLD}开始构建...{Colors.ENDC}")
    
    try:
        # 运行构建脚本
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # 实时显示输出
        for line in iter(process.stdout.readline, ''):
            print(line, end='')
            sys.stdout.flush()
        
        process.wait()
        
        if process.returncode == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}构建成功!{Colors.ENDC}")
            return True
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}构建失败!{Colors.ENDC}")
            return False
            
    except Exception as e:
        print(f"\n{Colors.RED}{Colors.BOLD}构建过程中发生错误: {e}{Colors.ENDC}")
        return False


def show_summary(
    platform_choice: str,
    arch_choice: str,
    output_dir: str,
    success: bool
) -> None:
    """
    显示构建摘要
    
    Args:
        platform_choice: 目标平台
        arch_choice: 目标架构
        output_dir: 输出目录
        success: 构建是否成功
    """
    print(f"\n{Colors.BOLD}构建摘要:{Colors.ENDC}")
    print(f"  平台: {platform_choice}")
    print(f"  架构: {arch_choice}")
    print(f"  输出目录: {output_dir}")
    print(f"  状态: {'成功' if success else '失败'}")
    
    if success:
        # 确定输出文件名
        if platform_choice == 'all':
            print(f"\n{Colors.GREEN}所有平台的可执行文件已构建到以下目录:{Colors.ENDC}")
            print(f"  {output_dir}")
        else:
            exe_name = 'python-sql-backup'
            if platform_choice == 'windows':
                exe_name += '.exe'
                
            platform_dir = f"{platform_choice}-{arch_choice}" if arch_choice != 'all' else platform_choice
            print(f"\n{Colors.GREEN}可执行文件已构建到:{Colors.ENDC}")
            print(f"  {os.path.join(output_dir, platform_dir, exe_name)}")
            
        print(f"\n{Colors.GREEN}配置文件可在以下位置找到:{Colors.ENDC}")
        print(f"  {os.path.join(output_dir, 'config')}")
    
    print(f"\n{Colors.BOLD}{'=' * 50}{Colors.ENDC}")


def main() -> int:
    """
    主函数
    
    Returns:
        退出代码 (0=成功, 非0=失败)
    """
    # 打印标题
    print_header()
    
    # 步骤1: 检查依赖项
    print_step(1, 5, "检查依赖项")
    if not check_dependencies():
        print(f"\n{Colors.RED}请安装所需的依赖项后重试。{Colors.ENDC}")
        return 1
    
    # 步骤2: 选择目标平台
    print_step(2, 5, "选择目标平台")
    platform_choice = select_platform()
    
    # 步骤3: 选择目标架构
    print_step(3, 5, "选择目标架构")
    arch_choice = select_architecture(platform_choice)
    
    # 步骤4: 选择输出目录
    print_step(4, 5, "配置构建选项")
    output_dir = select_output_directory()
    build_options = select_build_options()
    
    # 步骤5: 运行构建
    print_step(5, 5, "运行构建")
    success = run_build(platform_choice, arch_choice, output_dir, build_options)
    
    # 显示摘要
    show_summary(platform_choice, arch_choice, output_dir, success)
    
    return 0 if success else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}构建已取消。{Colors.ENDC}")
        sys.exit(1)
