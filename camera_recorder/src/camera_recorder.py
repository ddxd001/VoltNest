#!/usr/bin/env python3
"""
摄像头录制主程序

启动即录制，停止即结束。
"""

import cv2
import os
import sys
import signal
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# 添加父目录到路径以便导入配置模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config_loader import load_config


class CameraRecorder:
    """摄像头录制器"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化录制器
        
        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        self.config = load_config(config_path)
        
        # 设置日志
        log_level = self.config.get('advanced.log_level', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='[%(levelname)s] %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # 摄像头配置
        self.device_id = self.config.get('camera.device_id', 0)
        self.width = self.config.get('camera.width', 1280)
        self.height = self.config.get('camera.height', 720)
        self.fps = self.config.get('camera.fps', 30)
        
        # 录制配置
        self.output_dir = self.config.get('recording.output_dir', './recordings')
        self.codec = self.config.get('recording.codec', 'mp4v')
        self.file_prefix = self.config.get('recording.file_prefix', 'recording')
        
        # 运行状态
        self.camera: Optional[cv2.VideoCapture] = None
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.output_file: Optional[str] = None
        self.is_recording = False
        self.frame_count = 0
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """处理中断信号"""
        self.logger.info("Received stop signal, stopping recording...")
        self.stop()
        sys.exit(0)
    
    def _init_camera(self) -> bool:
        """
        初始化摄像头
        
        Returns:
            是否成功
        """
        try:
            self.logger.info(f"Initializing camera device {self.device_id}...")
            self.camera = cv2.VideoCapture(self.device_id)
            
            if not self.camera.isOpened():
                self.logger.error(f"Failed to open camera device {self.device_id}")
                return False
            
            # 设置分辨率
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.camera.set(cv2.CAP_PROP_FPS, self.fps)
            
            # 获取实际分辨率
            actual_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(self.camera.get(cv2.CAP_PROP_FPS))
            
            self.logger.info(f"Camera initialized: {actual_width}x{actual_height} @ {actual_fps}fps")
            
            # 更新实际值
            self.width = actual_width
            self.height = actual_height
            self.fps = actual_fps if actual_fps > 0 else self.fps
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize camera: {e}")
            return False
    
    def _init_video_writer(self) -> bool:
        """
        初始化视频写入器
        
        Returns:
            是否成功
        """
        try:
            # 创建输出目录
            output_dir = Path(self.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名（带时间戳）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.file_prefix}_{timestamp}.mp4"
            self.output_file = str(output_dir / filename)
            
            # 创建视频写入器
            fourcc = cv2.VideoWriter_fourcc(*self.codec)
            self.video_writer = cv2.VideoWriter(
                self.output_file,
                fourcc,
                self.fps,
                (self.width, self.height)
            )
            
            if not self.video_writer.isOpened():
                self.logger.error("Failed to initialize video writer")
                return False
            
            self.logger.info(f"Recording started: {self.output_file}")
            self.logger.info(f"Codec: {self.codec}, Resolution: {self.width}x{self.height}, FPS: {self.fps}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize video writer: {e}")
            return False
    
    def start(self) -> bool:
        """
        开始录制
        
        Returns:
            是否成功启动
        """
        # 初始化摄像头
        if not self._init_camera():
            return False
        
        # 初始化视频写入器
        if not self._init_video_writer():
            self.camera.release()
            return False
        
        self.is_recording = True
        self.frame_count = 0
        
        self.logger.info("Press Ctrl+C to stop recording")
        
        # 录制循环
        try:
            while self.is_recording:
                ret, frame = self.camera.read()
                
                if not ret:
                    self.logger.warning("Failed to read frame from camera")
                    break
                
                # 写入帧
                self.video_writer.write(frame)
                self.frame_count += 1
                
                # 每 100 帧输出一次进度
                if self.frame_count % 100 == 0:
                    duration = self.frame_count / self.fps
                    self.logger.debug(f"Recorded {self.frame_count} frames ({duration:.1f}s)")
        
        except Exception as e:
            self.logger.error(f"Recording error: {e}")
            return False
        
        finally:
            self.stop()
        
        return True
    
    def stop(self):
        """停止录制"""
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        # 释放资源
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None
        
        if self.camera is not None:
            self.camera.release()
            self.camera = None
        
        # 输出统计信息
        if self.frame_count > 0:
            duration = self.frame_count / self.fps
            file_size = os.path.getsize(self.output_file) / (1024 * 1024)  # MB
            
            self.logger.info("=" * 50)
            self.logger.info("Recording stopped")
            self.logger.info(f"Output file: {self.output_file}")
            self.logger.info(f"Total frames: {self.frame_count}")
            self.logger.info(f"Duration: {duration:.1f}s ({duration/60:.1f}min)")
            self.logger.info(f"File size: {file_size:.1f} MB")
            self.logger.info("=" * 50)
        else:
            self.logger.warning("No frames recorded")


def main():
    """主函数"""
    # 获取脚本所在目录
    script_dir = Path(__file__).parent.parent
    config_path = script_dir / "config.yaml"
    
    # 切换到脚本目录
    os.chdir(script_dir)
    
    print("=" * 50)
    print("  Camera Recorder")
    print("  启动即录制，Ctrl+C 停止")
    print("=" * 50)
    print()
    
    # 创建录制器
    recorder = CameraRecorder(str(config_path))
    
    # 开始录制
    success = recorder.start()
    
    if not success:
        print("\n[ERROR] Recording failed!")
        sys.exit(1)
    
    print("\n[INFO] Recording completed successfully!")
    sys.exit(0)


if __name__ == "__main__":
    main()
