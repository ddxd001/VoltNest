# VoltNest 控制 API 文档

本文档基于 VoltNest 当前实现，说明如何通过 HTTP API 控制机器人底盘、升降轴以及音频播放。

## 服务概览

- 服务脚本：`examples/alohamini/base_control_api.py`（运行在 Mac 端）
- 默认地址：`http://127.0.0.1:8000`
- 请求格式：`application/json`
- 控制链路：HTTP -> Mac API -> ZMQ -> Pi `lekiwi_host` -> 机器人

## 启动方式

```bash
python examples/alohamini/base_control_api.py \
  --remote_ip <树莓派IP> \
  --http_host 127.0.0.1 \
  --http_port 8000
```

可选参数：

- `--send_hz`：底盘命令持续发送频率，默认 `20`
- `--source`：仲裁来源标识，默认 `api_http`
- `--lease_ms`：控制权租约时长（毫秒），默认 `1200`
- `--priority`：控制权优先级，默认 `100`（数值越大优先级越高）

## 接口列表

### 1) 状态查询

#### `GET /health` 或 `GET /status`

返回当前控制状态。

示例：

```bash
curl http://127.0.0.1:8000/health
```

返回示例：

```json
{
  "ok": true,
  "cmd": {
    "x_vel": 0.2,
    "y_vel": 0.0,
    "theta_vel": 0.0
  },
  "lift_active": true,
  "lift_vel_cmd": 500.0,
  "last_update_s": 1711111111.11,
  "control_active": true
}
```

---

### 2) 底盘控制

#### `POST /move`

设置底盘速度并持续生效，直到再次调用 `/move` 或 `/stop`。

请求字段（支持两套别名）：

- `x` 或 `x_vel`：前后速度，单位 `m/s`
- `y` 或 `y_vel`：横移速度，单位 `m/s`
- `theta` 或 `theta_vel`：旋转角速度，单位 `deg/s`

示例：

```bash
curl -X POST http://127.0.0.1:8000/move \
  -H "Content-Type: application/json" \
  -d '{"x":0.2,"y":0,"theta":0}'
```

#### `POST /stop`

停止底盘（将 `x/y/theta` 速度置 0）。

```bash
curl -X POST http://127.0.0.1:8000/stop
```

#### `POST /release`

释放底盘控制权（允许其他控制源接管，如键盘遥控）。

```bash
curl -X POST http://127.0.0.1:8000/release
```

---

### 3) 升降轴控制

#### `POST /lift`

控制升降轴（对应原键盘 `U/J` 行为）。

当前使用**速度控制模式**，支持两种写法：

1. `direction + speed`
2. 直接给 `velocity`（可正可负）

上升（等价按住 U）：

```bash
curl -X POST http://127.0.0.1:8000/lift \
  -H "Content-Type: application/json" \
  -d '{"direction":"up","speed":600}'
```

下降（等价按住 J）：

```bash
curl -X POST http://127.0.0.1:8000/lift \
  -H "Content-Type: application/json" \
  -d '{"direction":"down","speed":600}'
```

停止升降（速度置 0）：

```bash
curl -X POST http://127.0.0.1:8000/lift \
  -H "Content-Type: application/json" \
  -d '{"stop":true}'
```

参数说明：

- `direction`：`up` 或 `down`
- `speed`：速度大小（默认 `500`）
- `velocity`：直接速度值（正上升，负下降）
- `stop`：`true` 表示停止升降

---

### 4) 音频控制

#### `POST /audio/play`

播放音频文件。

```bash
curl -X POST http://127.0.0.1:8000/audio/play \
  -H "Content-Type: application/json" \
  -d '{"file":"welcome/ttsmaker-file-2026-3-26-20-6-31.mp3"}'
```

#### `POST /audio/stop`

停止当前音频播放。

```bash
curl -X POST http://127.0.0.1:8000/audio/stop
```

---

### 5) 手势控制（双臂镜像打招呼）

#### `POST /gesture/greet`

触发机器人左右臂镜像挥手动作（无需遥操作主臂）。

```bash
curl -X POST http://127.0.0.1:8000/gesture/greet \
  -H "Content-Type: application/json" \
  -d '{"waves":2,"speed_scale":1.0}'
```

参数说明：

- `waves`：挥手次数，默认 `2`
- `speed_scale`：动作速度倍率，默认 `1.0`（越大越快）

#### `POST /gesture/stop`

中断当前手势动作。

```bash
curl -X POST http://127.0.0.1:8000/gesture/stop
```

## 音频文件路径规则

Pi 端音频目录默认位于项目根目录下：

`<项目根目录>/audio`

`/audio/play` 的 `file` 建议使用相对路径（相对于上面的目录）：

- 示例传参：`"welcome/a.mp3"`
- 实际播放路径示例：`~/VoltNest/audio/welcome/a.mp3`

## 常见错误码

- `200`：成功（`{"ok": true, ...}`）
- `400`：请求参数错误
  - `invalid_json`
  - `missing_file`
  - `invalid_lift_payload`
- `404`：接口不存在（`not_found`）
- `500`：服务内部错误

## 注意事项

- 底盘控制是持续发送机制，未调用 `/stop` 前会保持当前速度。
- 升降也是持续速度控制，未发送 `{"stop":true}` 前会持续运动。
- 手势控制在 Pi 端本地执行，不依赖遥操主臂持续输入。
- 如需把底盘交回键盘控制，请调用 `/release`。
- 音频播放依赖 `ffplay`（通常来自 `ffmpeg`）。若未安装，播放会失败。

