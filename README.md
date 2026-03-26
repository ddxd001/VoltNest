# VoltNest - 完整文档

## 📋 目录

- [更新日志](#更新日志)
- [简介](#简介)
- [快速启动](#快速启动)
- [完整安装指南](#完整安装指南)
- [常用指令](#常用指令)
- [视频切换功能](#视频切换功能)
- [摄像头录制功能](#摄像头录制功能)
- [自动更新功能](#自动更新功能)
- [贡献指南](#贡献指南)

---

## 更新日志

- **[2025-11-06]** Compatible with LeRobot 0.4
- **[2026-03-14]** 添加视频表情切换功能
- **[2026-03-14]** 添加摄像头录制集成功能
- **[2026-03-14]** 添加启动脚本自动更新功能
- **[2026-03-14]** 优化视频切换为单视频循环模式

---

## 简介

Compared to the original lerobot, VoltNest significantly enhances debugging capabilities and is adapted for AlohaMini wheeled dual-arm robot hardware (based on Lekiwi extension).

For newly added debugging commands, please refer to:
[Debug Command Summary](examples/debug/README.md)

AlohaMini Hardware 
![alohamini concept](examples/alohamini/media/alohamini3a.png)

---

## 快速启动

### 🚀 一键启动（推荐）

#### Mac 端（遥控端）

```bash
cd ~/Repository/VoltNest
./start_mac.sh
```

#### 树莓派端（从臂端）

```bash
cd ~/VoltNest
./start_pi.sh
```

**可选：启用摄像头录制**

编辑 `start_pi.sh`，设置 `ENABLE_CAMERA_RECORDING=true`，即可在启动时自动开始录制。

### ⌨️ 键盘控制说明

- **W/S**: 前进/后退
- **A/D**: 左转/右转
- **Z/X**: 左移/右移
- **U/J**: 升降轴上升/下降
- **R/F**: 加速/减速
- **C**: 切换到下一个视频表情
- **V**: 切换到上一个视频表情
- **Q**: 退出程序

### 📋 完整启动流程

#### 步骤 1：启动树莓派端（先启动）

```bash
# SSH 到树莓派
ssh ubuntu@192.168.3.33

# 运行一键启动脚本
cd ~/VoltNest
./start_pi.sh
```

#### 步骤 2：启动 Mac 端（后启动）

```bash
# 在 Mac 上运行
cd ~/Repository/VoltNest
./start_mac.sh
```

#### 步骤 3：开始遥操作

- 移动主臂，从臂会跟随
- 使用键盘控制底盘和升降轴
- 按 C/V 键切换视频表情
- 按 Ctrl+C 或 Q 退出

---

## 完整安装指南

### 1. 准备工作

#### 网络环境测试
```bash
curl https://www.google.com
curl https://huggingface.co
```
First ensure network connectivity

#### CUDA 环境测试
```bash
nvidia-smi
```
After entering in terminal, you should be able to see the CUDA version number

### 2. 克隆仓库

```bash
cd ~
git clone https://github.com/ddxd001/VoltNest.git
```

### 3. 串口授权

By default, serial ports cannot be accessed. We need to authorize the ports.

1. Enter `whoami` in terminal  // Check current username
2. Enter `sudo usermod -a -G dialout username` // Permanently add username to device user group
3. Restart computer to make permissions effective

### 4. 安装 conda3 和环境依赖

Install conda3
```bash
mkdir -p ~/miniconda3
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
rm ~/miniconda3/miniconda.sh
~/miniconda3/bin/conda init bash
source ~/.bashrc
```

Initialize conda3
```bash
conda create -y -n lerobot_alohamini python=3.10
conda activate lerobot_alohamini
```

Install environment dependencies
```bash
cd ~/VoltNest
pip install -e .[all]
conda install ffmpeg=7.1.1 -c conda-forge
```

### 5. 配置机械臂端口号

AlohaMini has 4 robot arms in total: 2 leader arms connected to the PC, 2 follower arms connected to Raspberry Pi.

Connect the robot arms to power and to the computer via USB, then find the robot arm port numbers.

Method 1: Find ports through script:
```bash
cd ~/VoltNest
lerobot-find-port
```

Method 2: Direct command in terminal
```bash
ls /dev/ttyACM*
```

**After finding the correct ports, please modify the corresponding port numbers in the following files:**
- Follower arms: `lerobot/robots/alohamini/config_lekiwi.py`
- Leader arms: `examples/alohamini/teleoperate_bi.py`

### 6. 配置摄像头端口号

Camera ports are already built into the Raspberry Pi and do not need configuration:
`lerobot/robots/alohamini/config_lekiwi.py`

Note: Multiple cameras cannot be plugged into one USB Hub; 1 USB Hub only supports 1 camera

### 7. 遥操作校准和测试

#### 7.1 设置机械臂到中间位置

Host-side calibration:
SSH into the Raspberry Pi, install the conda environment, then perform the following operations:

```bash
python -m lerobot.robots.alohamini.lekiwi_host
```

If executing for the first time, the system will prompt us to calibrate the robot arm.
![Calibration](examples/alohamini/media/mid_position_so100.png)

Client-side calibration:
```bash
python examples/alohamini/teleoperate_bi.py \
--remote_ip 192.168.50.43
```

#### 7.2 遥操作命令总结

Raspberry Pi side:
```bash
python -m lerobot.robots.alohamini.lekiwi_host
```

PC side:
```bash
# Normal teleoperation
python examples/alohamini/teleoperate_bi.py \
  --remote_ip 192.168.50.43

# Teleoperation with voice functionality
python examples/alohamini/teleoperate_bi_voice.py \
  --remote_ip 192.168.50.43
```

### 8. 录制数据集

#### 1. Register on HuggingFace, Obtain and Configure Key

1. Go to HuggingFace website (huggingface.co), apply for {Key}
2. Add API token to Git credentials

```bash
git config --global credential.helper store
huggingface-cli login --token {key} --add-to-git-credential
```

#### 2. Run Script

```bash
HF_USER=$(huggingface-cli whoami | head -n 1)
echo $HF_USER

python examples/alohamini/record_bi.py \
  --dataset $HF_USER/so100_bi_test \
  --num_episodes 1 \
  --fps 30 \
  --episode_time 45 \
  --reset_time 8 \
  --task_description "pickup1" \
  --remote_ip 127.0.0.1
```

### 9. 回放数据集

```bash
python examples/alohamini/replay_bi.py  \
--dataset $HF_USER/so100_bi_test \
--episode 0 \
--remote_ip 127.0.0.1
```

### 10. 数据集可视化

```bash
lerobot-dataset-viz \
  --repo-id $HF_USER/so100_bi_test \
  --episode-index 0
```

### 11. 本地训练

```bash
lerobot-train \
  --dataset.repo_id=$HF_USER/so100_bi_test \
  --policy.type=act \
  --output_dir=outputs/train/act_your_dataset1 \
  --job_name=act_your_dataset \
  --policy.device=cuda \
  --wandb.enable=false \
  --policy.repo_id=liyitenga/act_policy
```

### 12. 远程训练

Using AutoDL as an example:

```bash
# Enter remote terminal, initialize conda
conda init

# Restart terminal, create environment
conda create -y -n lerobot python=3.10
conda activate lerobot

# Academic acceleration
source /etc/network_turbo

# Get lerobot
git clone https://github.com/ddxd001/VoltNest.git

# Install necessary files
cd ~/VoltNest
pip install -e ".[feetech,aloha,pusht]"
```

### 13. 评估训练集

```bash
python examples/alohamini/evaluate_bi.py \
  --num_episodes 3 \
  --fps 20 \
  --episode_time 45 \
  --task_description "Pick and place task" \
  --hf_model_id liyitenga/act_policy \
  --hf_dataset_id liyitenga/eval_dataset \
  --remote_ip 127.0.0.1 \
  --robot_id my_alohamini \
  --hf_model_id ./outputs/train/act_your_dataset1/checkpoints/020000/pretrained_model
```

---

## 常用指令

### 校准指令

#### Mac 端 - 校准主臂

```bash
# 校准左主臂
lerobot-calibrate \
  --teleop.type=so101_leader \
  --teleop.port=/dev/cu.usbmodem5AE60814681 \
  --teleop.arm_profile=so-arm-5dof \
  --teleop.id=left_leader

# 校准右主臂
lerobot-calibrate \
  --teleop.type=so101_leader \
  --teleop.port=/dev/cu.usbmodem5AE60528341 \
  --teleop.arm_profile=so-arm-5dof \
  --teleop.id=right_leader
```

#### 树莓派端 - 校准从臂

```bash
ssh ubuntu@192.168.3.33
conda activate lerobot_alohamini
cd ~/VoltNest
lerobot-calibrate --robot.type=lekiwi
```

### 调试命令

#### 查看串口设备

```bash
# Mac
ls /dev/cu.usbmodem*

# 树莓派
ls /dev/ttyACM*
```

#### 测试网络连接

```bash
# Mac 端测试树莓派
ping 192.168.3.33

# 测试 ZMQ 端口
nc -zv 192.168.3.33 5555
nc -zv 192.168.3.33 5556
```

#### 查看校准文件

```bash
# Mac 端
ls ~/.cache/huggingface/lerobot/calibration/teleoperators/so_leader/

# 树莓派端
ls ~/.cache/huggingface/lerobot/calibration/robots/lekiwi/
```

---

## 视频切换功能

### 🎯 功能说明

**单视频循环播放模式**：
- 每个视频独立循环播放
- 只在按下 C/V 键时才切换到其他视频
- 不按键时保持当前视频持续循环

### 核心特性

1. **单视频循环**
   - VLC 播放单个视频并循环
   - 不会自动切换到下一个视频
   - 保持当前表情持续显示

2. **手动切换**
   - 按 C 键：切换到下一个视频
   - 按 V 键：切换到上一个视频
   - 切换后新视频开始循环播放

3. **快速切换**
   - 停止当前 VLC 进程
   - 启动新视频的 VLC 进程
   - 切换时间约 1-2 秒（包含黑屏过渡）

### 依赖要求

树莓派端需要安装 VLC：
```bash
sudo apt-get install vlc
```

验证安装：
```bash
which cvlc
```

---

## 摄像头录制功能

### 🎯 功能概述

`start_pi.sh` 现在支持在启动遥操作服务时**自动启动摄像头录制**，实现一键启动、同步录制的功能。

### ⚙️ 配置方法

#### 开启摄像头录制

编辑 `start_pi.sh` 文件：

```bash
# 摄像头录制开关：true=启用录制，false=禁用录制
ENABLE_CAMERA_RECORDING=true    # 改为 true
```

#### 关闭摄像头录制

```bash
ENABLE_CAMERA_RECORDING=false   # 改为 false（默认）
```

### 🚀 使用方法

```bash
# 1. 编辑 start_pi.sh，设置 ENABLE_CAMERA_RECORDING=true

# 2. 启动服务（自动开始录制）
./start_pi.sh

# 3. 进行遥操作...

# 4. 完成后按 Ctrl+C 停止（录制会自动停止并保存）
```

### 📊 录制管理

#### 查看录制日志

```bash
# 实时查看录制日志
tail -f ~/VoltNest/camera_recorder/recorder.log
```

#### 查看录制文件

```bash
# 列出所有录制文件
ls -lh ~/VoltNest/camera_recorder/recordings/
```

#### 下载录制文件

```bash
# 从树莓派下载到 Mac
scp ubuntu@192.168.3.33:~/VoltNest/camera_recorder/recordings/*.mp4 ~/Downloads/
```

### 🔧 高级配置

编辑 `camera_recorder/config.yaml`：

```yaml
camera:
  device_id: 0        # 摄像头 ID
  width: 1280         # 分辨率
  height: 720
  fps: 30             # 帧率

recording:
  codec: "MJPG"       # 编码格式（推荐MJPG用于树莓派）
  file_prefix: "recording"
```

### 📝 注意事项

1. **存储空间**
   - 720p @ 30fps ≈ 100-150 MB/分钟
   - 定期清理旧录像

2. **性能影响**
   - 录制在后台运行，不影响遥操作性能
   - 如遇性能问题，可降低录制分辨率

3. **自动停止**
   - 按 Ctrl+C 停止服务时，录制会自动停止
   - 录制文件会自动保存，不会丢失

---

## 自动更新功能

### 📋 功能概述

启动脚本现在支持**自动从 GitHub 拉取最新代码**，确保每次运行时使用最新版本。

### 🎛️ 开关控制

#### 启用自动更新（默认）

编辑启动脚本：
```bash
AUTO_UPDATE=true
```

#### 禁用自动更新

编辑启动脚本：
```bash
AUTO_UPDATE=false
```

### 🔄 工作流程

```
启动脚本
    ↓
检查是否是 Git 仓库
    ↓
检查是否有未提交的本地修改
    ↓
├─ 有未提交修改 → 跳过更新，显示警告
└─ 无未提交修改 → 执行 git pull
    ↓
检查依赖文件是否变化
    ↓
├─ 有变化 → 提示重新安装依赖
└─ 无变化 → 继续启动程序
```

### ✅ 智能检测功能

1. **本地修改检测**
   - 自动检测是否有未提交的本地修改
   - 如有修改，跳过更新以避免冲突

2. **依赖变化检测**
   - 检测依赖文件是否变化
   - 如有变化，提示用户重新安装依赖

3. **Git 仓库检测**
   - 检测当前目录是否是 Git 仓库
   - 非 Git 仓库时跳过更新

### 🔧 手动更新方法

如果禁用了自动更新，可以手动更新代码：

```bash
cd ~/VoltNest
git pull origin main
pip install -e ".[feetech]"  # 如有依赖变化
```

---

## 🐛 常见问题

### 1. 串口设备未找到

**Mac 端**：
- 检查主臂是否连接：`ls /dev/cu.usbmodem*`
- 修改串口路径：编辑 `examples/alohamini/teleoperate_bi.py`

**树莓派端**：
- 检查从臂是否连接：`ls /dev/ttyACM*`
- 确认从臂已上电

### 2. 无法连接树莓派

- 检查网络：`ping 192.168.3.33`
- 确认树莓派端服务已启动
- 检查防火墙设置

### 3. 环境未激活

```bash
conda activate lerobot_alohamini
```

### 4. 摄像头录制失败

- 检查摄像头设备：`ls -l /dev/video*`
- 查看录制日志：`cat ~/VoltNest/camera_recorder/recorder.log`
- 测试摄像头：`cd camera_recorder && python scripts/test_camera.py`

---

## 🎯 新版本特性

- ✅ 视频表情切换功能（C/V 键）
- ✅ 摄像头录制功能（可选启用）
- ✅ 安全电流调整（2800mA）
- ✅ 简化的启动参数
- ✅ 一键启动脚本
- ✅ 自动更新功能
- ✅ 更好的错误处理
- ✅ 单视频循环播放模式

---

## 贡献指南

Everyone is welcome to contribute, and we value everybody's contribution. Code is thus not the only way to help the community.

Please be mindful to respect our [code of conduct](CODE_OF_CONDUCT.md).

---

## 📞 技术支持

如有问题，请检查：
1. 硬件连接是否正常
2. 网络连接是否正常
3. 环境是否正确激活
4. 串口路径是否正确
5. 查看相关日志文件

---

## 📄 许可证

本项目基于 Apache License 2.0 许可证。详见 LICENSE 文件。

