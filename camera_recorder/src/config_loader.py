"""
配置加载模块
"""

import os
import yaml
from typing import Dict, Any


class ConfigLoader:
    """配置文件加载器"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化配置加载器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        return config
    
    def get_camera_config(self) -> Dict[str, Any]:
        """获取摄像头配置"""
        return self.config.get('camera', {})
    
    def get_recording_config(self) -> Dict[str, Any]:
        """获取录制配置"""
        return self.config.get('recording', {})
    
    def get_advanced_config(self) -> Dict[str, Any]:
        """获取高级配置"""
        return self.config.get('advanced', {})
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项
        
        Args:
            key: 配置键（支持点号分隔的嵌套键，如 'camera.device_id'）
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value if value is not None else default


def load_config(config_path: str = "config.yaml") -> ConfigLoader:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        ConfigLoader 实例
    """
    return ConfigLoader(config_path)
