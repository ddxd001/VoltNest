#!/bin/bash
# 摄像头录制停止脚本

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  停止摄像头录制${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# 查找录制进程
RECORDER_PID=$(pgrep -f "camera_recorder.py" || true)

if [ -z "$RECORDER_PID" ]; then
    echo -e "${YELLOW}⚠️  未找到运行中的录制进程${NC}"
    exit 0
fi

echo -e "${YELLOW}找到录制进程: PID $RECORDER_PID${NC}"
echo -e "${YELLOW}正在停止...${NC}"

# 发送 SIGINT 信号（相当于 Ctrl+C）
kill -SIGINT $RECORDER_PID

# 等待进程结束
sleep 2

# 检查是否已停止
if ps -p $RECORDER_PID > /dev/null 2>&1; then
    echo -e "${YELLOW}进程未响应，强制停止...${NC}"
    kill -SIGKILL $RECORDER_PID
fi

echo -e "${GREEN}✅ 录制已停止${NC}"
echo ""
