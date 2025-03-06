#!/usr/bin/env python3
"""
Cross-platform build script for python_sql_backup.

This script builds standalone executables for Windows, macOS, and Linux
using PyInstaller, supporting various CPU architectures.

Usage:
    python build_executable.py [options]

Options:
    --target-platform PLATFORM   Target platform (windows, macos, linux)
    --target-arch ARCH          Target architecture (x86, x86_64, arm64)
    --all                       Build for all supported platforms and architectures
    --output-dir DIR            Output directory for executables
    --verbose                   Enable verbose output
    --clean                     Clean build directories before building
    --help                      Show this help message
"""

import os
import sys
import shutil
import platform
import subprocess
import argparse
from typing import List, Dict, Optional, Tuple
import logging
from pathlib import Path


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('build_executable')


# Define supported platforms and architectures
SUPPORTED_PLATFORMS = ['windows', 'macos', 'linux']
SUPPORTED_ARCHITECTURES = {
    'windows': ['x86', 'x86_64', 'arm64'],
    'macos': ['x86_64', 'arm64'],
    'linux': ['x86', 'x86_64', 'arm64']
}

# Define platform-specific file extensions
PLATFORM_EXT = {
    'windows': '.exe',
    'macos': '',
    'linux': ''
}

# Define PyInstaller options for each platform
PLATFORM_OPTIONS = {
    'windows': [
        '--windowed',  # For GUI applications only
        '--icon=resources/icon.ico',  # Windows icon (if available)
    ],
    'macos': [
        '--icon=resources/icon.icns',  # macOS icon (if available)
    ],
    'linux': []
}

# Common PyInstaller options
COMMON_OPTIONS = [
    '--onefile',  # Create a single executable
    '--clean',  # Clean PyInstaller cache before building
    '--noconfirm',  # Replace output directory without asking
    '--name', 'python-sql-backup',  # Output executable name
]


def detect_current_platform() -> str:
    """Detect the current platform."""
    system = platform.system().lower()
    if system == 'darwin':
        return 'macos'
    elif system == 'windows':
        return 'windows'
    else:
        return 'linux'  # Default to Linux for other systems


def detect_current_arch() -> str:
    """Detect the current architecture."""
    machine = platform.machine().lower()
    if machine in ['i386', 'i686']:
        return 'x86'
    elif machine in ['x86_64', 'amd64']:
        return 'x86_64'
    elif machine in ['arm64', 'aarch64']:
        return 'arm64'
    else:
        # Default to x86_64 if unknown
        logger.warning(f"Unknown architecture: {machine}, defaulting to x86_64")
        return 'x86_64'


def ensure_dependencies() -> bool:
    """
    Ensure all required dependencies are installed.
    
    Returns:
        True if all dependencies are installed, False otherwise.
    """
    try:
        # Check PyInstaller
        subprocess.run(
            [sys.executable, '-m', 'PyInstaller', '--version'],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.info("PyInstaller is installed")
        
        # Check if dependencies from requirements.txt are installed
        requirements_file = Path('requirements.txt')
        if requirements_file.exists():
            logger.info("Checking dependencies from requirements.txt")
            try:
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'check'],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                logger.info("All dependencies are satisfied")
            except subprocess.CalledProcessError:
                logger.warning("Some dependencies may be missing or have conflicts")
                logger.info("Installing required dependencies")
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
                    check=True
                )
                logger.info("Dependencies installed successfully")
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error checking dependencies: {e}")
        logger.error("Please install required dependencies:")
        logger.error("  pip install pyinstaller")
        logger.error("  pip install -r requirements.txt")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False


def create_resources() -> None:
    """Create necessary resource files if they don't exist."""
    # Create resources directory
    resources_dir = Path('resources')
    resources_dir.mkdir(exist_ok=True)
    
    # Check for icons and create placeholders if needed
    icon_files = {
        'windows': resources_dir / 'icon.ico',
        'macos': resources_dir / 'icon.icns',
    }
    
    for platform_name, icon_path in icon_files.items():
        if not icon_path.exists():
            logger.warning(f"Icon file for {platform_name} not found: {icon_path}")
            # We could create placeholder icons here, but skipping for now


def clean_build_dirs() -> None:
    """Clean build and dist directories."""
    dirs_to_clean = ['build', 'dist']
    
    for dir_name in dirs_to_clean:
        dir_path = Path(dir_name)
        if dir_path.exists():
            logger.info(f"Cleaning {dir_path}")
            shutil.rmtree(dir_path)


def get_build_command(
    platform_name: str, 
    arch: str, 
    output_dir: str,
    verbose: bool
) -> List[str]:
    """
    Generate the PyInstaller command for the given platform and architecture.
    
    Args:
        platform_name: Target platform name
        arch: Target architecture
        output_dir: Output directory for the executable
        verbose: Whether to enable verbose output
        
    Returns:
        The PyInstaller command as a list of strings
    """
    # Start with the Python executable
    cmd = [sys.executable, '-m', 'PyInstaller']
    
    # Check if spec file exists
    spec_file = Path('python_sql_backup.spec')
    
    # If spec file exists, we shouldn't add options that are defined in the spec file
    if spec_file.exists():
        # When using a spec file, only add the clean and verbosity options if needed
        cmd.append('--noconfirm')  # Always confirm overwrite
        
        if '--clean' in COMMON_OPTIONS:
            cmd.append('--clean')
            
        # Set the output directory
        dist_path = os.path.join(output_dir, f"{platform_name}-{arch}")
        cmd.extend(['--distpath', dist_path])
            
        # Add the spec file
        cmd.append(str(spec_file))
    else:
        # No spec file found, use all common options
        cmd.extend(COMMON_OPTIONS)
        
        # Add platform-specific options
        if platform_name in PLATFORM_OPTIONS:
            for opt in PLATFORM_OPTIONS[platform_name]:
                # Skip icon options if the file doesn't exist
                if opt.startswith('--icon='):
                    icon_path = opt.split('=')[1]
                    if not os.path.exists(icon_path):
                        continue
                cmd.append(opt)
        
        # Set the output directory
        dist_path = os.path.join(output_dir, f"{platform_name}-{arch}")
        cmd.extend(['--distpath', dist_path])
        
        # Add the main script
        logger.warning("Spec file not found, using main module")
        cmd.append('python_sql_backup/__main__.py')
    
    # Add verbose flag if requested
    if verbose:
        cmd.append('--verbose')
        
    return cmd


def build_for_platform(
    platform_name: str, 
    arch: str, 
    output_dir: str,
    verbose: bool
) -> bool:
    """
    Build the executable for the specified platform and architecture.
    
    Args:
        platform_name: Target platform name
        arch: Target architecture
        output_dir: Output directory for the executable
        verbose: Whether to enable verbose output
        
    Returns:
        True if the build was successful, False otherwise
    """
    logger.info(f"Building for {platform_name} ({arch})")
    
    # Create output directory
    dist_path = os.path.join(output_dir, f"{platform_name}-{arch}")
    os.makedirs(dist_path, exist_ok=True)
    
    # Get the build command
    cmd = get_build_command(platform_name, arch, output_dir, verbose)
    
    if verbose:
        logger.info(f"Build command: {' '.join(cmd)}")
    
    # Set environment variables for cross-platform building
    env = os.environ.copy()
    
    # Platform-specific environment variables
    if platform_name == 'windows':
        env['PYTHONPATH'] = os.pathsep.join([env.get('PYTHONPATH', ''), '.'])
    elif platform_name == 'macos':
        env['PYTHONPATH'] = os.pathsep.join([env.get('PYTHONPATH', ''), '.'])
        if arch == 'arm64':
            env['ARCHFLAGS'] = '-arch arm64'
        else:
            env['ARCHFLAGS'] = '-arch x86_64'
    elif platform_name == 'linux':
        env['PYTHONPATH'] = os.pathsep.join([env.get('PYTHONPATH', ''), '.'])
    
    try:
        # Run the PyInstaller command
        subprocess.run(cmd, check=True, env=env)
        
        # Rename the executable if needed
        executable_name = 'python-sql-backup'
        if platform_name == 'windows':
            executable_name += '.exe'
        
        logger.info(f"Build successful for {platform_name} ({arch})")
        logger.info(f"Executable: {os.path.join(dist_path, executable_name)}")
        
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Build failed for {platform_name} ({arch}): {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during build for {platform_name} ({arch}): {e}")
        return False


def create_config_bundle(output_dir: str) -> None:
    """
    Create a bundle with configuration and documentation files.
    
    Args:
        output_dir: Output directory for the bundles
    """
    logger.info("Creating configuration bundles")
    
    # Files to include in the bundle
    files_to_bundle = [
        'config.ini.example',
        'README.md',
        'LICENSE',  # If available
    ]
    
    # Create a directory for the bundle
    bundle_dir = os.path.join(output_dir, 'config')
    os.makedirs(bundle_dir, exist_ok=True)
    
    # Copy files to the bundle directory
    for file_name in files_to_bundle:
        if os.path.exists(file_name):
            shutil.copy2(file_name, bundle_dir)
            logger.info(f"Added {file_name} to bundle")
        else:
            logger.warning(f"File not found: {file_name}")
    
    logger.info(f"Configuration bundle created at {bundle_dir}")


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Build standalone executables for Python SQL Backup"
    )
    
    parser.add_argument(
        '--target-platform',
        choices=SUPPORTED_PLATFORMS,
        help="Target platform (windows, macos, linux)"
    )
    
    parser.add_argument(
        '--target-arch',
        help="Target architecture (x86, x86_64, arm64)"
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help="Build for all supported platforms and architectures"
    )
    
    parser.add_argument(
        '--output-dir',
        default='dist',
        help="Output directory for executables (default: dist)"
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help="Enable verbose output"
    )
    
    parser.add_argument(
        '--clean',
        action='store_true',
        help="Clean build directories before building"
    )
    
    return parser.parse_args()


def main() -> int:
    """Main function."""
    args = parse_arguments()
    
    # Print information about the current system
    current_platform = detect_current_platform()
    current_arch = detect_current_arch()
    logger.info(f"Current platform: {current_platform}")
    logger.info(f"Current architecture: {current_arch}")
    
    # Clean build directories if requested
    if args.clean:
        clean_build_dirs()
    
    # Ensure dependencies are installed
    if not ensure_dependencies():
        return 1
    
    # Create necessary resource files
    create_resources()
    
    # Determine target platforms and architectures
    build_targets = []
    
    if args.all:
        # Build for all supported platforms and architectures
        for platform_name in SUPPORTED_PLATFORMS:
            for arch in SUPPORTED_ARCHITECTURES[platform_name]:
                build_targets.append((platform_name, arch))
    elif args.target_platform:
        # Build for the specified platform
        if args.target_platform not in SUPPORTED_PLATFORMS:
            logger.error(f"Unsupported platform: {args.target_platform}")
            return 1
        
        if args.target_arch:
            # Build for the specified architecture
            if args.target_arch not in SUPPORTED_ARCHITECTURES[args.target_platform]:
                logger.error(f"Unsupported architecture for {args.target_platform}: {args.target_arch}")
                return 1
            
            build_targets.append((args.target_platform, args.target_arch))
        else:
            # Build for all supported architectures of the platform
            for arch in SUPPORTED_ARCHITECTURES[args.target_platform]:
                build_targets.append((args.target_platform, arch))
    else:
        # Build for the current platform and architecture
        build_targets.append((current_platform, current_arch))
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Build for each target
    build_results = []
    for platform_name, arch in build_targets:
        success = build_for_platform(platform_name, arch, args.output_dir, args.verbose)
        build_results.append((platform_name, arch, success))
    
    # Create configuration bundle
    create_config_bundle(args.output_dir)
    
    # Print build results
    logger.info("\nBuild Results:")
    all_success = True
    for platform_name, arch, success in build_results:
        status = "Success" if success else "Failed"
        logger.info(f"{platform_name} ({arch}): {status}")
        if not success:
            all_success = False
    
    if all_success:
        logger.info("\nAll builds completed successfully")
        return 0
    else:
        logger.error("\nSome builds failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
