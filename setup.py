"""
Setup script for python_sql_backup package.
"""
from setuptools import setup, find_packages


def read_requirements():
    with open('requirements.txt') as f:
        return f.read().splitlines()


setup(
    name="python_sql_backup",
    version="1.0.0",
    description="MySQL backup and recovery solution using XtraBackup",
    author="Python SQL Backup Team",
    packages=find_packages(),
    install_requires=read_requirements(),
    entry_points={
        'console_scripts': [
            'python-sql-backup=python_sql_backup.cli.commands:cli',
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Topic :: Database",
        "Topic :: System :: Archiving :: Backup",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.10",
)
