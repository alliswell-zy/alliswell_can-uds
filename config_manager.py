#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理器 - 管理应用程序配置
支持YAML配置文件格式
"""

import os
import json
import yaml
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

class CANInterfaceType(Enum):
    """CAN接口类型枚举"""
    PCAN = "pcan"
    VECTOR = "vector"
    IXXAT = "ixxat"
    KVASER = "kvaser"
    SLCAN = "slcan"
    CANDLELIGHT = "candlelight"
    NI_XNET = "ni_xnet"
    VIRTUAL = "virtual"
    SOCKETCAN = "socketcan"
    USBCAN = "usbcan"
    PCICAN = "pcican"
    
class CANMode(Enum):
    """CAN模式枚举"""
    CAN = "can"
    CAN_FD = "can_fd"

class FrameType(Enum):
    """帧类型枚举"""
    STANDARD = "standard"
    EXTENDED = "extended"

@dataclass
class CANInterfaceConfig:
    """CAN接口配置"""
    interface_type: CANInterfaceType = CANInterfaceType.VIRTUAL
    channel: str = "0"
    bitrate: int = 500000
    data_bitrate: int = 2000000  # CAN FD数据段波特率
    fd_enabled: bool = False
    sample_point: float = 0.75
    sjw: int = 1
    listen_only: bool = False
    f_clock: int = 80000000
    sjw_fd: int = 1
    tseg1_fd: int = 31
    tseg2_fd: int = 10
    sample_point_fd: float = 0.75
    
    # NI XNET特定配置
    ni_database_path: str = ""
    ni_interface_name: str = ""
    
    # Vector特定配置
    vector_app_name: str = "UDS_Tool"
    vector_hw_channel: int = 1
    
    # IXXAT特定配置
    ixxat_device_id: int = 0
    
    # SLCAN特定配置
    slcan_serial_port: str = "COM1"
    slcan_baudrate: int = 115200
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['interface_type'] = self.interface_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CANInterfaceConfig':
        """从字典创建"""
        if 'interface_type' in data:
            data['interface_type'] = CANInterfaceType(data['interface_type'])
        return cls(**data)

@dataclass
class UDSConfig:
    """UDS配置"""
    # ISO-TP配置
    isotp_rx_id: int = 0x7E0
    isotp_tx_id: int = 0x7E8
    addressing_mode: str = "normal"  # normal, extended, mixed
    frame_type: FrameType = FrameType.STANDARD
    
    # 流控制参数
    st_min: int = 0
    block_size: int = 8
    separation_time: int = 0
    
    # CAN FD配置
    can_fd_enabled: bool = False
    fd_baudrate_switch: bool = True
    fd_bitrate_switch: bool = True
    fd_dlc: int = 64  # 0-64字节
    
    # 定时参数
    p2_timeout: int = 50  # ms
    p2_extended: int = 5000  # ms
    p4_timeout: int = 5000  # ms
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['frame_type'] = self.frame_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UDSConfig':
        """从字典创建"""
        if 'frame_type' in data:
            data['frame_type'] = FrameType(data['frame_type'])
        return cls(**data)

@dataclass
class MonitorConfig:
    """监控配置"""
    enabled: bool = True
    auto_scroll: bool = True
    timestamp_format: str = "absolute"  # absolute, relative, off
    show_can_fd: bool = True
    show_error_frames: bool = True
    colorize_messages: bool = True
    max_display_lines: int = 1000
    save_to_file: bool = False
    save_path: str = ""
    file_max_size: int = 100  # MB
    
class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        self.config_path = config_path or self._get_default_config_path()
        self.config_dir = Path(self.config_path).parent
        
        # 确保配置目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # 默认配置
        self.can_config = CANInterfaceConfig()
        self.uds_config = UDSConfig()
        self.monitor_config = MonitorConfig()
        
        # 用户配置
        self.user_settings: Dict[str, Any] = {
            'recent_files': [],
            'window_geometry': None,
            'window_state': None,
            'theme': 'light',
            'language': 'en',
            'auto_connect': False,
            'start_minimized': False,
        }
        
        # 加载配置
        self.load_config()
        
    def _get_default_config_path(self) -> str:
        """获取默认配置文件路径"""
        if os.name == 'nt':  # Windows
            config_dir = Path.home() / "AppData" / "Local" / "UDSTool"
        elif os.name == 'posix':  # Linux/macOS
            config_dir = Path.home() / ".config" / "udstool"
        else:
            config_dir = Path.cwd() / "config"
        
        return str(config_dir / "config.yaml")
    
    def save_config(self) -> bool:
        """保存配置到文件"""
        try:
            config_data = {
                'version': '1.0',
                'can_config': self.can_config.to_dict(),
                'uds_config': self.uds_config.to_dict(),
                'monitor_config': asdict(self.monitor_config),
                'user_settings': self.user_settings,
            }
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"Configuration saved to {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    def load_config(self) -> bool:
        """从文件加载配置"""
        try:
            if not os.path.exists(self.config_path):
                logger.info(f"Configuration file not found, using defaults: {self.config_path}")
                return False
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            if not config_data:
                return False
            
            # 加载CAN配置
            if 'can_config' in config_data:
                self.can_config = CANInterfaceConfig.from_dict(config_data['can_config'])
            
            # 加载UDS配置
            if 'uds_config' in config_data:
                self.uds_config = UDSConfig.from_dict(config_data['uds_config'])
            
            # 加载监控配置
            if 'monitor_config' in config_data:
                self.monitor_config = MonitorConfig(**config_data['monitor_config'])
            
            # 加载用户设置
            if 'user_settings' in config_data:
                self.user_settings.update(config_data['user_settings'])
            
            logger.info(f"Configuration loaded from {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return False
    
    def get_available_interfaces(self) -> List[Tuple[str, str]]:
        """获取可用CAN接口列表"""
        interfaces = []
        
        try:
            import can
            
            # 获取python-can检测到的接口
            can_interfaces = can.detect_available_configs()
            for interface in can_interfaces:
                interface_str = f"{interface['interface']} - {interface.get('channel', 'N/A')}"
                interfaces.append((interface['interface'], interface_str))
                
        except ImportError:
            logger.error("python-can not installed")
        except Exception as e:
            logger.error(f"Error detecting interfaces: {e}")
        
        # 添加NI XNET接口
        try:
            import nixnet
            from nixnet import constants
            import nixnet._funcs
            
            # 获取NI XNET接口
            ni_interfaces = nixnet._funcs.get_interface_refs()
            for intf in ni_interfaces:
                interfaces.append(('ni_xnet', f"NI XNET - {intf}"))
                
        except ImportError:
            logger.debug("NI XNET not available")
        except Exception as e:
            logger.debug(f"NI XNET detection failed: {e}")
        
        # 如果没有检测到接口，添加虚拟接口
        if not interfaces:
            interfaces = [
                ('virtual', 'Virtual CAN Interface'),
                ('pcan', 'PCAN (需要PCAN驱动)'),
                ('vector', 'Vector (需要Vector驱动)'),
                ('ixxat', 'IXXAT (需要IXXAT驱动)'),
                ('kvaser', 'Kvaser (需要Kvaser驱动)'),
            ]
        
        return interfaces
    
    def add_recent_file(self, file_path: str) -> None:
        """添加最近使用的文件"""
        if file_path in self.user_settings['recent_files']:
            self.user_settings['recent_files'].remove(file_path)
        
        self.user_settings['recent_files'].insert(0, file_path)
        
        # 限制最近文件数量
        if len(self.user_settings['recent_files']) > 10:
            self.user_settings['recent_files'] = self.user_settings['recent_files'][:10]
        
        self.save_config()
    
    def clear_recent_files(self) -> None:
        """清除最近使用的文件"""
        self.user_settings['recent_files'] = []
        self.save_config()