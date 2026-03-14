# stop_recorder.sh 脚本说明

## 🎯 作用

`stop_recorder.sh` 用于**在另一个终端**停止正在运行的录制程序。

---

## 📖 使用场景

### 场景 1：后台运行时停止录制

如果你将录制程序放到后台运行：

```bash
# 终端 1：后台启动录制
nohup ./scripts/start_recorder.sh > recorder.log 2>&1 &

# 终端 2：停止录制
./scripts/stop_recorder.sh
```

### 场景 2：SSH 连接断开后停止

如果你通过 SSH 启动了录制，然后断开了连接，可以重新连接后停止：

```bash
# 重新 SSH 连接
ssh ubuntu@192.168.3.33

# 停止录制
cd ~/lerobot_alohamini/camera_recorder
./scripts/stop_recorder.sh
```

### 场景 3：远程控制

从 Mac 端远程停止树莓派上的录制：

```bash
# 在 Mac 上执行
ssh ubuntu@192.168.3.33 "cd ~/lerobot_alohamini/camera_recorder && ./scripts/stop_recorder.sh"
```

---

## 🔧 工作原理

脚本会：
1. 查找正在运行的 `camera_recorder.py` 进程
2. 发送 `SIGINT` 信号（相当于按 Ctrl+C）
3. 等待进程正常退出
4. 如果进程未响应，强制终止

---

## ⚠️ 注意事项

### 大多数情况下不需要这个脚本

如果你在前台运行录制程序，直接按 **Ctrl+C** 即可停止，不需要使用这个脚本。

### 何时使用

- ✅ 后台运行时
- ✅ SSH 断开后重新连接
- ✅ 远程控制停止
- ✅ 自动化脚本中

### 何时不需要

- ❌ 前台运行时（直接按 Ctrl+C）
- ❌ 正常的交互式使用

---

## 💡 推荐使用方式

### 方式 1：前台运行（推荐）

```bash
# 启动录制
./scripts/start_recorder.sh

# 停止录制：直接按 Ctrl+C
```

### 方式 2：后台运行

```bash
# 启动录制（后台）
nohup ./scripts/start_recorder.sh > recorder.log 2>&1 &

# 查看日志
tail -f recorder.log

# 停止录制
./scripts/stop_recorder.sh
```

---

## 📝 总结

- **前台运行**：按 `Ctrl+C` 停止（最常用）
- **后台运行**：使用 `./scripts/stop_recorder.sh` 停止
- **远程控制**：通过 SSH 执行 `stop_recorder.sh`

大多数情况下，你只需要按 **Ctrl+C** 就可以了！
