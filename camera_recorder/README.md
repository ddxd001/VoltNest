# 📹 摄像头录制模块

独立的树莓派摄像头录制模块，用于在遥操作过程中录制视频。

## 🎯 功能特点

- ✅ 启动即录制，停止即结束
- ✅ 自动生成带时间戳的文件名
- ✅ 支持多种摄像头（USB/CSI）
- ✅ 可配置分辨率和帧率
- ✅ 独立运行，不影响主程序

---

## 📁 目录结构

```
camera_recorder/
├── README.md                # 本文档
├── config.yaml              # 配置文件
├── requirements.txt         # Python 依赖
├── src/                     # 源代码
│   ├── __init__.py
│   ├── camera_recorder.py   # 主录制程序
│   └── config_loader.py     # 配置加载
├── scripts/                 # 脚本
│   ├── start_recorder.sh    # 启动录制
│   ├── stop_recorder.sh     # 停止录制
│   └── test_camera.py       # 测试摄像头
└── recordings/              # 录制文件存储
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd ~/lerobot_alohamini/camera_recorder
pip install -r requirements.txt
```

### 2. 配置摄像头

编辑 `config.yaml`：

```yaml
camera:
  device_id: 0              # 摄像头设备 ID（0, 1, 2...）
  width: 640                # 分辨率宽度
  height: 480               # 分辨率高度
  fps: 30                   # 帧率

recording:
  output_dir: "./recordings"  # 录制文件保存目录
  codec: "mp4v"              # 视频编码（mp4v, XVID, H264）
  file_prefix: "recording"   # 文件名前缀
```

### 3. 测试摄像头

```bash
cd ~/lerobot_alohamini/camera_recorder
python scripts/test_camera.py
```

### 4. 启动录制

```bash
cd ~/lerobot_alohamini/camera_recorder
./scripts/start_recorder.sh
```

### 5. 停止录制

按 `Ctrl+C` 或运行：

```bash
./scripts/stop_recorder.sh
```

---

## ⚙️ 配置说明

### 摄像头设备 ID

- `0`: 第一个摄像头（通常是 /dev/video0）
- `1`: 第二个摄像头（通常是 /dev/video1）
- 可以使用测试脚本查看可用摄像头

### 分辨率建议

| 分辨率 | 文件大小 | 适用场景 |
|--------|---------|---------|
| 1920x1080 | ~200 MB/分钟 | 高清录制 |
| 1280x720 | ~100 MB/分钟 | 标清录制（推荐） |
| 640x480 | ~50 MB/分钟 | 低清录制 |

### 视频编码

- `mp4v`: 通用编码，兼容性好
- `XVID`: 压缩率高
- `H264`: 质量好，需要硬件支持

---

## 🔧 使用示例

### 示例 1：基本录制

```bash
# 启动录制（使用默认配置）
./scripts/start_recorder.sh

# 程序会输出：
# [INFO] Camera initialized: 640x480 @ 30fps
# [INFO] Recording started: recordings/recording_20260314_110730.mp4
# [INFO] Press Ctrl+C to stop recording
```

### 示例 2：自定义配置

修改 `config.yaml` 后启动：

```bash
./scripts/start_recorder.sh
```

### 示例 3：与遥操作同时运行

```bash
# 终端 1：启动录制
cd ~/lerobot_alohamini/camera_recorder
./scripts/start_recorder.sh

# 终端 2：启动遥操作
cd ~/lerobot_alohamini
./start_pi.sh
```

---

## 📊 录制文件

### 文件命名格式

```
recording_YYYYMMDD_HHMMSS.mp4
```

例如：
- `recording_20260314_110730.mp4`
- `recording_20260314_143522.mp4`

### 文件位置

默认保存在 `camera_recorder/recordings/` 目录下。

### 下载录制文件

```bash
# 从树莓派下载到 Mac
scp ubuntu@192.168.3.33:~/lerobot_alohamini/camera_recorder/recordings/*.mp4 ~/Downloads/
```

---

## 🐛 故障排查

### 问题 1：找不到摄像头

**错误信息**：
```
[ERROR] Failed to open camera device 0
```

**解决方法**：
```bash
# 查看可用摄像头
ls /dev/video*

# 测试摄像头
python scripts/test_camera.py

# 修改 config.yaml 中的 device_id
```

### 问题 2：录制失败

**错误信息**：
```
[ERROR] Failed to initialize video writer
```

**解决方法**：
```bash
# 检查输出目录权限
chmod 755 recordings/

# 尝试更换编码格式（修改 config.yaml）
codec: "XVID"  # 或 "mp4v"
```

### 问题 3：视频无法播放

**可能原因**：编码格式不兼容

**解决方法**：
```bash
# 使用 ffmpeg 转换格式
ffmpeg -i recording.mp4 -c:v libx264 recording_converted.mp4
```

---

## 📝 注意事项

1. **存储空间**
   - 定期清理旧录像
   - 监控磁盘空间：`df -h`

2. **性能影响**
   - 录制不会影响遥操作性能（独立进程）
   - 建议使用 720p 分辨率

3. **摄像头占用**
   - 确保摄像头未被其他程序占用
   - 一个摄像头同时只能被一个程序使用

4. **文件管理**
   - 录制文件较大，注意存储空间
   - 建议定期备份到 Mac 或云端

---

## 🔍 技术细节

### 依赖库

- `opencv-python`: 摄像头访问和视频录制
- `pyyaml`: 配置文件解析
- `numpy`: 图像处理

### 录制流程

1. 读取配置文件
2. 初始化摄像头
3. 创建视频写入器
4. 循环读取帧并写入
5. 捕获 Ctrl+C 信号
6. 释放资源并保存

---

## 📞 技术支持

如有问题，请检查：
1. 摄像头是否正确连接
2. 配置文件是否正确
3. 输出目录是否有写权限
4. 磁盘空间是否充足
