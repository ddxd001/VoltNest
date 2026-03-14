#!/bin/bash
# LeRobot AlohaMini - 树莓派端（从臂端）一键启动脚本
# 用于启动从臂控制服务

set -e

# ============ 配置选项 ============ #
# 自动更新开关：true=启用自动更新，false=禁用自动更新
AUTO_UPDATE=true

# 摄像头录制开关：true=启用录制，false=禁用录制
ENABLE_CAMERA_RECORDING=true
# ================================= #

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  LeRobot AlohaMini - 树莓派端启动${NC}"
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
    echo -e "${YELLOW}请先安装 Miniconda${NC}"
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
echo -e "${YELLOW}🔌 检查从臂串口设备...${NC}"
if ls /dev/ttyACM* 1> /dev/null 2>&1; then
    echo -e "${GREEN}✅ 找到串口设备：${NC}"
    ls /dev/ttyACM*
else
    echo -e "${RED}⚠️  警告: 未找到串口设备 (/dev/ttyACM*)${NC}"
    echo -e "${YELLOW}请检查：${NC}"
    echo "  1. 从臂是否已连接"
    echo "  2. 从臂是否已上电"
    echo "  3. USB 线是否连接正常"
    echo ""
    read -p "是否继续？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""

# 启动摄像头录制（如果启用）
RECORDER_PID=""
if [ "$ENABLE_CAMERA_RECORDING" = true ]; then
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}  启动摄像头录制${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo ""
    
    # 检查录制模块是否存在
    if [ -d "camera_recorder" ] && [ -f "camera_recorder/scripts/start_recorder.sh" ]; then
        echo -e "${YELLOW}📹 启动摄像头录制（后台运行）...${NC}"
        
        # 后台启动录制程序
        cd camera_recorder
        nohup ./scripts/start_recorder.sh > recorder.log 2>&1 &
        RECORDER_PID=$!
        cd "$SCRIPT_DIR"
        
        # 等待录制程序启动
        sleep 2
        
        # 检查录制程序是否成功启动
        if ps -p $RECORDER_PID > /dev/null 2>&1; then
            echo -e "${GREEN}✅ 摄像头录制已启动 (PID: $RECORDER_PID)${NC}"
            echo -e "${GREEN}   录制日志: camera_recorder/recorder.log${NC}"
        else
            echo -e "${RED}⚠️  摄像头录制启动失败，请检查日志${NC}"
            RECORDER_PID=""
        fi
    else
        echo -e "${YELLOW}⚠️  未找到摄像头录制模块，跳过录制${NC}"
    fi
    echo ""
fi

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  启动从臂控制服务${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "${GREEN}配置信息：${NC}"
echo "  - 机械臂类型: so-arm-5dof"
echo "  - 监听端口: 5555 (命令), 5556 (观测)"
echo "  - 控制频率: 30 Hz"
echo "  - 看门狗超时: 1500 ms"
if [ "$ENABLE_CAMERA_RECORDING" = true ] && [ -n "$RECORDER_PID" ]; then
    echo "  - 摄像头录制: 已启用 (PID: $RECORDER_PID)"
fi
echo ""
echo -e "${YELLOW}⚠️  注意事项：${NC}"
echo "  1. 确保从臂已上电"
echo "  2. 确保串口连接正常"
echo "  3. 等待 Mac 端连接后开始遥操作"
if [ "$ENABLE_CAMERA_RECORDING" = true ] && [ -n "$RECORDER_PID" ]; then
    echo "  4. 摄像头正在录制，停止服务时录制也会自动停止"
fi
echo ""
echo -e "${YELLOW}按 Ctrl+C 停止服务${NC}"
echo ""

# 定义清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}正在停止服务...${NC}"
    
    # 停止摄像头录制
    if [ -n "$RECORDER_PID" ]; then
        echo -e "${YELLOW}停止摄像头录制...${NC}"
        kill -SIGINT $RECORDER_PID 2>/dev/null || true
        sleep 1
        # 如果进程还在运行，强制终止
        if ps -p $RECORDER_PID > /dev/null 2>&1; then
            kill -SIGKILL $RECORDER_PID 2>/dev/null || true
        fi
        echo -e "${GREEN}✅ 摄像头录制已停止${NC}"
    fi
}

# 注册清理函数
trap cleanup EXIT INT TERM

# 运行从臂服务
python -m lerobot.robots.alohamini.lekiwi_host \
  --arm_profile so-arm-5dof

# 程序结束
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}✅ 从臂服务已退出${NC}"
echo -e "${BLUE}================================================${NC}"
