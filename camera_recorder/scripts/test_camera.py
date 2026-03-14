#!/usr/bin/env python3
"""
摄像头测试脚本

用于测试摄像头是否可用，并显示可用的摄像头列表。
"""

import cv2
import sys


def test_camera(device_id: int) -> bool:
    """
    测试指定的摄像头
    
    Args:
        device_id: 摄像头设备 ID
        
    Returns:
        是否可用
    """
    print(f"\n测试摄像头 {device_id}...")
    
    cap = cv2.VideoCapture(device_id)
    
    if not cap.isOpened():
        print(f"  ❌ 无法打开摄像头 {device_id}")
        return False
    
    # 读取一帧测试
    ret, frame = cap.read()
    
    if not ret:
        print(f"  ❌ 无法读取摄像头 {device_id} 的画面")
        cap.release()
        return False
    
    # 获取摄像头信息
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    
    print(f"  ✅ 摄像头 {device_id} 可用")
    print(f"     分辨率: {width}x{height}")
    print(f"     帧率: {fps} fps")
    print(f"     设备路径: /dev/video{device_id}")
    
    cap.release()
    return True


def find_all_cameras(max_devices: int = 10) -> list:
    """
    查找所有可用的摄像头
    
    Args:
        max_devices: 最大检测设备数
        
    Returns:
        可用摄像头的 ID 列表
    """
    available_cameras = []
    
    print("正在扫描可用摄像头...")
    print("=" * 50)
    
    for device_id in range(max_devices):
        if test_camera(device_id):
            available_cameras.append(device_id)
    
    return available_cameras


def main():
    """主函数"""
    print("=" * 50)
    print("  摄像头测试工具")
    print("=" * 50)
    
    # 查找所有摄像头
    cameras = find_all_cameras()
    
    print("\n" + "=" * 50)
    print("扫描结果:")
    print("=" * 50)
    
    if cameras:
        print(f"\n找到 {len(cameras)} 个可用摄像头:")
        for cam_id in cameras:
            print(f"  - 摄像头 {cam_id} (/dev/video{cam_id})")
        
        print("\n💡 提示:")
        print(f"   在 config.yaml 中设置 device_id: {cameras[0]} 来使用第一个摄像头")
    else:
        print("\n❌ 未找到可用摄像头")
        print("\n请检查:")
        print("  1. 摄像头是否已连接")
        print("  2. 摄像头驱动是否已安装")
        print("  3. 是否有权限访问摄像头设备")
        print("\n可以尝试运行:")
        print("  ls -l /dev/video*")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
