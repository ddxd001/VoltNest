#!/usr/bin/env python

# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import json
import logging
import math
import time
import sys
import threading
import os
import subprocess

import cv2
import zmq
from pathlib import Path

from .config_lekiwi import LeKiwiConfig, LeKiwiHostConfig
from .lekiwi import LeKiwi

_BASE_KEYS = ("x.vel", "y.vel", "theta.vel")
_ARB_META_KEYS = ("__source", "__base_claim", "__base_release", "__base_lease_ms", "__base_priority")
_LEFT_ARM_KEYS = (
    "arm_left_shoulder_pan.pos",
    "arm_left_shoulder_lift.pos",
    "arm_left_elbow_flex.pos",
    "arm_left_wrist_flex.pos",
    "arm_left_wrist_roll.pos",
    "arm_left_gripper.pos",
)
_RIGHT_ARM_KEYS = (
    "arm_right_shoulder_pan.pos",
    "arm_right_shoulder_lift.pos",
    "arm_right_elbow_flex.pos",
    "arm_right_wrist_flex.pos",
    "arm_right_wrist_roll.pos",
    "arm_right_gripper.pos",
)
_BOTH_ARM_KEYS = _LEFT_ARM_KEYS + _RIGHT_ARM_KEYS


class BaseControlArbitrator:
    """Arbitrate who can command base velocity keys in multi-client scenarios."""

    def __init__(self, default_lease_ms: int = 1200, default_priority: int = 10):
        self.default_lease_ms = int(default_lease_ms)
        self.default_priority = int(default_priority)
        self.owner_source: str | None = None
        self.owner_priority: int = self.default_priority
        self.owner_expire_at: float = 0.0

    def _clear_owner(self) -> None:
        self.owner_source = None
        self.owner_priority = self.default_priority
        self.owner_expire_at = 0.0

    def _check_owner_expired(self, now: float) -> None:
        if self.owner_source is not None and now >= self.owner_expire_at:
            logging.info("[ARB] Base owner '%s' lease expired", self.owner_source)
            self._clear_owner()

    def _pick_meta(self, data: dict) -> tuple[str, bool, bool, int, int]:
        source = str(data.get("__source", "teleop"))
        claim = bool(data.get("__base_claim", False))
        release = bool(data.get("__base_release", False))
        lease_ms = int(data.get("__base_lease_ms", self.default_lease_ms))
        priority = int(data.get("__base_priority", self.default_priority))
        if lease_ms <= 0:
            lease_ms = self.default_lease_ms
        return source, claim, release, lease_ms, priority

    def _strip_meta(self, data: dict) -> dict:
        return {k: v for k, v in data.items() if k not in _ARB_META_KEYS}

    def filter_action(self, data: dict) -> dict:
        """Return action with unauthorized base keys removed, then meta keys stripped."""
        now = time.time()
        self._check_owner_expired(now)
        source, claim, release, lease_ms, priority = self._pick_meta(data)
        has_base_cmd = any(k in data for k in _BASE_KEYS)

        if release and self.owner_source == source:
            logging.info("[ARB] '%s' released base control", source)
            self._clear_owner()

        if not has_base_cmd:
            return self._strip_meta(data)

        allow_base = False
        if self.owner_source is None:
            allow_base = True
            if claim:
                self.owner_source = source
                self.owner_priority = priority
                self.owner_expire_at = now + lease_ms / 1000.0
                logging.info(
                    "[ARB] '%s' acquired base control (priority=%s, lease_ms=%s)",
                    source,
                    priority,
                    lease_ms,
                )
        elif self.owner_source == source:
            allow_base = True
            if claim:
                self.owner_expire_at = now + lease_ms / 1000.0
                self.owner_priority = priority
        elif claim and priority > self.owner_priority:
            logging.info(
                "[ARB] '%s' preempted '%s' for base control (priority %s > %s)",
                source,
                self.owner_source,
                priority,
                self.owner_priority,
            )
            self.owner_source = source
            self.owner_priority = priority
            self.owner_expire_at = now + lease_ms / 1000.0
            allow_base = True
        else:
            allow_base = False

        out = self._strip_meta(data)
        if not allow_base:
            for k in _BASE_KEYS:
                out.pop(k, None)
        return out


class LeKiwiHost:
    def __init__(self, config: LeKiwiHostConfig):
        self.zmq_context = zmq.Context()
        self.zmq_cmd_socket = self.zmq_context.socket(zmq.PULL)
        self.zmq_cmd_socket.setsockopt(zmq.CONFLATE, 1)
        self.zmq_cmd_socket.bind(f"tcp://*:{config.port_zmq_cmd}")

        self.zmq_observation_socket = self.zmq_context.socket(zmq.PUSH)
        self.zmq_observation_socket.setsockopt(zmq.CONFLATE, 1)
        self.zmq_observation_socket.bind(f"tcp://*:{config.port_zmq_observations}")

        self.connection_time_s = config.connection_time_s
        self.watchdog_timeout_ms = config.watchdog_timeout_ms
        self.max_loop_freq_hz = config.max_loop_freq_hz

    def disconnect(self):
        self.zmq_observation_socket.close()
        self.zmq_cmd_socket.close()
        self.zmq_context.term()


class VideoPlayer:
    """视频播放器类，支持动态切换视频（播放列表循环模式，手动切换）"""
    def __init__(self, video_dir: str):
        self.video_dir = video_dir
        self.current_video_index = 0
        self.vlc_process = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.playlist_file = None
        
        # 获取所有视频文件
        self.video_files = sorted([f for f in os.listdir(video_dir) if f.endswith('.mp4')])
        if not self.video_files:
            raise ValueError(f"No video files found in {video_dir}")
        
        print(f"[VIDEO] Found {len(self.video_files)} videos: {self.video_files}", flush=True)
        
        # 创建播放列表文件
        self._create_playlist()
    
    def _create_playlist(self):
        """创建 M3U 播放列表文件"""
        import tempfile
        self.playlist_file = tempfile.NamedTemporaryFile(mode='w', suffix='.m3u', delete=False)
        self.playlist_file.write("#EXTM3U\n")
        for video_file in self.video_files:
            video_path = os.path.join(self.video_dir, video_file)
            self.playlist_file.write(f"{video_path}\n")
        self.playlist_file.close()
        print(f"[VIDEO] Playlist created: {self.playlist_file.name}", flush=True)
    
    def get_current_video_name(self):
        return self.video_files[self.current_video_index]
    
    def switch_to_next(self):
        """切换到下一个视频（使用 DBus 控制，无需重启进程）"""
        with self.lock:
            old_index = self.current_video_index
            self.current_video_index = (self.current_video_index + 1) % len(self.video_files)
            print(f"[VIDEO] Switching to next: {self.current_video_index + 1}/{len(self.video_files)}: {self.video_files[self.current_video_index]}", flush=True)
            self._send_dbus_command("Next")
    
    def switch_to_previous(self):
        """切换到上一个视频（使用 DBus 控制，无需重启进程）"""
        with self.lock:
            old_index = self.current_video_index
            self.current_video_index = (self.current_video_index - 1) % len(self.video_files)
            print(f"[VIDEO] Switching to previous: {self.current_video_index + 1}/{len(self.video_files)}: {self.video_files[self.current_video_index]}", flush=True)
            self._send_dbus_command("Previous")
    
    def _send_dbus_command(self, command):
        """通过 DBus 发送控制命令到 VLC"""
        try:
            # 使用 dbus-send 命令控制 VLC
            subprocess.run([
                "dbus-send",
                "--type=method_call",
                "--dest=org.mpris.MediaPlayer2.vlc",
                "/org/mpris/MediaPlayer2",
                f"org.mpris.MediaPlayer2.Player.{command}"
            ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=0.5)
        except Exception as e:
            print(f"[VIDEO] DBus command failed: {e}", flush=True)
    
    def _stop_current_vlc(self):
        """停止当前VLC进程"""
        if self.vlc_process and self.vlc_process.poll() is None:
            print(f"[VIDEO] Stopping VLC process...", flush=True)
            self.vlc_process.terminate()
            try:
                self.vlc_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                print(f"[VIDEO] VLC didn't terminate, killing...", flush=True)
                self.vlc_process.kill()
    
    def _start_vlc_with_playlist(self):
        """启动VLC播放整个播放列表（单曲循环模式）"""
        vlc_cmd = [
            "cvlc",
            "--fullscreen",
            "--repeat",  # 单曲循环（不自动切换到下一首）
            "--no-video-title-show",
            "--no-osd",
            "--quiet",
            "--no-random",
            "--playlist-autostart",
            self.playlist_file.name
        ]
        
        self.vlc_process = subprocess.Popen(
            vlc_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, 'DISPLAY': os.environ.get('DISPLAY', ':0')}
        )
        print(f"[VIDEO] VLC started with playlist (PID: {self.vlc_process.pid})", flush=True)
        
        # 等待 VLC 启动并跳转到初始视频
        time.sleep(1.5)
        if self.current_video_index > 0:
            for _ in range(self.current_video_index):
                self._send_dbus_command("Next")
                time.sleep(0.1)
    
    def run(self):
        """视频播放主循环（播放列表模式，DBus 控制切换）"""
        print(f"[VIDEO] Player thread started (playlist mode with manual switching)", flush=True)
        
        try:
            # 启动 VLC 播放列表（只启动一次）
            self._start_vlc_with_playlist()
            
            # 保持运行，监控 VLC 进程
            while not self.stop_event.is_set():
                # 检查VLC是否还在运行
                if self.vlc_process.poll() is not None:
                    print(f"[VIDEO] VLC exited unexpectedly, restarting...", flush=True)
                    self._start_vlc_with_playlist()
                
                time.sleep(0.5)
            
            print(f"[VIDEO] Player stopped", flush=True)
            
        except Exception as e:
            print(f"[VIDEO ERROR] Player error: {e}", flush=True)
            logging.error(f"Video player error: {e}")
    
    def stop(self):
        """停止视频播放"""
        print(f"[VIDEO] Stopping player...", flush=True)
        self.stop_event.set()
        self._stop_current_vlc()
        
        # 清理播放列表文件
        if self.playlist_file and os.path.exists(self.playlist_file.name):
            try:
                os.unlink(self.playlist_file.name)
                print(f"[VIDEO] Playlist file cleaned up", flush=True)
            except Exception as e:
                print(f"[VIDEO] Failed to clean up playlist: {e}", flush=True)
 

class AudioPlayer:
    """Simple audio player wrapper using ffplay."""

    def __init__(self, audio_dir: str):
        self.audio_dir = Path(audio_dir).expanduser().resolve()
        self.process: subprocess.Popen | None = None
        self._set_system_volume_max()

    def _resolve_audio_file(self, file_name: str) -> Path | None:
        p = Path(file_name)
        if not p.is_absolute():
            p = (self.audio_dir / p).resolve()
        else:
            p = p.resolve()

        # Keep playback constrained under configured audio directory when using relative file names.
        if not str(p).startswith(str(self.audio_dir)):
            return None
        if not p.exists() or not p.is_file():
            return None
        return p

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None

    def _set_system_volume_max(self) -> None:
        """Best-effort: maximize output volume on Raspberry Pi."""
        commands = [
            ["amixer", "-q", "sset", "Master", "100%", "unmute"],
            ["amixer", "-q", "sset", "PCM", "100%", "unmute"],
            ["amixer", "-q", "sset", "Speaker", "100%", "unmute"],
        ]
        for cmd in commands:
            try:
                subprocess.run(
                    cmd,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=0.5,
                )
            except Exception:
                pass

    def play(self, file_name: str) -> tuple[bool, str]:
        target = self._resolve_audio_file(file_name)
        if target is None:
            return False, f"Audio file not found or not allowed: {file_name}"

        self.stop()
        self._set_system_volume_max()
        try:
            self.process = subprocess.Popen(
                [
                    "ffplay",
                    "-nodisp",
                    "-autoexit",
                    "-volume",
                    "100",
                    "-loglevel",
                    "error",
                    str(target),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True, f"Playing audio: {target.name}"
        except FileNotFoundError:
            return False, "ffplay not found; please install ffmpeg"
        except Exception as e:
            return False, f"Failed to play audio: {e}"


class GestureController:
    """Generate predefined mirrored dual-arm gestures locally on Pi side."""

    def __init__(self) -> None:
        self.active = False
        self.start_time = 0.0
        self.waves = 2
        self.speed_scale = 1.0
        self.base_pose: dict[str, float] = {}
        self.raised_pose: dict[str, float] = {}
        self.wave_amplitude_deg = 14.0

    def _lerp_pose(self, a: dict[str, float], b: dict[str, float], alpha: float) -> dict[str, float]:
        alpha = max(0.0, min(1.0, alpha))
        out: dict[str, float] = {}
        for k in _BOTH_ARM_KEYS:
            out[k] = float(a.get(k, 0.0) + (b.get(k, 0.0) - a.get(k, 0.0)) * alpha)
        return out

    def _build_raised_pose(self, base: dict[str, float]) -> dict[str, float]:
        pose = dict(base)
        # Apply same amplitude on both arms; mirror is handled in pan oscillation.
        pose["arm_left_shoulder_lift.pos"] = base["arm_left_shoulder_lift.pos"] + 7.0
        pose["arm_left_elbow_flex.pos"] = base["arm_left_elbow_flex.pos"] - 40.0
        pose["arm_left_wrist_flex.pos"] = base["arm_left_wrist_flex.pos"] + 5.0

        pose["arm_right_shoulder_lift.pos"] = base["arm_right_shoulder_lift.pos"] + 7.0
        pose["arm_right_elbow_flex.pos"] = base["arm_right_elbow_flex.pos"] - 40.0
        pose["arm_right_wrist_flex.pos"] = base["arm_right_wrist_flex.pos"] + 5.0
        return pose

    def start_greet(self, observation: dict, waves: int = 2, speed_scale: float = 1.0) -> tuple[bool, str]:
        missing = [k for k in _BOTH_ARM_KEYS if k not in observation]
        if missing:
            return False, f"Missing arm observation keys: {missing[:2]}"

        self.base_pose = {k: float(observation[k]) for k in _BOTH_ARM_KEYS}
        self.raised_pose = self._build_raised_pose(self.base_pose)
        self.waves = max(1, min(int(waves), 6))
        self.speed_scale = max(0.3, min(float(speed_scale), 3.0))
        self.start_time = time.time()
        self.active = True
        return True, f"Greet started (waves={self.waves}, speed_scale={self.speed_scale:.2f})"

    def stop(self) -> None:
        self.active = False

    def update(self, now_s: float) -> dict[str, float]:
        if not self.active:
            return {}

        t = (now_s - self.start_time) * self.speed_scale
        raise_dur = 0.45
        wave_period = 0.45
        wave_dur = wave_period * self.waves
        return_dur = 0.45
        total = raise_dur + wave_dur + return_dur

        if t >= total:
            self.active = False
            return {}

        if t < raise_dur:
            return self._lerp_pose(self.base_pose, self.raised_pose, t / raise_dur)

        if t < raise_dur + wave_dur:
            tau = t - raise_dur
            # Mirror pan oscillation: left/right move opposite directions.
            phase = 2.0 * 3.1415926 * (tau / wave_period)
            pose = dict(self.raised_pose)
            pose["arm_left_shoulder_pan.pos"] = self.raised_pose["arm_left_shoulder_pan.pos"] - self.wave_amplitude_deg * math.sin(
                phase
            )
            pose["arm_right_shoulder_pan.pos"] = self.raised_pose["arm_right_shoulder_pan.pos"] + self.wave_amplitude_deg * math.sin(
                phase
            )
            return pose

        return self._lerp_pose(self.raised_pose, self.base_pose, (t - raise_dur - wave_dur) / return_dur)


def main():
    logging.info("Configuring LeKiwi")
    robot_config = LeKiwiConfig()
    robot_config.id = "AlohaMiniRobot"
    robot = LeKiwi(robot_config)


    logging.info("Connecting AlohaMini")
    robot.connect()

    logging.info("Starting HostAgent")
    host_config = LeKiwiHostConfig()
    host_config.video_path = "/home/ubuntu/lerobot_alohamini/face_video"
    host_config.enable_video_playback = True
    host = LeKiwiHost(host_config)

    print(f"[CONFIG] Video playback enabled: {host_config.enable_video_playback}", flush=True)
    print(f"[CONFIG] Video directory: {host_config.video_path}", flush=True)

    video_player = None
    video_thread = None
    audio_player = None
    gesture_controller = GestureController()
    arbitrator = BaseControlArbitrator(default_lease_ms=1200, default_priority=10)
    # Use project-root-relative audio directory to avoid hardcoded project name.
    audio_dir = os.path.join(os.getcwd(), "audio")
    
    if host_config.enable_video_playback and host_config.video_path:
        print(f"[MAIN] Starting video player thread...", flush=True)
        try:
            video_player = VideoPlayer(host_config.video_path)
            video_thread = threading.Thread(
                target=video_player.run,
                daemon=True
            )
            video_thread.start()
            print(f"[MAIN] Video player started successfully", flush=True)
            time.sleep(0.5)
        except Exception as e:
            print(f"[MAIN ERROR] Failed to start video player: {e}", flush=True)
            video_player = None
    else:
        print(f"[MAIN] Video playback NOT enabled or path not set", flush=True)

    try:
        audio_player = AudioPlayer(audio_dir)
        print(f"[AUDIO] Audio control enabled, directory: {audio_dir}", flush=True)
    except Exception as e:
        logging.warning(f"Failed to initialize audio player: {e}")
        audio_player = None

    last_cmd_time = time.time()
    watchdog_active = False
    logging.info("Waiting for commands...")

    try:
        # Business logic
        start = time.perf_counter()
        duration = 0
        last_observation: dict = {}

        while duration < host.connection_time_s:
            loop_start_time = time.time()
            data: dict = {}
            try:
                msg = host.zmq_cmd_socket.recv_string(zmq.NOBLOCK)
                data = dict(json.loads(msg))
                data = arbitrator.filter_action(data)

                gesture_cmd = str(data.pop("__gesture", "")).strip().lower()
                if gesture_cmd:
                    if gesture_cmd == "greet":
                        waves = int(data.pop("__gesture_waves", 2))
                        speed_scale = float(data.pop("__gesture_speed_scale", 1.0))
                        ok, message = gesture_controller.start_greet(last_observation, waves=waves, speed_scale=speed_scale)
                        print(f"[GESTURE] {message}", flush=True)
                        if not ok:
                            logging.warning(message)
                    elif gesture_cmd == "stop":
                        gesture_controller.stop()
                        print("[GESTURE] Stopped", flush=True)

                audio_play_file = data.pop("__audio_play", None)
                audio_stop = bool(data.pop("__audio_stop", False))
                if audio_player is not None:
                    if audio_stop:
                        audio_player.stop()
                        print("[AUDIO] Stopped", flush=True)
                    if audio_play_file:
                        ok, message = audio_player.play(str(audio_play_file))
                        print(f"[AUDIO] {message}", flush=True)
                        if not ok:
                            logging.warning(message)
                
                # 检查是否有视频切换命令
                if video_player:
                    if "video_next" in data and data["video_next"]:
                        video_player.switch_to_next()
                    elif "video_prev" in data and data["video_prev"]:
                        video_player.switch_to_previous()

                last_cmd_time = time.time()
                watchdog_active = False
            except zmq.Again:
                if not watchdog_active:
                    logging.warning("No command available")
            except Exception as e:
                logging.exception("Message fetching failed: %s", e)

            gesture_action = gesture_controller.update(time.time())
            if gesture_action:
                data.update(gesture_action)

            if data:
                # Ensure base keys exist to satisfy robot.send_action() assumptions.
                for k in _BASE_KEYS:
                    data.setdefault(k, 0.0)
                _action_sent = robot.send_action(data)

            now = time.time()
            if (now - last_cmd_time > host.watchdog_timeout_ms / 1000) and not watchdog_active:
                logging.warning(
                    f"Command not received for more than {host.watchdog_timeout_ms} milliseconds. Stopping the base."
                )
                watchdog_active = True
                robot.stop_base()

            
            robot.lift.update()
            last_observation = robot.get_observation()

            # Encode ndarrays to base64 strings
            for cam_key, _ in robot.cameras.items():
                ret, buffer = cv2.imencode(
                    ".jpg", last_observation[cam_key], [int(cv2.IMWRITE_JPEG_QUALITY), 90]
                )
                if ret:
                    last_observation[cam_key] = base64.b64encode(buffer).decode("utf-8")
                else:
                    last_observation[cam_key] = ""

            # Send the observation to the remote agent
            try:
                host.zmq_observation_socket.send_string(json.dumps(last_observation), flags=zmq.NOBLOCK)
            except zmq.Again:
                logging.info("Dropping observation, no client connected")

            # Ensure a short sleep to avoid overloading the CPU.
            elapsed = time.time() - loop_start_time

            time.sleep(max(1 / host.max_loop_freq_hz - elapsed, 0))
            duration = time.perf_counter() - start
        print("Cycle time reached.")

    except KeyboardInterrupt:
        print("Keyboard interrupt received. Exiting...")
    except SystemExit:
        print("System exit triggered (likely due to overcurrent protection).")
    finally:
        print("Shutting down AlohaMini Host.")
        
        if video_player:
            logging.info("Stopping video playback...")
            video_player.stop()
            if video_thread and video_thread.is_alive():
                video_thread.join(timeout=2)

        if audio_player:
            try:
                audio_player.stop()
            except Exception as e:
                logging.warning(f"Error during audio stop: {e}")
        
        try:
            robot.disconnect()
        except Exception as e:
            logging.warning(f"Error during robot disconnect: {e}")
        
        try:
            host.disconnect()
        except Exception as e:
            logging.warning(f"Error during host disconnect: {e}")

    logging.info("Finished AlohaMini cleanly")


if __name__ == "__main__":
    main()
