#!/bin/bash  

rm -rf /home/alex/Desktop/chatgpt-on-wechat/image/Tarot/*

# 创建日志目录  
mkdir -p ./log  

# 获取当前时间，用于日志文件名（只保留年月日）  
current_date=$(date "+%Y_%m_%d")  
log_dir="./log"  
log_file="${log_dir}/log_${current_date}.txt"  

# 记录脚本日志的函数（输出到控制台和日志文件）  
log_message() {  
    local message="$(date "+%Y-%m-%d %H:%M:%S") - $1"  
    echo "$message"  
    echo "$message" >> "${log_file}"  
}  

# 检查进程是否运行  
check_process() {  
    pgrep -f "python3.*app\.py" > /dev/null  
    return $?  
}  

# 启动应用  
start_app() {  
    # 将应用的所有输出追加到日志文件  
    nohup python3 app.py >> "${log_file}" 2>&1 &  
    log_message "应用已启动，PID: $!"  
}  

# 停止应用  
stop_app() {  
    pid=$(pgrep -f "python3.*app\.py")  
    if [ ! -z "$pid" ]; then  
        kill -9 $pid  
        log_message "已终止进程，PID: $pid"  
    fi  
}  

# 主逻辑  
main() {  
    # 检查app.py是否存在  
    if [ ! -f "app.py" ]; then  
        log_message "错误：app.py 文件不存在"  
        exit 1  
    fi  

    # 检查当前进程状态  
    if check_process; then  
        case "$1" in  
            "1")  
                log_message "检测到现有进程，准备重启"  
                stop_app  
                log_message "等待5秒后重启..."  
                sleep 5  
                start_app  
                ;;  
            "2")  
                log_message "检测到现有进程，终止进程"  
                stop_app  
                ;;  
            *)  
                log_message "应用已在运行中，退出脚本"  
                ;;  
        esac  
    else  
        case "$1" in  
            "2")  
                log_message "没有检测到运行中的进程"  
                ;;  
            *)  
                log_message "启动新的应用实例"  
                start_app  
                ;;  
        esac  
    fi  
}  

# 执行主函数  
main "$1"