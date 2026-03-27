#!/usr/bin/env python3
"""
HTTP control interface for AlohaMini base (chassis) movement.

This script runs on the Mac side and reuses the existing ZMQ protocol:
Mac -> (ZMQ PUSH) -> Pi host -> LeKiwi base motors

Why we need a background sender:
The Pi host has a watchdog (default ~1.5s). If commands stop arriving, the base is stopped.
So we continuously publish the latest base velocity command at a fixed rate.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from typing import Any, TYPE_CHECKING

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    # Allow running this script without `pip install -e .`
    sys.path.insert(0, str(_SRC_DIR))

if TYPE_CHECKING:
    from lerobot.robots.alohamini import LeKiwiClient


class _SharedState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.x_vel_mps: float = 0.0
        self.y_vel_mps: float = 0.0
        self.theta_vel_degps: float = 0.0
        self.timed_move_queue: list[dict[str, float]] = []
        self.active_timed_move: dict[str, float] | None = None
        self.active_timed_move_end_s: float = 0.0
        self.active_timed_move_started_s: float = 0.0
        self.lift_vel_cmd: float = 0.0
        self.lift_active: bool = False
        self.lift_stop_once: bool = False
        self.last_update_s: float = time.time()
        self.control_active: bool = False
        self.release_once: bool = False
        self.pending_once_commands: list[dict[str, Any]] = []
        self.gesture_active: bool = False
        self.gesture_last: str = "idle"

    def set_cmd(self, x: float, y: float, theta: float, active: bool = True) -> None:
        with self._lock:
            # Manual velocity command interrupts timed queue execution.
            self.timed_move_queue.clear()
            self.active_timed_move = None
            self.active_timed_move_end_s = 0.0
            self.active_timed_move_started_s = 0.0
            self.x_vel_mps = float(x)
            self.y_vel_mps = float(y)
            self.theta_vel_degps = float(theta)
            self.last_update_s = time.time()
            self.control_active = bool(active)
            self.release_once = False

    def stop_cmd(self) -> None:
        with self._lock:
            self.timed_move_queue.clear()
            self.active_timed_move = None
            self.active_timed_move_end_s = 0.0
            self.active_timed_move_started_s = 0.0
            self.x_vel_mps = 0.0
            self.y_vel_mps = 0.0
            self.theta_vel_degps = 0.0
            self.last_update_s = time.time()
            self.control_active = True
            self.release_once = False

    def release_control(self) -> None:
        with self._lock:
            self.timed_move_queue.clear()
            self.active_timed_move = None
            self.active_timed_move_end_s = 0.0
            self.active_timed_move_started_s = 0.0
            self.x_vel_mps = 0.0
            self.y_vel_mps = 0.0
            self.theta_vel_degps = 0.0
            self.last_update_s = time.time()
            self.control_active = False
            self.release_once = True

    def enqueue_timed_move(self, x: float, y: float, theta: float, duration_s: float) -> int:
        with self._lock:
            self.timed_move_queue.append(
                {
                    "x": float(x),
                    "y": float(y),
                    "theta": float(theta),
                    "duration_s": float(duration_s),
                }
            )
            return len(self.timed_move_queue) + (1 if self.active_timed_move is not None else 0)

    def _advance_timed_move_locked(self, now_s: float) -> None:
        # End current segment if finished.
        if self.active_timed_move is not None and now_s >= self.active_timed_move_end_s:
            self.active_timed_move = None
            self.active_timed_move_end_s = 0.0
            self.active_timed_move_started_s = 0.0
            self.x_vel_mps = 0.0
            self.y_vel_mps = 0.0
            self.theta_vel_degps = 0.0
            self.control_active = True

        # Start next queued segment if idle.
        if self.active_timed_move is None and self.timed_move_queue:
            seg = self.timed_move_queue.pop(0)
            self.active_timed_move = seg
            self.active_timed_move_started_s = now_s
            self.active_timed_move_end_s = now_s + float(seg["duration_s"])
            self.x_vel_mps = float(seg["x"])
            self.y_vel_mps = float(seg["y"])
            self.theta_vel_degps = float(seg["theta"])
            self.control_active = True

    def queue_once_command(self, cmd: dict[str, Any]) -> None:
        with self._lock:
            self.pending_once_commands.append(dict(cmd))

    def queue_gesture_greet(self, waves: int, speed_scale: float) -> None:
        with self._lock:
            self.pending_once_commands.append(
                {"__gesture": "greet", "__gesture_waves": int(waves), "__gesture_speed_scale": float(speed_scale)}
            )
            self.gesture_active = True
            self.gesture_last = "greet"

    def queue_gesture_stop(self) -> None:
        with self._lock:
            self.pending_once_commands.append({"__gesture": "stop"})
            self.gesture_active = False
            self.gesture_last = "stop"

    def set_lift_velocity(self, velocity: float) -> float:
        with self._lock:
            self.lift_vel_cmd = float(velocity)
            self.lift_active = True
            self.lift_stop_once = False
            return self.lift_vel_cmd

    def stop_lift(self) -> None:
        with self._lock:
            self.lift_vel_cmd = 0.0
            self.lift_active = False
            self.lift_stop_once = True

    def consume_sender_state(
        self,
    ) -> tuple[float, float, float, float, bool, bool, list[dict[str, Any]], bool, bool, float]:
        with self._lock:
            self._advance_timed_move_locked(time.time())
            once_cmds = list(self.pending_once_commands)
            self.pending_once_commands.clear()
            do_release = self.release_once
            if self.release_once:
                self.release_once = False
            do_lift_stop_once = self.lift_stop_once
            if self.lift_stop_once:
                self.lift_stop_once = False
            return (
                float(self.x_vel_mps),
                float(self.y_vel_mps),
                float(self.theta_vel_degps),
                float(self.last_update_s),
                bool(self.control_active),
                bool(do_release),
                once_cmds,
                bool(self.lift_active),
                bool(do_lift_stop_once),
                float(self.lift_vel_cmd),
            )

    def snapshot(self) -> tuple[float, float, float, float, bool, bool, float, bool, str, bool, int, float]:
        with self._lock:
            now_s = time.time()
            queued = len(self.timed_move_queue)
            timed_active = self.active_timed_move is not None
            remaining_s = max(self.active_timed_move_end_s - now_s, 0.0) if timed_active else 0.0
            return (
                float(self.x_vel_mps),
                float(self.y_vel_mps),
                float(self.theta_vel_degps),
                float(self.last_update_s),
                bool(self.control_active),
                bool(self.lift_active),
                float(self.lift_vel_cmd),
                bool(self.gesture_active),
                str(self.gesture_last),
                bool(timed_active),
                int(queued),
                float(remaining_s),
            )


def _parse_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _write_json(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = (json.dumps(payload, ensure_ascii=True) + "\n").encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def make_handler(state: _SharedState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            # Keep stdout clean; override if you want access logs.
            return

        def do_GET(self) -> None:
            if self.path.rstrip("/") in ("", "/health", "/status"):
                x, y, th, ts, active, lift_active, lift_vel, gesture_active, gesture_last, timed_active, timed_queue_len, timed_remaining_s = state.snapshot()
                _write_json(
                    self,
                    200,
                    {
                        "ok": True,
                        "cmd": {"x_vel": x, "y_vel": y, "theta_vel": th},
                        "lift_active": lift_active,
                        "lift_vel_cmd": lift_vel,
                        "gesture_active": gesture_active,
                        "gesture_last": gesture_last,
                        "timed_move_active": timed_active,
                        "timed_move_queue_len": timed_queue_len,
                        "timed_move_remaining_s": timed_remaining_s,
                        "last_update_s": ts,
                        "control_active": active,
                    },
                )
                return

            _write_json(self, 404, {"ok": False, "error": "not_found"})

        def do_POST(self) -> None:
            try:
                if self.path.rstrip("/") == "/move":
                    data = _parse_json_body(self)
                    # Accept either x/y/theta or x_vel/y_vel/theta_vel.
                    x = data.get("x", data.get("x_vel", 0.0))
                    y = data.get("y", data.get("y_vel", 0.0))
                    th = data.get("theta", data.get("theta_vel", 0.0))
                    state.set_cmd(x, y, th, active=True)
                    _write_json(self, 200, {"ok": True})
                    return

                if self.path.rstrip("/") == "/stop":
                    state.stop_cmd()
                    _write_json(self, 200, {"ok": True})
                    return

                if self.path.rstrip("/") == "/release":
                    state.release_control()
                    _write_json(self, 200, {"ok": True})
                    return

                if self.path.rstrip("/") == "/move_timed":
                    data = _parse_json_body(self)
                    x = float(data.get("x", data.get("x_vel", 0.0)))
                    y = float(data.get("y", data.get("y_vel", 0.0)))
                    th = float(data.get("theta", data.get("theta_vel", 0.0)))
                    duration_s = float(data.get("duration_s", data.get("duration", 0.0)))
                    if duration_s <= 0:
                        _write_json(self, 400, {"ok": False, "error": "invalid_duration", "hint": "duration_s must be > 0"})
                        return
                    total_pending = state.enqueue_timed_move(x, y, th, duration_s)
                    _write_json(
                        self,
                        200,
                        {
                            "ok": True,
                            "queued": True,
                            "pending_segments": int(total_pending),
                            "segment": {"x": x, "y": y, "theta": th, "duration_s": duration_s},
                        },
                    )
                    return

                if self.path.rstrip("/") == "/lift":
                    data = _parse_json_body(self)
                    if bool(data.get("stop", False)):
                        state.stop_lift()
                        _write_json(self, 200, {"ok": True, "lift_active": False, "lift_vel_cmd": 0.0})
                        return

                    direction = str(data.get("direction", "")).strip().lower()
                    speed = float(data.get("speed", data.get("velocity", 500.0)))

                    if direction in ("up", "down"):
                        vel = abs(speed) if direction == "up" else -abs(speed)
                        vel = state.set_lift_velocity(vel)
                        _write_json(self, 200, {"ok": True, "lift_active": True, "lift_vel_cmd": vel})
                        return

                    if "velocity" in data or "speed" in data:
                        vel = state.set_lift_velocity(speed)
                        _write_json(self, 200, {"ok": True, "lift_active": True, "lift_vel_cmd": vel})
                        return

                    _write_json(self, 400, {"ok": False, "error": "invalid_lift_payload", "hint": "use direction/speed or stop"})
                    return

                if self.path.rstrip("/") == "/audio/play":
                    data = _parse_json_body(self)
                    file_name = str(data.get("file", "")).strip()
                    if not file_name:
                        _write_json(self, 400, {"ok": False, "error": "missing_file"})
                        return
                    state.queue_once_command({"__audio_play": file_name})
                    _write_json(self, 200, {"ok": True, "file": file_name})
                    return

                if self.path.rstrip("/") == "/audio/stop":
                    state.queue_once_command({"__audio_stop": True})
                    _write_json(self, 200, {"ok": True})
                    return

                if self.path.rstrip("/") == "/gesture/greet":
                    data = _parse_json_body(self)
                    waves = int(data.get("waves", 2))
                    speed_scale = float(data.get("speed_scale", 1.0))
                    state.queue_gesture_greet(waves=waves, speed_scale=speed_scale)
                    _write_json(
                        self,
                        200,
                        {"ok": True, "gesture": "greet", "waves": int(waves), "speed_scale": float(speed_scale)},
                    )
                    return

                if self.path.rstrip("/") == "/gesture/stop":
                    state.queue_gesture_stop()
                    _write_json(self, 200, {"ok": True, "gesture": "stop"})
                    return

                _write_json(self, 404, {"ok": False, "error": "not_found"})
            except json.JSONDecodeError:
                _write_json(self, 400, {"ok": False, "error": "invalid_json"})
            except Exception as e:
                _write_json(self, 500, {"ok": False, "error": str(e)})

    return Handler


def _sender_loop(
    robot: "LeKiwiClient",
    state: _SharedState,
    send_hz: float,
    stop_event: threading.Event,
    source: str,
    lease_ms: int,
    priority: int,
) -> None:
    period_s = 1.0 / max(send_hz, 1e-6)
    while not stop_event.is_set():
        t0 = time.perf_counter()
        x, y, th, _ts, active, do_release, once_cmds, lift_active, do_lift_stop_once, lift_vel = state.consume_sender_state()

        # IMPORTANT:
        # ZMQ sockets are configured with CONFLATE=1, so only the latest message survives.
        # Merge all command intents into a single action per loop to avoid dropping one-shot
        # commands (e.g. lift/audio) when base keepalive is enabled.
        action: dict[str, Any] = {}
        for cmd in once_cmds:
            action.update(cmd)

        if active:
            action.update(
                {
                    "x.vel": x,
                    "y.vel": y,
                    "theta.vel": th,
                    "__source": source,
                    "__base_claim": True,
                    "__base_lease_ms": int(lease_ms),
                    "__base_priority": int(priority),
                }
            )
        elif do_release:
            action.update(
                {
                    "x.vel": 0.0,
                    "y.vel": 0.0,
                    "theta.vel": 0.0,
                    "__source": source,
                    "__base_release": True,
                    "__base_priority": int(priority),
                }
            )

        if lift_active:
            action["lift_axis.vel"] = float(lift_vel)
        elif do_lift_stop_once:
            action["lift_axis.vel"] = 0.0

        if action:
            robot.send_action(action)
        dt = time.perf_counter() - t0
        time.sleep(max(period_s - dt, 0.0))


def main() -> int:
    ap = argparse.ArgumentParser(description="AlohaMini base HTTP control API (Mac side).")
    ap.add_argument("--remote_ip", type=str, required=True, help="Pi host IP address")
    ap.add_argument("--http_host", type=str, default="127.0.0.1", help="HTTP bind host")
    ap.add_argument("--http_port", type=int, default=8000, help="HTTP bind port")
    ap.add_argument("--send_hz", type=float, default=12.0, help="ZMQ command publish rate (Hz)")
    ap.add_argument("--source", type=str, default="api_http", help="Arbitration source id")
    ap.add_argument("--lease_ms", type=int, default=1200, help="Arbitration lease timeout in ms")
    ap.add_argument("--priority", type=int, default=100, help="Arbitration priority (higher wins)")
    args = ap.parse_args()

    # Delay heavy imports so `-h` works even if deps aren't installed yet.
    from lerobot.robots.alohamini import LeKiwiClient, LeKiwiClientConfig

    robot = LeKiwiClient(LeKiwiClientConfig(remote_ip=args.remote_ip, id="base_control_api"))
    robot.connect()

    state = _SharedState()
    stop_event = threading.Event()
    sender = threading.Thread(
        target=_sender_loop,
        args=(
            robot,
            state,
            float(args.send_hz),
            stop_event,
            str(args.source),
            int(args.lease_ms),
            int(args.priority),
        ),
        daemon=True,
    )
    sender.start()

    server = ThreadingHTTPServer((args.http_host, int(args.http_port)), make_handler(state))
    try:
        print(f"Base control API listening on http://{args.http_host}:{args.http_port}")
        print(
            "Endpoints: GET /health, POST /move, POST /move_timed, POST /stop, POST /release, POST /lift, POST /audio/play, POST /audio/stop, POST /gesture/greet, POST /gesture/stop"
        )
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        try:
            server.shutdown()
        except Exception:
            pass
        try:
            # Best-effort stop before disconnect.
            state.stop_cmd()
            time.sleep(0.05)
            robot.disconnect()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

