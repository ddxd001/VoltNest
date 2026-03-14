#!/bin/bash
# 摄像头录制启动脚本

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  摄像头录制服务启动${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
RECORDER_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$RECORDER_DIR"

echo -e "${GREEN}📁 工作目录: $RECORDER_DIR${NC}"
echo ""

# 检测并激活 Conda 环境
if command -v conda &> /dev/null; then
    echo -e "${YELLOW}🔄 激活虚拟环境: lerobot_alohamini${NC}"
    source $(conda info --base)/etc/profile.d/conda.sh
    conda activate lerobot_alohamini
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ 错误: 无法激活环境 lerobot_alohamini${NC}"
        echo -e "${YELLOW}请先创建环境或检查环境名称${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ 虚拟环境已激活${NC}"
    echo ""
else
    echo -e "${YELLOW}⚠️  警告: 未找到 conda，使用系统 Python${NC}"
    echo ""
fi

# 检查配置文件
if [ ! -f "config.yaml" ]; then
    echo -e "${RED}❌ 错误: 配置文件不存在 (config.yaml)${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 配置文件已找到${NC}"
echo ""

# 检查 Python
if ! command -v python &> /dev/null; then
    echo -e "${RED}❌ 错误: 未找到 python${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python 环境已就绪${NC}"
echo ""

# 检查依赖
echo -e "${YELLOW}🔍 检查依赖...${NC}"
if ! python -c "import cv2" &> /dev/null; then
    echo -e "${YELLOW}⚠️  警告: opencv-python 未安装${NC}"
    echo -e "${YELLOW}正在安装依赖...${NC}"
    pip install -r requirements.txt
fi

if ! python -c "import yaml" &> /dev/null; then
    echo -e "${YELLOW}⚠️  警告: pyyaml 未安装${NC}"
    echo -e "${YELLOW}正在安装依赖...${NC}"
    pip install -r requirements.txt
fi

echo -e "${GREEN}✅ 依赖已安装${NC}"
echo ""

# 创建录制目录
mkdir -p recordings

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  启动录制程序${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "${YELLOW}⚠️  提示:${NC}"
echo "  - 启动即开始录制"
echo "  - 按 Ctrl+C 停止录制"
echo "  - 录制文件保存在 recordings/ 目录"
echo ""

# 运行录制程序
python src/camera_recorder.py

# 程序结束
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}✅ 录制程序已退出${NC}"
echo -e "${BLUE}================================================${NC}"
