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
import time
import sys
import threading
import os
import subprocess

import cv2
import zmq

from .config_lekiwi import LeKiwiConfig, LeKiwiHostConfig
from .lekiwi import LeKiwi


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
    """视频播放器类，支持动态切换视频（单视频循环模式）"""
    def __init__(self, video_dir: str):
        self.video_dir = video_dir
        self.current_video_index = 0
        self.vlc_process = None
        self.stop_event = threading.Event()
        self.switch_event = threading.Event()
        self.lock = threading.Lock()
        
        # 获取所有视频文件
        self.video_files = sorted([f for f in os.listdir(video_dir) if f.endswith('.mp4')])
        if not self.video_files:
            raise ValueError(f"No video files found in {video_dir}")
        
        print(f"[VIDEO] Found {len(self.video_files)} videos: {self.video_files}", flush=True)
    
    def get_current_video_path(self):
        """获取当前视频的完整路径"""
        return os.path.join(self.video_dir, self.video_files[self.current_video_index])
    
    def get_current_video_name(self):
        """获取当前视频的文件名"""
        return self.video_files[self.current_video_index]
    
    def switch_to_next(self):
        """切换到下一个视频"""
        with self.lock:
            old_index = self.current_video_index
            self.current_video_index = (self.current_video_index + 1) % len(self.video_files)
            print(f"[VIDEO] Switching to next: {self.current_video_index + 1}/{len(self.video_files)}: {self.video_files[self.current_video_index]}", flush=True)
            self.switch_event.set()
    
    def switch_to_previous(self):
        """切换到上一个视频"""
        with self.lock:
            old_index = self.current_video_index
            self.current_video_index = (self.current_video_index - 1) % len(self.video_files)
            print(f"[VIDEO] Switching to previous: {self.current_video_index + 1}/{len(self.video_files)}: {self.video_files[self.current_video_index]}", flush=True)
            self.switch_event.set()
    
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
    
    def _start_vlc_single_video(self, video_path):
        """启动VLC播放单个视频（循环播放）"""
        vlc_cmd = [
            "cvlc",
            "--fullscreen",
            "--loop",  # 循环播放当前视频
            "--no-video-title-show",
            "--no-osd",
            "--quiet",
            video_path
        ]
        
        self.vlc_process = subprocess.Popen(
            vlc_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, 'DISPLAY': os.environ.get('DISPLAY', ':0')}
        )
        print(f"[VIDEO] VLC started (PID: {self.vlc_process.pid}): {os.path.basename(video_path)}", flush=True)
    
    def run(self):
        """视频播放主循环（单视频循环模式）"""
        print(f"[VIDEO] Player thread started (single video loop mode)", flush=True)
        
        try:
            while not self.stop_event.is_set():
                # 获取当前视频路径
                video_path = self.get_current_video_path()
                
                if not os.path.exists(video_path):
                    print(f"[VIDEO ERROR] Video not found: {video_path}", flush=True)
                    time.sleep(1)
                    continue
                
                # 启动VLC播放当前视频（循环播放）
                self._start_vlc_single_video(video_path)
                
                # 等待切换事件或停止事件
                while not self.stop_event.is_set() and not self.switch_event.is_set():
                    # 检查VLC是否还在运行
                    if self.vlc_process.poll() is not None:
                        print(f"[VIDEO] VLC exited unexpectedly, restarting...", flush=True)
                        break
                    time.sleep(0.1)
                
                # 停止当前VLC
                self._stop_current_vlc()
                
                # 清除切换事件标志
                self.switch_event.clear()
            
            print(f"[VIDEO] Player stopped", flush=True)
            
        except Exception as e:
            print(f"[VIDEO ERROR] Player error: {e}", flush=True)
            logging.error(f"Video player error: {e}")
    
    def stop(self):
        """停止视频播放"""
        print(f"[VIDEO] Stopping player...", flush=True)
        self.stop_event.set()
        self._stop_current_vlc()
 

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

    last_cmd_time = time.time()
    watchdog_active = False
    logging.info("Waiting for commands...")

    try:
        # Business logic
        start = time.perf_counter()
        duration = 0

        while duration < host.connection_time_s:
            loop_start_time = time.time()
            try:
                msg = host.zmq_cmd_socket.recv_string(zmq.NOBLOCK)
                data = dict(json.loads(msg))
                
                # 检查是否有视频切换命令
                if video_player:
                    if "video_next" in data and data["video_next"]:
                        video_player.switch_to_next()
                    elif "video_prev" in data and data["video_prev"]:
                        video_player.switch_to_previous()
                
                # 发送动作到机器人
                _action_sent = robot.send_action(data)
                
                last_cmd_time = time.time()
                watchdog_active = False
            except zmq.Again:
                if not watchdog_active:
                    logging.warning("No command available")
            except Exception as e:
                logging.exception("Message fetching failed: %s", e)

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
