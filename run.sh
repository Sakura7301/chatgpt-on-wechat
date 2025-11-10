#!/bin/bash

#============================================
# ChatGPT-on-WeChat 管理脚本
# 用法: ./manage.sh [command] [type]
#============================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 获取脚本所在目录（自动）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR"
LOG_DIR="$APP_DIR/log"

# 默认程序类型
APP_TYPE="${2:-app}"  # 第二个参数，默认为 app

# 根据类型设置程序信息
if [ "$APP_TYPE" = "ui" ]; then
    APP_PATH="web_ui.py"
    PROCESS_NAME="web_ui.py"
    APP_DESC="Web UI"
else
    APP_TYPE="app"
    APP_PATH="app.py"
    PROCESS_NAME="app.py"
    APP_DESC="主程序"
fi

#============================================
# 辅助函数
#============================================

# 打印带颜色的日志
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${CYAN}[✓]${NC} $1"
}

# 显示帮助信息
show_help() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${PURPLE}  ChatGPT-on-WeChat 管理脚本${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${GREEN}用法:${NC}"
    echo -e "  $0 [命令] [类型]"
    echo ""
    echo -e "${GREEN}命令:${NC}"
    echo -e "  ${CYAN}start${NC}    启动程序"
    echo -e "  ${CYAN}stop${NC}     停止程序"
    echo -e "  ${CYAN}restart${NC}  重启程序"
    echo -e "  ${CYAN}status${NC}   查看状态"
    echo -e "  ${CYAN}log${NC}      查看日志"
    echo -e "  ${CYAN}tail${NC}     实时查看日志"
    echo -e "  ${CYAN}clean${NC}    清理旧日志（保留7天）"
    echo -e "  ${CYAN}help${NC}     显示此帮助信息"
    echo ""
    echo -e "${GREEN}类型:${NC}"
    echo -e "  ${CYAN}app${NC}      主程序（默认）"
    echo -e "  ${CYAN}ui${NC}       Web UI"
    echo ""
    echo -e "${GREEN}示例:${NC}"
    echo -e "  $0 start           # 启动主程序"
    echo -e "  $0 start ui        # 启动 Web UI"
    echo -e "  $0 restart         # 重启主程序"
    echo -e "  $0 status          # 查看所有状态"
    echo -e "  $0 tail app        # 实时查看主程序日志"
    echo -e "  $0 clean           # 清理7天前的日志"
    echo ""
    echo -e "${GREEN}快捷方式:${NC}"
    echo -e "  $0                 # 智能启动（未运行则启动）"
    echo -e "  $0 1               # 重启（兼容旧版）"
    echo -e "  $0 2               # 停止（兼容旧版）"
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# 检查程序是否运行
check_running() {
    local process=$1
    local pid=$(pgrep -f "python3.*$process" | head -1)
    
    if [ -n "$pid" ]; then
        echo "$pid"
        return 0
    else
        return 1
    fi
}

# 获取程序状态
get_status() {
    local process=$1
    local desc=$2
    local pid=$(check_running "$process")
    
    if [ -n "$pid" ]; then
        local uptime=$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ')
        local mem=$(ps -o rss= -p "$pid" 2>/dev/null | awk '{printf "%.1f MB", $1/1024}')
        echo -e "${GREEN}●${NC} ${desc} ${GREEN}运行中${NC} - PID: ${CYAN}${pid}${NC} | 运行时间: ${uptime} | 内存: ${mem}"
        return 0
    else
        echo -e "${RED}○${NC} ${desc} ${RED}未运行${NC}"
        return 1
    fi
}

# 显示所有状态
show_status() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${PURPLE}  程序运行状态${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    get_status "app.py" "主程序  "
    get_status "web_ui.py" "Web UI  "
    
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# 启动程序
start_process() {
    local pid=$(check_running "$PROCESS_NAME")
    
    if [ -n "$pid" ]; then
        log_warn "${APP_DESC} 已在运行中 (PID: $pid)"
        return 1
    fi
    
    # 创建日志目录
    if [ ! -d "$LOG_DIR" ]; then
        mkdir -p "$LOG_DIR"
        log_info "创建日志目录: $LOG_DIR"
    fi
    
    # 设置日志文件
    local date=$(date +%Y_%m_%d)
    local log_file="$LOG_DIR/log_${APP_TYPE}_${date}.txt"
    
    # 进入应用目录
    cd "$APP_DIR" || {
        log_error "无法进入目录: $APP_DIR"
        return 1
    }
    
    # 检查程序文件是否存在
    if [ ! -f "$APP_PATH" ]; then
        log_error "程序文件不存在: $APP_PATH"
        return 1
    fi
    
    # 启动程序
    log_info "正在启动 ${APP_DESC}..."
    nohup python3 "$APP_PATH" >> "$log_file" 2>&1 &
    local new_pid=$!
    
    # 等待并验证启动
    sleep 2
    if ps -p $new_pid > /dev/null 2>&1; then
        log_success "${APP_DESC} 启动成功！"
        echo -e "${GREEN}[INFO]${NC} 进程 ID: ${CYAN}${new_pid}${NC}"
        echo -e "${GREEN}[INFO]${NC} 日志文件: ${CYAN}${log_file}${NC}"
        echo -e "${GREEN}[INFO]${NC} 查看日志: ${CYAN}$0 tail $APP_TYPE${NC}"
        return 0
    else
        log_error "${APP_DESC} 启动失败，请查看日志"
        tail -n 20 "$log_file"
        return 1
    fi
}

# 停止程序
stop_process() {
    local pid=$(check_running "$PROCESS_NAME")
    
    if [ -z "$pid" ]; then
        log_warn "${APP_DESC} 未在运行"
        return 1
    fi
    
    log_info "正在停止 ${APP_DESC} (PID: $pid)..."
    
    # 尝试优雅关闭
    kill -TERM "$pid" 2>/dev/null
    
    # 等待最多10秒
    for i in {1..10}; do
        if ! ps -p "$pid" > /dev/null 2>&1; then
            log_success "${APP_DESC} 已停止"
            return 0
        fi
        sleep 1
    done
    
    # 强制关闭
    log_warn "程序未响应，强制关闭..."
    kill -9 "$pid" 2>/dev/null
    sleep 1
    
    if ! ps -p "$pid" > /dev/null 2>&1; then
        log_success "${APP_DESC} 已强制停止"
        return 0
    else
        log_error "无法停止 ${APP_DESC}"
        return 1
    fi
}

# 重启程序
restart_process() {
    log_info "正在重启 ${APP_DESC}..."
    
    if stop_process; then
        log_info "等待 3 秒..."
        sleep 3
    fi
    
    start_process
}

# 查看日志
show_log() {
    local date=$(date +%Y_%m_%d)
    local log_file="$LOG_DIR/log_${APP_TYPE}_${date}.txt"
    
    if [ ! -f "$log_file" ]; then
        log_error "日志文件不存在: $log_file"
        return 1
    fi
    
    log_info "显示日志: $log_file"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    tail -n 50 "$log_file"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# 实时查看日志
tail_log() {
    local date=$(date +%Y_%m_%d)
    local log_file="$LOG_DIR/log_${APP_TYPE}_${date}.txt"
    
    if [ ! -f "$log_file" ]; then
        log_error "日志文件不存在: $log_file"
        return 1
    fi
    
    log_info "实时查看日志: $log_file"
    log_info "按 Ctrl+C 退出"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    tail -f "$log_file"
}

# 清理旧日志
clean_logs() {
    local days=${1:-7}
    log_info "清理 ${days} 天前的日志文件..."
    
    if [ ! -d "$LOG_DIR" ]; then
        log_warn "日志目录不存在"
        return 1
    fi
    
    local count=$(find "$LOG_DIR" -name "log_*.txt" -type f -mtime +${days} 2>/dev/null | wc -l)
    
    if [ $count -eq 0 ]; then
        log_info "没有需要清理的日志"
        return 0
    fi
    
    find "$LOG_DIR" -name "log_*.txt" -type f -mtime +${days} -delete 2>/dev/null
    log_success "已清理 ${count} 个日志文件"
}

# 智能启动（未运行则启动，已运行则显示状态）
smart_start() {
    local pid=$(check_running "$PROCESS_NAME")
    
    if [ -n "$pid" ]; then
        show_status
    else
        start_process
    fi
}

#============================================
# 主逻辑
#============================================

# 解析命令
COMMAND="${1:-smart}"

case "$COMMAND" in
    start)
        start_process
        ;;
    stop)
        stop_process
        ;;
    restart|reload)
        restart_process
        ;;
    status)
        show_status
        ;;
    log)
        show_log
        ;;
    tail|follow)
        tail_log
        ;;
    clean|cleanup)
        clean_logs "$2"
        ;;
    help|--help|-h)
        show_help
        ;;
    # 兼容旧版参数
    1)
        restart_process
        ;;
    2)
        stop_process
        ;;
    smart|*)
        smart_start
        ;;
esac

exit $?