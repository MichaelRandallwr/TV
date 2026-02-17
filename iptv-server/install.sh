#!/bin/bash

# IPTV 源管理服务一键安装脚本
# 适用于 Ubuntu 20.04 / 22.04 / 24.04

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 安装目录
INSTALL_DIR="/opt/iptv-server"

# 打印带颜色的消息
print_message() {
    local color=$1
    shift
    echo -e "${color}$@${NC}"
}

print_info() {
    print_message "$GREEN" "[INFO] $@"
}

print_warn() {
    print_message "$YELLOW" "[WARN] $@"
}

print_error() {
    print_message "$RED" "[ERROR] $@"
}

# 检查是否以 root 权限运行
check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "请使用 root 权限运行此脚本"
        echo "使用方法: sudo bash install.sh"
        exit 1
    fi
}

# 检测系统版本
check_system() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    else
        print_error "无法检测系统版本"
        exit 1
    fi
    
    print_info "检测到系统: $OS $VER"
    
    if [[ ! "$OS" =~ "Ubuntu" ]]; then
        print_warn "此脚本主要适用于 Ubuntu 系统，当前系统可能不兼容"
    fi
}

# 安装依赖
install_dependencies() {
    print_info "开始安装依赖..."
    
    # 更新包列表
    print_info "更新包列表..."
    apt-get update -qq
    
    # 安装 Python3 和 pip
    if ! command -v python3 &> /dev/null; then
        print_info "安装 Python3..."
        apt-get install -y python3
    else
        print_info "Python3 已安装: $(python3 --version)"
    fi
    
    if ! command -v pip3 &> /dev/null; then
        print_info "安装 pip3..."
        apt-get install -y python3-pip
    else
        print_info "pip3 已安装: $(pip3 --version)"
    fi
    
    # 安装 ffmpeg
    if ! command -v ffmpeg &> /dev/null; then
        print_info "安装 ffmpeg..."
        apt-get install -y ffmpeg
    else
        print_info "ffmpeg 已安装: $(ffmpeg -version | head -n 1)"
    fi
    
    # 安装 Python 依赖
    print_info "安装 Python 依赖包..."
    pip3 install requests -q
    
    print_info "依赖安装完成"
}

# 复制文件到安装目录
install_files() {
    print_info "复制文件到 $INSTALL_DIR..."
    
    # 获取脚本所在目录
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # 创建安装目录
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR/output"
    mkdir -p "$INSTALL_DIR/logs"
    
    # 复制文件
    cp "$SCRIPT_DIR/iptv_manager.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/update.sh" "$INSTALL_DIR/"
    
    # 设置执行权限
    chmod +x "$INSTALL_DIR/iptv_manager.py"
    chmod +x "$INSTALL_DIR/update.sh"
    
    print_info "文件复制完成"
}

# 注册 systemd 服务
install_service() {
    print_info "注册 systemd 服务..."
    
    # 获取脚本所在目录
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # 复制服务文件
    cp "$SCRIPT_DIR/iptv.service" /etc/systemd/system/
    
    # 重新加载 systemd
    systemctl daemon-reload
    
    # 启用服务（开机自启）
    systemctl enable iptv.service
    
    print_info "systemd 服务注册完成"
}

# 设置 crontab 定时任务
setup_crontab() {
    print_info "设置 crontab 定时任务（每6小时更新一次）..."
    
    # 添加 crontab 任务（如果不存在）
    CRON_CMD="0 */6 * * * $INSTALL_DIR/update.sh"
    
    # 检查是否已存在
    if crontab -l 2>/dev/null | grep -q "$INSTALL_DIR/update.sh"; then
        print_info "crontab 任务已存在，跳过"
    else
        # 添加到 crontab
        (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
        print_info "crontab 任务添加成功"
    fi
}

# 首次更新源
first_update() {
    print_info "执行首次源抓取和检测..."
    print_info "这可能需要几分钟时间，请耐心等待..."
    
    cd "$INSTALL_DIR"
    
    if python3 iptv_manager.py update; then
        print_info "首次更新完成"
    else
        print_warn "首次更新失败，但服务已安装，可稍后手动运行"
    fi
}

# 启动服务
start_service() {
    print_info "启动 IPTV 服务..."
    
    systemctl start iptv.service
    
    # 等待服务启动
    sleep 2
    
    # 检查服务状态
    if systemctl is-active --quiet iptv.service; then
        print_info "服务启动成功"
    else
        print_error "服务启动失败，请查看日志: journalctl -u iptv.service -n 50"
        exit 1
    fi
}

# 显示访问信息
show_info() {
    # 获取本机 IP
    LOCAL_IP=$(hostname -I | awk '{print $1}')
    
    echo ""
    echo "========================================"
    print_info "安装完成！"
    echo "========================================"
    echo ""
    echo "服务信息："
    echo "  - 服务名称: iptv"
    echo "  - 安装目录: $INSTALL_DIR"
    echo "  - 监听端口: 8080"
    echo ""
    echo "访问地址："
    echo "  - http://localhost:8080/config.json"
    echo "  - http://localhost:8080/live.txt"
    echo "  - http://localhost:8080/live_multi.txt"
    echo ""
    if [ -n "$LOCAL_IP" ]; then
        echo "局域网访问："
        echo "  - http://${LOCAL_IP}:8080/config.json"
        echo "  - http://${LOCAL_IP}:8080/live.txt"
        echo "  - http://${LOCAL_IP}:8080/live_multi.txt"
        echo ""
    fi
    echo "常用命令："
    echo "  - 查看服务状态: systemctl status iptv"
    echo "  - 查看服务日志: journalctl -u iptv -f"
    echo "  - 重启服务: systemctl restart iptv"
    echo "  - 停止服务: systemctl stop iptv"
    echo "  - 手动更新源: $INSTALL_DIR/update.sh"
    echo ""
    echo "定时任务："
    echo "  - 已设置每 6 小时自动更新一次"
    echo "  - 查看定时任务: crontab -l"
    echo ""
    echo "输出文件："
    echo "  - $INSTALL_DIR/output/config.json"
    echo "  - $INSTALL_DIR/output/live.txt"
    echo "  - $INSTALL_DIR/output/live_multi.txt"
    echo ""
    echo "日志文件："
    echo "  - $INSTALL_DIR/logs/service.log"
    echo "  - $INSTALL_DIR/logs/manager.log"
    echo "  - $INSTALL_DIR/logs/update.log"
    echo "========================================"
    echo ""
}

# 主函数
main() {
    echo ""
    echo "========================================"
    echo "  IPTV 源管理服务 - 一键安装脚本"
    echo "========================================"
    echo ""
    
    check_root
    check_system
    
    install_dependencies
    install_files
    install_service
    setup_crontab
    first_update
    start_service
    
    show_info
}

# 运行主函数
main
