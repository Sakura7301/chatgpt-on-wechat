#!/bin/bash  

# 检查参数是否存在  
if [ $# -eq 0 ]; then  
    echo "错误：请提供一个1-99之间的数字参数" >&2  
    exit 1  
fi  

# 检查输入是否为数字  
if ! [[ $1 =~ ^[0-9]+$ ]]; then  
    echo "错误：参数必须是数字" >&2  
    exit 1  
fi  

# 检查数字范围  
if [ $1 -lt 1 ] || [ $1 -gt 99 ]; then  
    echo "错误：数字必须在1到99之间" >&2  
    exit 1  
fi  

# 检查face目录是否存在  
if [ ! -d "./face" ]; then  
    echo "错误：./face目录不存在" >&2  
    exit 1  
fi  

# 检查config.json是否存在  
if [ ! -f "./config.json" ]; then  
    echo "错误：config.json文件不存在" >&2  
    exit 1  
fi  

# 格式化数字为两位数（例如：1 -> 01）  
padded_num=$(printf "%02d" $1)  

# 查找对应前缀的文件  
file_found=$(find ./face -type f -name "${padded_num}_*" | head -n 1)  

if [ -z "$file_found" ]; then  
    echo "错误：没有找到以 ${padded_num}_ 为前缀的文件" >&2  
    exit 1  
fi  

# 拷贝文件到config.json  
cp "$file_found" "./config.json"  
echo "成功：已将文件 $file_found 拷贝到 config.json"