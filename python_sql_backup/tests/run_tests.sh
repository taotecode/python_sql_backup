#!/bin/bash

# 确保脚本在错误时退出
set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 错误处理函数
cleanup() {
    echo -e "${YELLOW}清理测试环境...${NC}"
    docker-compose down -v 2>/dev/null || true
}

# 设置错误处理
trap cleanup EXIT

# 打印信息函数
info() {
    echo -e "${GREEN}$1${NC}"
}

error() {
    echo -e "${RED}错误: $1${NC}"
    exit 1
}

# 创建必要的目录
info "创建必要的目录..."
mkdir -p config scripts

# 检查必要的命令
info "检查环境依赖..."
for cmd in docker-compose python3 pytest; do
    if ! command -v $cmd &> /dev/null; then
        error "未找到命令: $cmd"
    fi
done

# 检查必要的Python包
info "检查Python依赖..."
python3 -c "import pytest" 2>/dev/null || error "未安装pytest包，请运行: pip install pytest"
python3 -c "import mysql.connector" 2>/dev/null || error "未安装mysql-connector-python包，请运行: pip install mysql-connector-python"

# 停止并删除现有容器和卷
info "清理现有环境..."
docker-compose down -v 2>/dev/null || true

# 启动Docker容器
info "启动测试环境..."
docker-compose up -d

# 等待MySQL准备就绪
info "等待MySQL准备就绪..."
for i in {1..30}; do
    if docker exec mysql_test mysqladmin ping -h localhost -u root -prootpassword &>/dev/null; then
        info "MySQL已就绪"
        break
    fi
    if [ $i -eq 30 ]; then
        error "MySQL启动超时"
    fi
    echo -n "."
    sleep 1
done

# 确保备份目录存在且有正确的权限
info "检查备份目录权限..."
docker exec xtrabackup_test mkdir -p /backup
docker exec xtrabackup_test chown -R 999:999 /backup

# 运行测试
info "运行测试..."
PYTHONPATH=.. pytest test_backup.py test_recovery.py -v

info "测试完成" 