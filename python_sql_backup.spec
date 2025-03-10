"""
PyInstaller spec file for python_sql_backup.

This enhanced spec file supports cross-platform building for Windows, macOS, and Linux
with various CPU architectures.
"""
import os
import sys
import platform
import subprocess
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Determine the current platform
current_platform = platform.system().lower()
if current_platform == 'darwin':
    current_platform = 'macos'
elif current_platform == 'windows':
    current_platform = 'windows'
else:
    current_platform = 'linux'

# Block cipher for encryption (None = no encryption)
block_cipher = None

# Define additional binary dependencies based on platform
binaries = []

# Add Python shared library for Linux
if current_platform == 'linux':
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    
    # Try to find Python library using ldconfig
    try:
        ldconfig_output = subprocess.check_output(['ldconfig', '-p']).decode()
        for line in ldconfig_output.splitlines():
            if f'libpython{python_version}.so' in line:
                lib_path = line.split('=>')[-1].strip()
                if os.path.exists(lib_path):
                    binaries.append((lib_path, '.'))
                    break
    except:
        pass
    
    # If ldconfig didn't work, try common locations
    if not binaries:
        lib_paths = [
            f"/usr/lib/libpython{python_version}.so",
            f"/usr/lib/aarch64-linux-gnu/libpython{python_version}.so",
            f"/usr/lib/python{python_version}/config-{python_version}-aarch64-linux-gnu/libpython{python_version}.so",
            f"/usr/lib/x86_64-linux-gnu/libpython{python_version}.so",
            f"/usr/local/lib/libpython{python_version}.so",
            os.path.join(sys.prefix, 'lib', f'libpython{python_version}.so'),
        ]
        
        # Add current Python's lib directory
        python_lib_dir = os.path.dirname(os.path.realpath(sys.executable))
        lib_paths.append(os.path.join(python_lib_dir, '..', 'lib', f'libpython{python_version}.so'))
        
        for lib_path in lib_paths:
            if os.path.exists(lib_path):
                binaries.append((lib_path, '.'))
                break

# Define data files to include
data_files = [
    ('config.ini.example', 'config.ini.example'),
    ('README.md', 'README.md'),
]

# Add icons if they exist
icon_paths = {
    'windows': os.path.join('resources', 'icon.ico'),
    'macos': os.path.join('resources', 'icon.icns'),
}

for platform_name, icon_path in icon_paths.items():
    if os.path.exists(icon_path):
        data_files.append((icon_path, icon_path))

# Hidden imports to ensure all necessary modules are included
hidden_imports = [
    'mysql.connector',
    'configparser',
    'click',
    'tabulate',
    'colorama',
    'tqdm',
    'typing',
    'pathlib',
]

# Add all submodules from our package
hidden_imports.extend(collect_submodules('python_sql_backup'))

# Create the Analysis object
a = Analysis(
    ['python_sql_backup/__main__.py'],
    pathex=[os.path.abspath(os.getcwd())],
    binaries=binaries,
    datas=data_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Create the PYZ archive
pyz = PYZ(
    a.pure, 
    a.zipped_data,
    cipher=block_cipher
)

# Platform-specific options for the executable
exe_args = {
    'name': 'python-sql-backup',
    'debug': False,
    'bootloader_ignore_signals': False,
    'strip': False,
    'upx': True,
    'console': True,
}

# Add platform-specific icon if available
if current_platform == 'windows' and os.path.exists(icon_paths['windows']):
    exe_args['icon'] = icon_paths['windows']
elif current_platform == 'macos' and os.path.exists(icon_paths['macos']):
    exe_args['icon'] = icon_paths['macos']

# Create mode-specific targets based on the build mode
# Onefile mode: Single executable file
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    **exe_args,
)

# For macOS, create a .app bundle
if current_platform == 'macos':
    app = BUNDLE(
        exe,
        name='python-sql-backup.app',
        icon=icon_paths['macos'] if os.path.exists(icon_paths['macos']) else None,
        bundle_identifier='com.mysql.backup',
        info_plist={
            'CFBundleShortVersionString': '1.0.0',
            'NSHighResolutionCapable': 'True',
        },
    )
