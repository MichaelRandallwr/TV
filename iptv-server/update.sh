#!/bin/bash

# IPTV 源更新脚本
# 供 crontab 定时调用

set -e

# 脚本目录
SCRIPT_DIR="/opt/iptv-server"
LOG_FILE="$SCRIPT_DIR/logs/update.log"

# 记录日志
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 切换到脚本目录
cd "$SCRIPT_DIR"

log "========================================"
log "开始更新 IPTV 源"
log "========================================"

# 执行更新
if python3 iptv_manager.py update; then
    log "更新成功"
else
    log "更新失败"
    exit 1
fi

log "========================================"
log "更新完成"
log "========================================"
