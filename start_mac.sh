#!/bin/bash
# VoltNest - Mac 端（遥控端）一键启动脚本
# 用于启动主臂遥操作程序

set -e

# ============ 配置选项 ============ #
# 自动更新开关：true=启用自动更新，false=禁用自动更新
AUTO_UPDATE=true
# 底盘 HTTP 控制接口：true=随脚本一起启动，false=不启动
ENABLE_BASE_API=true
# ================================= #

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  VoltNest - Mac 端启动${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${GREEN}📁 工作目录: $SCRIPT_DIR${NC}"
echo ""

# 自动更新代码
if [ "$AUTO_UPDATE" = true ]; then
    echo -e "${YELLOW}🔄 检查代码更新...${NC}"
    
    # 检查是否是 Git 仓库
    if [ -d ".git" ]; then
        # 保存当前分支
        CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
        
        # 检查是否有未提交的更改
        if ! git diff-index --quiet HEAD --; then
            echo -e "${YELLOW}⚠️  检测到未提交的本地修改，跳过自动更新${NC}"
            echo -e "${YELLOW}提示: 如需更新，请先提交或暂存本地修改${NC}"
            echo ""
        else
            # 拉取最新代码
            echo -e "${YELLOW}正在从 GitHub 拉取最新代码...${NC}"
            if git pull origin "$CURRENT_BRANCH" --quiet; then
                echo -e "${GREEN}✅ 代码已更新到最新版本${NC}"
                
                # 检查是否需要重新安装依赖
                if git diff HEAD@{1} HEAD --name-only | grep -q "pyproject.toml\|setup.py\|requirements.txt"; then
                    echo -e "${YELLOW}⚠️  检测到依赖文件变化，建议重新安装：${NC}"
                    echo -e "${YELLOW}   pip install -e \".[feetech]\"${NC}"
                fi
            else
                echo -e "${YELLOW}⚠️  代码更新失败或已是最新版本${NC}"
            fi
            echo ""
        fi
    else
        echo -e "${YELLOW}⚠️  当前目录不是 Git 仓库，跳过自动更新${NC}"
        echo ""
    fi
else
    echo -e "${YELLOW}ℹ️  自动更新已禁用${NC}"
    echo -e "${YELLOW}提示: 如需启用，请编辑脚本设置 AUTO_UPDATE=true${NC}"
    echo ""
fi

# 检测 Conda
if ! command -v conda &> /dev/null; then
    echo -e "${RED}❌ 错误: 未找到 conda 命令${NC}"
    echo -e "${YELLOW}请先安装 Anaconda/Miniconda${NC}"
    exit 1
fi

# 激活环境
echo -e "${YELLOW}🔄 激活环境: lerobot_alohamini${NC}"
source $(conda info --base)/etc/profile.d/conda.sh
conda activate lerobot_alohamini

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ 错误: 无法激活环境 lerobot_alohamini${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 环境已激活${NC}"
echo ""

# 检查串口设备
echo -e "${YELLOW}🔌 检查主臂串口设备...${NC}"
LEFT_PORT="/dev/cu.usbmodem5AE60814681"
RIGHT_PORT="/dev/cu.usbmodem5AE60528341"

if [ ! -e "$LEFT_PORT" ] || [ ! -e "$RIGHT_PORT" ]; then
    echo -e "${RED}⚠️  警告: 主臂串口未完全找到${NC}"
    echo -e "${YELLOW}当前可用串口：${NC}"
    ls /dev/cu.usbmodem* 2>/dev/null || echo "  无 USB 串口设备"
    echo ""
    echo -e "${YELLOW}请检查：${NC}"
    echo "  1. 主臂是否已连接"
    echo "  2. 串口路径是否正确"
    echo "  3. 如需修改串口，编辑: examples/alohamini/teleoperate_bi.py (第 34-35 行)"
    echo ""
    read -p "是否继续？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 检查网络连接
echo -e "${YELLOW}🌐 检查树莓派网络连接...${NC}"
REMOTE_IP="192.168.3.33"
API_HTTP_HOST="127.0.0.1"
API_HTTP_PORT="8000"

if ping -c 1 -W 1 $REMOTE_IP &> /dev/null; then
    echo -e "${GREEN}✅ 树莓派在线 ($REMOTE_IP)${NC}"
else
    echo -e "${RED}⚠️  警告: 无法连接到树莓派 ($REMOTE_IP)${NC}"
    echo -e "${YELLOW}请确保：${NC}"
    echo "  1. 树莓派已开机"
    echo "  2. 网络连接正常"
    echo "  3. 树莓派端已启动 lekiwi_host 服务"
    echo ""
    read -p "是否继续？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 启动底盘 HTTP 控制接口（如果启用）
API_PID=""
if [ "$ENABLE_BASE_API" = true ]; then
    echo -e "${YELLOW}🚀 启动底盘 HTTP 控制接口（后台运行）...${NC}"
    python examples/alohamini/base_control_api.py \
      --remote_ip "$REMOTE_IP" \
      --http_host "$API_HTTP_HOST" \
      --http_port "$API_HTTP_PORT" \
      > base_control_api.log 2>&1 &
    API_PID=$!
    sleep 1

    if ps -p $API_PID > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 底盘 API 已启动 (PID: $API_PID)${NC}"
        echo -e "${GREEN}   接口地址: http://$API_HTTP_HOST:$API_HTTP_PORT${NC}"
        echo -e "${GREEN}   日志文件: base_control_api.log${NC}"
    else
        echo -e "${RED}⚠️  底盘 API 启动失败，请检查 base_control_api.log${NC}"
        API_PID=""
    fi
    echo ""
fi

echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  启动遥操作程序${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "${GREEN}配置信息：${NC}"
echo "  - 远程 IP: $REMOTE_IP"
echo "  - 控制频率: 30 FPS"
echo "  - 左主臂: $LEFT_PORT"
echo "  - 右主臂: $RIGHT_PORT"
if [ "$ENABLE_BASE_API" = true ] && [ -n "$API_PID" ]; then
    echo "  - 底盘 API: http://$API_HTTP_HOST:$API_HTTP_PORT (PID: $API_PID)"
fi
echo ""
echo -e "${YELLOW}⌨️  键盘控制：${NC}"
echo "  - W/S: 前进/后退"
echo "  - A/D: 左转/右转"
echo "  - Z/X: 左移/右移"
echo "  - U/J: 升降轴上升/下降"
echo "  - R/F: 加速/减速"
echo "  - Q: 退出"
echo ""
echo -e "${YELLOW}🎬 视频控制（新功能）：${NC}"
echo "  - 支持视频表情切换"
echo "  - 安全电流调整"
echo ""
echo -e "${YELLOW}按 Ctrl+C 停止程序${NC}"
echo ""

# 定义清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}正在停止服务...${NC}"
    if [ -n "$API_PID" ]; then
        echo -e "${YELLOW}停止底盘 API...${NC}"
        kill -SIGINT $API_PID 2>/dev/null || true
        sleep 1
        if ps -p $API_PID > /dev/null 2>&1; then
            kill -SIGKILL $API_PID 2>/dev/null || true
        fi
        echo -e "${GREEN}✅ 底盘 API 已停止${NC}"
    fi
}

# 注册清理函数
trap cleanup EXIT INT TERM

# 运行遥操作程序
python examples/alohamini/teleoperate_bi.py \
  --remote_ip $REMOTE_IP \
  --fps 30

# 程序结束
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}✅ 遥操作程序已退出${NC}"
echo -e "${BLUE}================================================${NC}"
