#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CAN接口管理器 - 支持多种CAN卡接口
支持：PCAN、VECTOR、IXXAT、KVASER、SLCAN、candleLight、NI XNET、virtual
支持CAN FD和标准CAN
"""

import logging
import time
import threading
import queue
from enum import Enum
from typing import Optional, Dict, List, Any, Tuple, Union
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

import can
import cantools
from can import CanError, Bus, CanInterfaceNotImplementedError
from can.message import Message
from can.notifier import Notifier
from can.interfaces import VALID_INTERFACES

logger = logging.getLogger(__name__)

class CANInterfaceStatus(Enum):
    """CAN接口状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    CLOSING = "closing"

@dataclass
class CANFrame:
    """CAN帧数据类"""
    timestamp: float
    arbitration_id: int
    data: bytes
    is_extended_id: bool = False
    is_remote_frame: bool = False
    is_error_frame: bool = False
    is_fd: bool = False
    bitrate_switch: bool = False
    error_state_indicator: bool = False
    channel: int = 0
    dlc: int = 0
    
    def __post_init__(self):
        if self.dlc == 0:
            self.dlc = len(self.data)
    
    @property
    def id_hex(self) -> str:
        """返回十六进制ID"""
        return f"0x{self.arbitration_id:X}"
    
    @property
    def data_hex(self) -> str:
        """返回十六进制数据"""
        return self.data.hex().upper()
    
    @property
    def data_ascii(self) -> str:
        """返回ASCII数据"""
        result = ""
        for byte in self.data:
            if 32 <= byte <= 126:
                result += chr(byte)
            else:
                result += "."
        return result

class CANStatistics:
    """CAN通信统计"""
    def __init__(self):
        self.tx_frames = 0
        self.rx_frames = 0
        self.tx_bytes = 0
        self.rx_bytes = 0
        self.error_frames = 0
        self.start_time = time.time()
    
    def reset(self):
        """重置统计"""
        self.tx_frames = 0
        self.rx_frames = 0
        self.tx_bytes = 0
        self.rx_bytes = 0
        self.error_frames = 0
        self.start_time = time.time()
    
    @property
    def uptime(self) -> float:
        """运行时间"""
        return time.time() - self.start_time
    
    @property
    def tx_rate(self) -> float:
        """发送速率（帧/秒）"""
        if self.uptime > 0:
            return self.tx_frames / self.uptime
        return 0
    
    @property
    def rx_rate(self) -> float:
        """接收速率（帧/秒）"""
        if self.uptime > 0:
            return self.rx_frames / self.uptime
        return 0
    
    def get_summary(self) -> Dict[str, Any]:
        """获取统计摘要"""
        return {
            'tx_frames': self.tx_frames,
            'rx_frames': self.rx_frames,
            'tx_bytes': self.tx_bytes,
            'rx_bytes': self.rx_bytes,
            'error_frames': self.error_frames,
            'uptime': self.uptime,
            'tx_rate': self.tx_rate,
            'rx_rate': self.rx_rate,
        }

class BaseCANInterface(ABC):
    """CAN接口基类"""
    
    def __init__(self, interface_type: str, channel: str = "0", **kwargs):
        """
        初始化CAN接口
        
        Args:
            interface_type: 接口类型
            channel: 通道号
            **kwargs: 额外参数
        """
        self.interface_type = interface_type
        self.channel = channel
        self._bus: Optional[Bus] = None
        self._notifier: Optional[Notifier] = None
        self._status = CANInterfaceStatus.DISCONNECTED
        self._receive_queue = queue.Queue(maxsize=10000)
        self._callbacks = []
        self._statistics = CANStatistics()
        self._lock = threading.RLock()
        
        # 配置参数
        self.config = kwargs
        
    @property
    def status(self) -> CANInterfaceStatus:
        """获取接口状态"""
        return self._status
    
    @property
    def is_connected(self) -> bool:
        """检查是否连接"""
        return self._status == CANInterfaceStatus.CONNECTED
    
    @property
    def statistics(self) -> CANStatistics:
        """获取统计信息"""
        return self._statistics
    
    def connect(self, **kwargs) -> bool:
        """
        连接CAN接口
        
        Args:
            **kwargs: 连接参数
            
        Returns:
            bool: 连接是否成功
        """
        with self._lock:
            if self.is_connected:
                logger.warning("CAN interface already connected")
                return True
            
            self._status = CANInterfaceStatus.CONNECTING
            logger.info(f"Connecting to {self.interface_type} on channel {self.channel}")
            
            try:
                # 更新配置
                self.config.update(kwargs)
                
                # 创建CAN总线
                self._bus = self._create_bus()
                
                # 创建通知器
                self._notifier = can.Notifier(self._bus, [self._on_message_received])
                
                self._status = CANInterfaceStatus.CONNECTED
                self._statistics.reset()
                logger.info(f"Successfully connected to {self.interface_type}")
                return True
                
            except Exception as e:
                self._status = CANInterfaceStatus.ERROR
                logger.error(f"Failed to connect to {self.interface_type}: {e}")
                self.disconnect()
                return False
    
    def disconnect(self) -> bool:
        """
        断开CAN接口连接
        
        Returns:
            bool: 断开是否成功
        """
        with self._lock:
            if not self.is_connected and self._status != CANInterfaceStatus.CONNECTING:
                return True
            
            self._status = CANInterfaceStatus.CLOSING
            logger.info(f"Disconnecting from {self.interface_type}")
            
            try:
                # 停止通知器
                if self._notifier:
                    self._notifier.stop()
                    self._notifier = None
                
                # 关闭总线
                if self._bus:
                    self._bus.shutdown()
                    self._bus = None
                
                # 清空接收队列
                while not self._receive_queue.empty():
                    try:
                        self._receive_queue.get_nowait()
                    except queue.Empty:
                        break
                
                self._status = CANInterfaceStatus.DISCONNECTED
                logger.info(f"Successfully disconnected from {self.interface_type}")
                return True
                
            except Exception as e:
                logger.error(f"Error disconnecting from {self.interface_type}: {e}")
                self._status = CANInterfaceStatus.ERROR
                return False
    
    @abstractmethod
    def _create_bus(self) -> Bus:
        """创建CAN总线"""
        pass
    
    def send_frame(self, frame: CANFrame) -> bool:
        """
        发送CAN帧
        
        Args:
            frame: CAN帧
            
        Returns:
            bool: 发送是否成功
        """
        with self._lock:
            if not self.is_connected or not self._bus:
                logger.error("CAN interface not connected")
                return False
            
            try:
                # 创建can.Message对象
                msg = Message(
                    arbitration_id=frame.arbitration_id,
                    data=frame.data,
                    is_extended_id=frame.is_extended_id,
                    is_remote_frame=frame.is_remote_frame,
                    is_error_frame=frame.is_error_frame,
                    is_fd=frame.is_fd,
                    bitrate_switch=frame.bitrate_switch,
                    error_state_indicator=frame.error_state_indicator,
                    channel=frame.channel,
                    dlc=frame.dlc
                )
                
                # 发送消息
                self._bus.send(msg, timeout=0.1)
                
                # 更新统计
                self._statistics.tx_frames += 1
                self._statistics.tx_bytes += len(frame.data)
                
                logger.debug(f"Sent CAN frame: ID={frame.id_hex}, Data={frame.data_hex}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to send CAN frame: {e}")
                return False
    
    def receive_frame(self, timeout: float = 0.1) -> Optional[CANFrame]:
        """
        接收CAN帧
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            CANFrame or None: 接收到的帧，超时返回None
        """
        try:
            msg = self._receive_queue.get(timeout=timeout)
            return msg
        except queue.Empty:
            return None
    
    def _on_message_received(self, msg: Message) -> None:
        """
        CAN消息接收回调
        
        Args:
            msg: CAN消息
        """
        if not msg:
            return
        
        try:
            # 创建CANFrame对象
            frame = CANFrame(
                timestamp=msg.timestamp,
                arbitration_id=msg.arbitration_id,
                data=msg.data,
                is_extended_id=msg.is_extended_id,
                is_remote_frame=msg.is_remote_frame,
                is_error_frame=msg.is_error_frame,
                is_fd=msg.is_fd,
                bitrate_switch=msg.bitrate_switch,
                error_state_indicator=msg.error_state_indicator,
                channel=msg.channel,
                dlc=msg.dlc
            )
            
            # 添加到接收队列
            try:
                self._receive_queue.put_nowait(frame)
            except queue.Full:
                # 队列已满，丢弃最旧的消息
                try:
                    self._receive_queue.get_nowait()
                    self._receive_queue.put_nowait(frame)
                except queue.Empty:
                    pass
            
            # 更新统计
            self._statistics.rx_frames += 1
            self._statistics.rx_bytes += len(msg.data)
            
            # 调用注册的回调函数
            for callback in self._callbacks:
                try:
                    callback(frame)
                except Exception as e:
                    logger.error(f"Error in CAN frame callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error processing received message: {e}")
    
    def add_callback(self, callback: callable) -> None:
        """
        添加接收回调函数
        
        Args:
            callback: 回调函数，接收一个CANFrame参数
        """
        if callback not in self._callbacks:
            self._callbacks.append(callback)
    
    def remove_callback(self, callback: callable) -> None:
        """
        移除接收回调函数
        
        Args:
            callback: 回调函数
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def clear_callbacks(self) -> None:
        """清空所有回调函数"""
        self._callbacks.clear()
    
    def get_info(self) -> Dict[str, Any]:
        """
        获取接口信息
        
        Returns:
            dict: 接口信息
        """
        info = {
            'interface_type': self.interface_type,
            'channel': self.channel,
            'status': self.status.value,
            'is_connected': self.is_connected,
            'config': self.config.copy(),
        }
        
        if self._bus:
            info.update({
                'state': self._bus.state,
                'can_protocol': str(self._bus.protocol),
            })
        
        return info

class PCANInterface(BaseCANInterface):
    """PCAN接口实现"""
    
    def _create_bus(self) -> Bus:
        """创建PCAN总线"""
        return can.Bus(
            interface='pcan',
            channel=self.channel,
            bitrate=self.config.get('bitrate', 500000),
            fd=self.config.get('fd_enabled', False),
            data_bitrate=self.config.get('data_bitrate', 2000000),
            **self._get_interface_params()
        )
    
    def _get_interface_params(self) -> Dict[str, Any]:
        """获取PCAN接口参数"""
        params = {}
        
        # 添加PCAN特定参数
        if 'f_clock' in self.config:
            params['f_clock'] = self.config['f_clock']
        
        if 'nom_brp' in self.config:
            params['nom_brp'] = self.config['nom_brp']
        
        if 'nom_tseg1' in self.config:
            params['nom_tseg1'] = self.config['nom_tseg1']
        
        if 'nom_tseg2' in self.config:
            params['nom_tseg2'] = self.config['nom_tseg2']
        
        if 'nom_sjw' in self.config:
            params['nom_sjw'] = self.config['nom_sjw']
        
        # CAN FD参数
        if self.config.get('fd_enabled', False):
            if 'data_brp' in self.config:
                params['data_brp'] = self.config['data_brp']
            
            if 'data_tseg1' in self.config:
                params['data_tseg1'] = self.config['data_tseg1']
            
            if 'data_tseg2' in self.config:
                params['data_tseg2'] = self.config['data_tseg2']
            
            if 'data_sjw' in self.config:
                params['data_sjw'] = self.config['data_sjw']
        
        return params

class VectorInterface(BaseCANInterface):
    """Vector接口实现"""
    
    def _create_bus(self) -> Bus:
        """创建Vector总线"""
        return can.Bus(
            interface='vector',
            channel=self.channel,
            bitrate=self.config.get('bitrate', 500000),
            fd=self.config.get('fd_enabled', False),
            data_bitrate=self.config.get('data_bitrate', 2000000),
            app_name=self.config.get('vector_app_name', 'UDS_Tool'),
            **self._get_interface_params()
        )
    
    def _get_interface_params(self) -> Dict[str, Any]:
        """获取Vector接口参数"""
        params = {}
        
        # 添加Vector特定参数
        if 'rx_queue_size' in self.config:
            params['rx_queue_size'] = self.config['rx_queue_size']
        
        if 'tx_queue_size' in self.config:
            params['tx_queue_size'] = self.config['tx_queue_size']
        
        if 'poll_timeout' in self.config:
            params['poll_timeout'] = self.config['poll_timeout']
        
        if 'serial' in self.config:
            params['serial'] = self.config['serial']
        
        if 'hw_channel' in self.config:
            params['hw_channel'] = self.config['hw_channel']
        
        return params

class IXXATInterface(BaseCANInterface):
    """IXXAT接口实现"""
    
    def _create_bus(self) -> Bus:
        """创建IXXAT总线"""
        return can.Bus(
            interface='ixxat',
            channel=self.channel,
            bitrate=self.config.get('bitrate', 500000),
            fd=self.config.get('fd_enabled', False),
            data_bitrate=self.config.get('data_bitrate', 2000000),
            **self._get_interface_params()
        )
    
    def _get_interface_params(self) -> Dict[str, Any]:
        """获取IXXAT接口参数"""
        params = {}
        
        # 添加IXXAT特定参数
        if 'unique_hardware_id' in self.config:
            params['unique_hardware_id'] = self.config['unique_hardware_id']
        
        if 'controller_index' in self.config:
            params['controller_index'] = self.config['controller_index']
        
        if 'device_id' in self.config:
            params['device_id'] = self.config['device_id']
        
        return params

class KvaserInterface(BaseCANInterface):
    """Kvaser接口实现"""
    
    def _create_bus(self) -> Bus:
        """创建Kvaser总线"""
        return can.Bus(
            interface='kvaser',
            channel=self.channel,
            bitrate=self.config.get('bitrate', 500000),
            fd=self.config.get('fd_enabled', False),
            data_bitrate=self.config.get('data_bitrate', 2000000),
            **self._get_interface_params()
        )
    
    def _get_interface_params(self) -> Dict[str, Any]:
        """获取Kvaser接口参数"""
        params = {}
        
        # 添加Kvaser特定参数
        if 'serial' in self.config:
            params['serial'] = self.config['serial']
        
        if 'poll_timeout' in self.config:
            params['poll_timeout'] = self.config['poll_timeout']
        
        return params

class SLCANInterface(BaseCANInterface):
    """SLCAN接口实现"""
    
    def _create_bus(self) -> Bus:
        """创建SLCAN总线"""
        return can.Bus(
            interface='slcan',
            channel=self.config.get('serial_port', 'COM1'),
            bitrate=self.config.get('bitrate', 500000),
            fd=self.config.get('fd_enabled', False),
            data_bitrate=self.config.get('data_bitrate', 2000000),
            **self._get_interface_params()
        )
    
    def _get_interface_params(self) -> Dict[str, Any]:
        """获取SLCAN接口参数"""
        params = {}
        
        # 添加SLCAN特定参数
        if 'serial_port' in self.config:
            params['port'] = self.config['serial_port']
        
        if 'baudrate' in self.config:
            params['baudrate'] = self.config['baudrate']
        
        if 'ttyBaudrate' in self.config:
            params['ttyBaudrate'] = self.config['ttyBaudrate']
        
        if 'poll_timeout' in self.config:
            params['poll_timeout'] = self.config['poll_timeout']
        
        return params

class CandleLightInterface(BaseCANInterface):
    """candleLight接口实现"""
    
    def _create_bus(self) -> Bus:
        """创建candleLight总线"""
        return can.Bus(
            interface='candlelight',
            channel=self.channel,
            bitrate=self.config.get('bitrate', 500000),
            fd=self.config.get('fd_enabled', False),
            data_bitrate=self.config.get('data_bitrate', 2000000),
            **self._get_interface_params()
        )
    
    def _get_interface_params(self) -> Dict[str, Any]:
        """获取candleLight接口参数"""
        params = {}
        
        # 添加candleLight特定参数
        if 'serial' in self.config:
            params['serial'] = self.config['serial']
        
        return params

class NIXNETInterface(BaseCANInterface):
    """NI XNET接口实现"""
    
    def _create_bus(self) -> Bus:
        """创建NI XNET总线"""
        try:
            # NI XNET需要特殊处理
            import nixnet
            from nixnet import constants
            
            # 构建接口字符串
            interface_name = self.config.get('ni_interface_name', 'CAN1')
            mode = self.config.get('mode', 'can')
            
            if mode == 'can':
                interface_str = f"{interface_name}"
            else:
                interface_str = f"{interface_name}::{mode}"
            
            # 创建总线
            return can.Bus(
                interface='nixnet',
                channel=interface_str,
                bitrate=self.config.get('bitrate', 500000),
                fd=self.config.get('fd_enabled', False),
                data_bitrate=self.config.get('data_bitrate', 2000000),
                **self._get_interface_params()
            )
            
        except ImportError:
            raise ImportError("NI XNET driver not installed. Please install nixnet package.")
    
    def _get_interface_params(self) -> Dict[str, Any]:
        """获取NI XNET接口参数"""
        params = {}
        
        # 添加NI XNET特定参数
        if 'database' in self.config:
            params['database'] = self.config['database']
        
        if 'cluster' in self.config:
            params['cluster'] = self.config['cluster']
        
        if 'can_id' in self.config:
            params['can_id'] = self.config['can_id']
        
        if 'poll_timeout' in self.config:
            params['poll_timeout'] = self.config['poll_timeout']
        
        return params

class VirtualInterface(BaseCANInterface):
    """虚拟接口实现"""
    
    def _create_bus(self) -> Bus:
        """创建虚拟总线"""
        return can.Bus(
            interface='virtual',
            channel=self.channel,
            bitrate=self.config.get('bitrate', 500000),
            fd=self.config.get('fd_enabled', False),
            data_bitrate=self.config.get('data_bitrate', 2000000),
            **self._get_interface_params()
        )
    
    def _get_interface_params(self) -> Dict[str, Any]:
        """获取虚拟接口参数"""
        params = {}
        
        # 添加虚拟接口特定参数
        if 'receive_own_messages' in self.config:
            params['receive_own_messages'] = self.config['receive_own_messages']
        
        return params

class SocketCANInterface(BaseCANInterface):
    """SocketCAN接口实现"""
    
    def _create_bus(self) -> Bus:
        """创建SocketCAN总线"""
        return can.Bus(
            interface='socketcan',
            channel=self.channel,
            bitrate=self.config.get('bitrate', 500000),
            fd=self.config.get('fd_enabled', False),
            data_bitrate=self.config.get('data_bitrate', 2000000),
            **self._get_interface_params()
        )
    
    def _get_interface_params(self) -> Dict[str, Any]:
        """获取SocketCAN接口参数"""
        params = {}
        
        # 添加SocketCAN特定参数
        if 'receive_own_messages' in self.config:
            params['receive_own_messages'] = self.config['receive_own_messages']
        
        if 'fd' in self.config:
            params['fd'] = self.config['fd']
        
        return params

class CANInterfaceFactory:
    """CAN接口工厂"""
    
    @staticmethod
    def create_interface(interface_type: str, **kwargs) -> BaseCANInterface:
        """
        创建CAN接口
        
        Args:
            interface_type: 接口类型
            **kwargs: 接口参数
            
        Returns:
            BaseCANInterface: CAN接口实例
        """
        interface_type = interface_type.lower()
        
        # 接口类型映射
        interface_classes = {
            'pcan': PCANInterface,
            'vector': VectorInterface,
            'ixxat': IXXATInterface,
            'kvaser': KvaserInterface,
            'slcan': SLCANInterface,
            'candlelight': CandleLightInterface,
            'ni_xnet': NIXNETInterface,
            'nixnet': NIXNETInterface,
            'virtual': VirtualInterface,
            'socketcan': SocketCANInterface,
        }
        
        if interface_type not in interface_classes:
            logger.warning(f"Interface type '{interface_type}' not supported, using virtual")
            interface_type = 'virtual'
        
        # 创建接口实例
        interface_class = interface_classes[interface_type]
        return interface_class(interface_type, **kwargs)
    
    @staticmethod
    def get_available_interfaces() -> List[Dict[str, str]]:
        """
        获取可用接口列表
        
        Returns:
            list: 可用接口信息列表
        """
        interfaces = []
        
        try:
            # 使用python-can检测可用接口
            available_configs = can.detect_available_configs()
            
            for config in available_configs:
                interface_info = {
                    'interface': config['interface'],
                    'channel': str(config.get('channel', '0')),
                    'description': f"{config['interface']} - {config.get('channel', '0')}",
                }
                
                # 添加额外信息
                if 'serial' in config:
                    interface_info['serial'] = config['serial']
                
                interfaces.append(interface_info)
                
        except Exception as e:
            logger.error(f"Error detecting interfaces: {e}")
        
        # 如果没有检测到接口，添加虚拟接口
        if not interfaces:
            interfaces = [
                {
                    'interface': 'virtual',
                    'channel': '0',
                    'description': 'Virtual CAN Interface',
                }
            ]
        
        return interfaces

class CANInterfaceManager:
    """CAN接口管理器"""
    
    def __init__(self):
        self._interfaces: Dict[str, BaseCANInterface] = {}
        self._lock = threading.RLock()
    
    def create_interface(self, interface_id: str, interface_type: str, **kwargs) -> BaseCANInterface:
        """
        创建CAN接口
        
        Args:
            interface_id: 接口ID
            interface_type: 接口类型
            **kwargs: 接口参数
            
        Returns:
            BaseCANInterface: 创建的接口
        """
        with self._lock:
            if interface_id in self._interfaces:
                logger.warning(f"Interface '{interface_id}' already exists")
                return self._interfaces[interface_id]
            
            interface = CANInterfaceFactory.create_interface(interface_type, **kwargs)
            self._interfaces[interface_id] = interface
            
            logger.info(f"Created CAN interface '{interface_id}' of type '{interface_type}'")
            return interface
    
    def get_interface(self, interface_id: str) -> Optional[BaseCANInterface]:
        """
        获取CAN接口
        
        Args:
            interface_id: 接口ID
            
        Returns:
            BaseCANInterface or None: 接口实例
        """
        with self._lock:
            return self._interfaces.get(interface_id)
    
    def remove_interface(self, interface_id: str) -> bool:
        """
        移除CAN接口
        
        Args:
            interface_id: 接口ID
            
        Returns:
            bool: 是否成功移除
        """
        with self._lock:
            if interface_id not in self._interfaces:
                return False
            
            interface = self._interfaces[interface_id]
            
            # 断开连接
            if interface.is_connected:
                interface.disconnect()
            
            # 移除接口
            del self._interfaces[interface_id]
            
            logger.info(f"Removed CAN interface '{interface_id}'")
            return True
    
    def connect_interface(self, interface_id: str, **kwargs) -> bool:
        """
        连接CAN接口
        
        Args:
            interface_id: 接口ID
            **kwargs: 连接参数
            
        Returns:
            bool: 连接是否成功
        """
        interface = self.get_interface(interface_id)
        if not interface:
            logger.error(f"Interface '{interface_id}' not found")
            return False
        
        return interface.connect(**kwargs)
    
    def disconnect_interface(self, interface_id: str) -> bool:
        """
        断开CAN接口连接
        
        Args:
            interface_id: 接口ID
            
        Returns:
            bool: 断开是否成功
        """
        interface = self.get_interface(interface_id)
        if not interface:
            logger.error(f"Interface '{interface_id}' not found")
            return False
        
        return interface.disconnect()
    
    def send_frame(self, interface_id: str, frame: CANFrame) -> bool:
        """
        发送CAN帧
        
        Args:
            interface_id: 接口ID
            frame: CAN帧
            
        Returns:
            bool: 发送是否成功
        """
        interface = self.get_interface(interface_id)
        if not interface:
            logger.error(f"Interface '{interface_id}' not found")
            return False
        
        if not interface.is_connected:
            logger.error(f"Interface '{interface_id}' not connected")
            return False
        
        return interface.send_frame(frame)
    
    def get_all_interfaces(self) -> Dict[str, BaseCANInterface]:
        """
        获取所有接口
        
        Returns:
            dict: 所有接口
        """
        with self._lock:
            return self._interfaces.copy()
    
    def get_interface_info(self, interface_id: str) -> Optional[Dict[str, Any]]:
        """
        获取接口信息
        
        Args:
            interface_id: 接口ID
            
        Returns:
            dict or None: 接口信息
        """
        interface = self.get_interface(interface_id)
        if not interface:
            return None
        
        return interface.get_info()
    
    def get_statistics(self, interface_id: str) -> Optional[CANStatistics]:
        """
        获取接口统计信息
        
        Args:
            interface_id: 接口ID
            
        Returns:
            CANStatistics or None: 统计信息
        """
        interface = self.get_interface(interface_id)
        if not interface:
            return None
        
        return interface.statistics
    
    def clear_all_interfaces(self) -> None:
        """清空所有接口"""
        with self._lock:
            interface_ids = list(self._interfaces.keys())
            
            for interface_id in interface_ids:
                self.remove_interface(interface_id)