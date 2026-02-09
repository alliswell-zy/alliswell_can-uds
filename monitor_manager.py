#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控管理器 - 监控CAN总线数据，支持分离显示和实时监控
支持多种显示格式和过滤功能
"""

import logging
import time
import threading
import queue
import re
from enum import Enum
from typing import Optional, Dict, List, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime
import copy

from .can_interface import CANFrame, CANInterfaceManager, CANInterface
from .isotp_protocol import ISOTPManager, ISOTPProtocol
from .uds_session_manager import UDSSessionManager

logger = logging.getLogger(__name__)

class MonitorDisplayFormat(Enum):
    """监控显示格式"""
    HEX = "hex"          # 十六进制
    DEC = "dec"          # 十进制
    BIN = "bin"          # 二进制
    ASCII = "ascii"      # ASCII
    MIXED = "mixed"      # 混合格式

class MonitorFilterType(Enum):
    """监控过滤器类型"""
    ID_RANGE = "id_range"      # ID范围过滤
    ID_LIST = "id_list"        # ID列表过滤
    DATA_PATTERN = "data_pattern"  # 数据模式过滤
    CUSTOM = "custom"          # 自定义过滤

@dataclass
class MonitorFilter:
    """监控过滤器"""
    filter_type: MonitorFilterType
    enabled: bool = True
    name: str = ""
    
    # 过滤器参数
    id_range_start: int = 0x000
    id_range_end: int = 0x7FF
    id_list: List[int] = field(default_factory=list)
    data_pattern: str = ""  # 十六进制数据模式，支持通配符
    custom_function: Optional[Callable] = None
    
    def match(self, frame: CANFrame) -> bool:
        """检查帧是否匹配过滤器"""
        if not self.enabled:
            return True
        
        try:
            if self.filter_type == MonitorFilterType.ID_RANGE:
                return self.id_range_start <= frame.arbitration_id <= self.id_range_end
                
            elif self.filter_type == MonitorFilterType.ID_LIST:
                return frame.arbitration_id in self.id_list
                
            elif self.filter_type == MonitorFilterType.DATA_PATTERN:
                if not self.data_pattern:
                    return True
                
                # 将数据转换为十六进制字符串
                data_hex = frame.data.hex().upper()
                pattern = self.data_pattern.replace(' ', '').upper()
                
                # 支持通配符 '*'
                pattern_re = pattern.replace('*', '.*')
                return bool(re.match(pattern_re, data_hex))
                
            elif self.filter_type == MonitorFilterType.CUSTOM:
                if self.custom_function:
                    return self.custom_function(frame)
                return True
                
            else:
                return True
                
        except Exception as e:
            logger.error(f"Filter match error: {e}")
            return True

@dataclass
class MonitorDisplayConfig:
    """监控显示配置"""
    display_format: MonitorDisplayFormat = MonitorDisplayFormat.HEX
    show_timestamp: bool = True
    show_id: bool = True
    show_dlc: bool = True
    show_data: bool = True
    show_ascii: bool = False
    show_direction: bool = True
    show_channel: bool = True
    show_fd_flags: bool = True
    colorize_by_id: bool = True
    auto_scroll: bool = True
    max_display_lines: int = 1000
    timestamp_format: str = "absolute"  # absolute, relative, delta
    time_precision: int = 3  # 时间精度（毫秒）

@dataclass
class MonitorStatistics:
    """监控统计"""
    total_frames: int = 0
    rx_frames: int = 0
    tx_frames: int = 0
    error_frames: int = 0
    filtered_frames: int = 0
    start_time: float = field(default_factory=time.time)
    last_frame_time: float = 0
    
    def reset(self):
        """重置统计"""
        self.total_frames = 0
        self.rx_frames = 0
        self.tx_frames = 0
        self.error_frames = 0
        self.filtered_frames = 0
        self.start_time = time.time()
        self.last_frame_time = 0
    
    @property
    def uptime(self) -> float:
        """运行时间"""
        return time.time() - self.start_time
    
    @property
    def frame_rate(self) -> float:
        """帧率（帧/秒）"""
        if self.uptime > 0:
            return self.total_frames / self.uptime
        return 0
    
    @property
    def filtered_rate(self) -> float:
        """过滤率"""
        if self.total_frames > 0:
            return self.filtered_frames / self.total_frames * 100
        return 0

class MonitorFrame:
    """监控帧（用于显示）"""
    
    def __init__(self, can_frame: CANFrame, direction: str = "RX", source: str = "CAN"):
        """
        初始化监控帧
        
        Args:
            can_frame: CAN帧
            direction: 方向 (RX/TX)
            source: 来源 (CAN/ISO-TP/UDS)
        """
        self.can_frame = can_frame
        self.direction = direction  # RX: 接收, TX: 发送
        self.source = source
        self.timestamp = can_frame.timestamp
        self.formatted_data: Optional[str] = None
        
    def format(self, config: MonitorDisplayConfig) -> str:
        """格式化显示"""
        if self.formatted_data and not config.timestamp_format.startswith("relative"):
            return self.formatted_data
        
        parts = []
        
        # 时间戳
        if config.show_timestamp:
            if config.timestamp_format == "absolute":
                dt = datetime.fromtimestamp(self.timestamp)
                timestamp_str = dt.strftime("%H:%M:%S")
                if config.time_precision > 0:
                    millis = int((self.timestamp - int(self.timestamp)) * 1000)
                    timestamp_str += f".{millis:03d}"[:3 + config.time_precision]
            elif config.timestamp_format == "relative":
                elapsed = self.timestamp - config._reference_time
                timestamp_str = f"{elapsed:.3f}".rstrip('0').rstrip('.')
            else:  # delta
                if config._last_timestamp:
                    delta = self.timestamp - config._last_timestamp
                    timestamp_str = f"+{delta:.3f}".rstrip('0').rstrip('.')
                else:
                    timestamp_str = "0.000"
            parts.append(timestamp_str)
        
        # 方向
        if config.show_direction:
            parts.append(self.direction)
        
        # 通道
        if config.show_channel:
            parts.append(f"CH{self.can_frame.channel}")
        
        # ID
        if config.show_id:
            if self.can_frame.is_extended_id:
                id_str = f"{self.can_frame.arbitration_id:08X}"
            else:
                id_str = f"{self.can_frame.arbitration_id:03X}"
            parts.append(id_str)
        
        # DLC
        if config.show_dlc:
            dlc_str = f"DL{self.can_frame.dlc}"
            if self.can_frame.is_fd:
                dlc_str += "F"
            parts.append(dlc_str)
        
        # 数据
        if config.show_data:
            data_str = self._format_data(config.display_format)
            parts.append(data_str)
        
        # ASCII
        if config.show_ascii:
            ascii_str = self.can_frame.data_ascii
            parts.append(f"'{ascii_str}'")
        
        # CAN FD标志
        if config.show_fd_flags and self.can_frame.is_fd:
            flags = []
            if self.can_frame.bitrate_switch:
                flags.append("BRS")
            if self.can_frame.error_state_indicator:
                flags.append("ESI")
            if flags:
                parts.append(f"[{','.join(flags)}]")
        
        # 来源
        if self.source != "CAN":
            parts.append(f"({self.source})")
        
        self.formatted_data = " ".join(parts)
        return self.formatted_data
    
    def _format_data(self, format_type: MonitorDisplayFormat) -> str:
        """格式化数据"""
        if not self.can_frame.data:
            return ""
        
        if format_type == MonitorDisplayFormat.HEX:
            return self.can_frame.data.hex(' ').upper()
        elif format_type == MonitorDisplayFormat.DEC:
            dec_values = [str(byte) for byte in self.can_frame.data]
            return " ".join(dec_values)
        elif format_type == MonitorDisplayFormat.BIN:
            bin_values = [f"{byte:08b}" for byte in self.can_frame.data]
            return " ".join(bin_values)
        elif format_type == MonitorDisplayFormat.ASCII:
            ascii_str = ""
            for byte in self.can_frame.data:
                if 32 <= byte <= 126:
                    ascii_str += chr(byte)
                else:
                    ascii_str += "."
            return ascii_str
        elif format_type == MonitorDisplayFormat.MIXED:
            # 混合模式：显示十六进制，但可打印字符显示为ASCII
            mixed_str = ""
            for byte in self.can_frame.data:
                if 32 <= byte <= 126:
                    mixed_str += f"{chr(byte):>3}"
                else:
                    mixed_str += f"{byte:02X} "
            return mixed_str.strip()
        else:
            return self.can_frame.data.hex(' ').upper()

class MonitorManager:
    """监控管理器"""
    
    def __init__(self):
        """初始化监控管理器"""
        self.filters: List[MonitorFilter] = []
        self.config = MonitorDisplayConfig()
        self.statistics = MonitorStatistics()
        
        # 帧队列和缓冲区
        self.frame_queue = queue.Queue(maxsize=10000)
        self.display_buffer: List[MonitorFrame] = []
        self.buffer_lock = threading.RLock()
        self.buffer_max_size = 10000
        
        # 回调函数
        self.on_frame_received = None
        self.on_filter_changed = None
        self.on_config_changed = None
        
        # 线程控制
        self.running = False
        self.processing_thread: Optional[threading.Thread] = None
        self.callback_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # 保存的文件
        self.save_file = None
        self.save_enabled = False
        self.save_lock = threading.Lock()
        
        logger.info("Monitor manager initialized")
    
    def start(self) -> bool:
        """启动监控"""
        if self.running:
            logger.warning("Monitor is already running")
            return False
        
        self.running = True
        self.stop_event.clear()
        self.statistics.reset()
        
        # 启动处理线程
        self.processing_thread = threading.Thread(
            target=self._processing_thread_func,
            daemon=True,
            name="MonitorProcessing"
        )
        self.processing_thread.start()
        
        # 启动回调线程
        self.callback_thread = threading.Thread(
            target=self._callback_thread_func,
            daemon=True,
            name="MonitorCallback"
        )
        self.callback_thread.start()
        
        logger.info("Monitor started")
        return True
    
    def stop(self) -> bool:
        """停止监控"""
        if not self.running:
            return False
        
        self.running = False
        self.stop_event.set()
        
        # 等待线程结束
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=1.0)
        
        if self.callback_thread and self.callback_thread.is_alive():
            self.callback_thread.join(timeout=1.0)
        
        # 关闭保存文件
        self.stop_saving()
        
        # 清空缓冲区
        with self.buffer_lock:
            self.display_buffer.clear()
        
        logger.info("Monitor stopped")
        return True
    
    def add_frame(self, frame: MonitorFrame) -> bool:
        """
        添加帧到监控队列
        
        Args:
            frame: 监控帧
            
        Returns:
            bool: 是否添加成功
        """
        if not self.running:
            return False
        
        try:
            self.frame_queue.put_nowait(frame)
            return True
        except queue.Full:
            # 队列满时丢弃最旧的帧
            try:
                self.frame_queue.get_nowait()
                self.frame_queue.put_nowait(frame)
                return True
            except queue.Empty:
                return False
    
    def add_can_frame(self, can_frame: CANFrame, direction: str = "RX", source: str = "CAN") -> bool:
        """
        添加CAN帧到监控队列
        
        Args:
            can_frame: CAN帧
            direction: 方向
            source: 来源
            
        Returns:
            bool: 是否添加成功
        """
        monitor_frame = MonitorFrame(can_frame, direction, source)
        return self.add_frame(monitor_frame)
    
    def _processing_thread_func(self) -> None:
        """处理线程函数"""
        while self.running and not self.stop_event.is_set():
            try:
                # 从队列获取帧
                frame = self.frame_queue.get(timeout=0.1)
                
                # 应用过滤器
                if not self._apply_filters(frame):
                    self.statistics.filtered_frames += 1
                    continue
                
                # 更新统计
                self._update_statistics(frame)
                
                # 添加到显示缓冲区
                self._add_to_buffer(frame)
                
                # 保存到文件（如果启用）
                if self.save_enabled and self.save_file:
                    self._save_frame_to_file(frame)
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in monitor processing thread: {e}")
    
    def _callback_thread_func(self) -> None:
        """回调线程函数"""
        while self.running and not self.stop_event.is_set():
            try:
                # 从队列获取帧
                frame = self.frame_queue.get(timeout=0.1)
                
                # 应用过滤器
                if not self._apply_filters(frame):
                    continue
                
                # 调用回调函数
                if self.on_frame_received:
                    try:
                        self.on_frame_received(frame)
                    except Exception as e:
                        logger.error(f"Error in frame received callback: {e}")
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in monitor callback thread: {e}")
    
    def _apply_filters(self, frame: MonitorFrame) -> bool:
        """应用过滤器"""
        if not self.filters:
            return True
        
        # 如果没有任何启用的过滤器，显示所有帧
        enabled_filters = [f for f in self.filters if f.enabled]
        if not enabled_filters:
            return True
        
        # 应用过滤器（逻辑与）
        for filter_obj in enabled_filters:
            if not filter_obj.match(frame.can_frame):
                return False
        
        return True
    
    def _update_statistics(self, frame: MonitorFrame) -> None:
        """更新统计信息"""
        self.statistics.total_frames += 1
        
        if frame.direction == "RX":
            self.statistics.rx_frames += 1
        elif frame.direction == "TX":
            self.statistics.tx_frames += 1
        
        if frame.can_frame.is_error_frame:
            self.statistics.error_frames += 1
        
        self.statistics.last_frame_time = time.time()
    
    def _add_to_buffer(self, frame: MonitorFrame) -> None:
        """添加到显示缓冲区"""
        with self.buffer_lock:
            self.display_buffer.append(frame)
            
            # 限制缓冲区大小
            if len(self.display_buffer) > self.buffer_max_size:
                self.display_buffer = self.display_buffer[-self.buffer_max_size:]
    
    def _save_frame_to_file(self, frame: MonitorFrame) -> None:
        """保存帧到文件"""
        try:
            with self.save_lock:
                if self.save_file and not self.save_file.closed:
                    # 格式化帧
                    formatted_line = frame.format(self.config) + "\n"
                    self.save_file.write(formatted_line)
                    self.save_file.flush()
        except Exception as e:
            logger.error(f"Error saving frame to file: {e}")
    
    def get_frames(self, count: int = 100, start_index: int = -1) -> List[MonitorFrame]:
        """
        获取帧
        
        Args:
            count: 获取的数量
            start_index: 起始索引（负数表示从末尾开始）
            
        Returns:
            list: 监控帧列表
        """
        with self.buffer_lock:
            if not self.display_buffer:
                return []
            
            if start_index < 0:
                start_index = max(0, len(self.display_buffer) + start_index)
            
            end_index = min(start_index + count, len(self.display_buffer))
            return self.display_buffer[start_index:end_index]
    
    def get_formatted_frames(self, count: int = 100, start_index: int = -1) -> List[str]:
        """
        获取格式化后的帧
        
        Args:
            count: 获取的数量
            start_index: 起始索引
            
        Returns:
            list: 格式化后的帧字符串列表
        """
        frames = self.get_frames(count, start_index)
        return [frame.format(self.config) for frame in frames]
    
    def clear_buffer(self) -> None:
        """清空缓冲区"""
        with self.buffer_lock:
            self.display_buffer.clear()
        logger.info("Monitor buffer cleared")
    
    def add_filter(self, filter_obj: MonitorFilter) -> None:
        """添加过滤器"""
        self.filters.append(filter_obj)
        logger.debug(f"Added filter: {filter_obj.name}")
        
        # 通知过滤器变化
        if self.on_filter_changed:
            try:
                self.on_filter_changed()
            except Exception as e:
                logger.error(f"Error in filter changed callback: {e}")
    
    def remove_filter(self, filter_index: int) -> bool:
        """移除过滤器"""
        if 0 <= filter_index < len(self.filters):
            removed = self.filters.pop(filter_index)
            logger.debug(f"Removed filter: {removed.name}")
            
            # 通知过滤器变化
            if self.on_filter_changed:
                try:
                    self.on_filter_changed()
                except Exception as e:
                    logger.error(f"Error in filter changed callback: {e}")
            
            return True
        return False
    
    def update_filter(self, filter_index: int, filter_obj: MonitorFilter) -> bool:
        """更新过滤器"""
        if 0 <= filter_index < len(self.filters):
            self.filters[filter_index] = filter_obj
            logger.debug(f"Updated filter: {filter_obj.name}")
            
            # 通知过滤器变化
            if self.on_filter_changed:
                try:
                    self.on_filter_changed()
                except Exception as e:
                    logger.error(f"Error in filter changed callback: {e}")
            
            return True
        return False
    
    def get_filters(self) -> List[MonitorFilter]:
        """获取过滤器列表"""
        return copy.deepcopy(self.filters)
    
    def update_config(self, config: MonitorDisplayConfig) -> None:
        """更新配置"""
        self.config = config
        logger.debug("Monitor config updated")
        
        # 通知配置变化
        if self.on_config_changed:
            try:
                self.on_config_changed()
            except Exception as e:
                logger.error(f"Error in config changed callback: {e}")
    
    def start_saving(self, file_path: str) -> bool:
        """
        开始保存到文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否成功
        """
        try:
            self.stop_saving()  # 先停止现有的保存
            
            self.save_file = open(file_path, 'a', encoding='utf-8')
            self.save_enabled = True
            
            # 写入文件头
            header = f"# Monitor Log started at {datetime.now().isoformat()}\n"
            header += f"# Format: {self.config.display_format.value}\n"
            self.save_file.write(header)
            
            logger.info(f"Started saving monitor data to '{file_path}'")
            return True
            
        except Exception as e:
            logger.error(f"Error starting monitor save: {e}")
            self.save_enabled = False
            return False
    
    def stop_saving(self) -> None:
        """停止保存到文件"""
        if self.save_file and not self.save_file.closed:
            try:
                # 写入文件尾
                footer = f"# Monitor Log stopped at {datetime.now().isoformat()}\n"
                self.save_file.write(footer)
                self.save_file.close()
                logger.info("Stopped saving monitor data")
            except Exception as e:
                logger.error(f"Error stopping monitor save: {e}")
        
        self.save_file = None
        self.save_enabled = False
    
    def export_to_file(self, file_path: str, frame_count: int = 0) -> bool:
        """
        导出帧到文件
        
        Args:
            file_path: 文件路径
            frame_count: 导出的帧数量（0表示全部）
            
        Returns:
            bool: 是否成功
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                # 写入文件头
                f.write(f"# Monitor Export at {datetime.now().isoformat()}\n")
                f.write(f"# Total frames: {self.statistics.total_frames}\n")
                f.write(f"# Display format: {self.config.display_format.value}\n\n")
                
                # 获取帧
                if frame_count <= 0:
                    frames = self.get_frames()
                else:
                    frames = self.get_frames(min(frame_count, len(self.display_buffer)))
                
                # 写入帧数据
                for frame in frames:
                    formatted_line = frame.format(self.config)
                    f.write(formatted_line + "\n")
            
            logger.info(f"Exported {len(frames)} frames to '{file_path}'")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting monitor data: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_frames': self.statistics.total_frames,
            'rx_frames': self.statistics.rx_frames,
            'tx_frames': self.statistics.tx_frames,
            'error_frames': self.statistics.error_frames,
            'filtered_frames': self.statistics.filtered_frames,
            'uptime': self.statistics.uptime,
            'frame_rate': self.statistics.frame_rate,
            'filtered_rate': self.statistics.filtered_rate,
            'buffer_size': len(self.display_buffer),
            'queue_size': self.frame_queue.qsize(),
            'running': self.running,
        }
    
    def create_id_range_filter(self, name: str, start_id: int, end_id: int, enabled: bool = True) -> MonitorFilter:
        """创建ID范围过滤器"""
        return MonitorFilter(
            filter_type=MonitorFilterType.ID_RANGE,
            name=name,
            enabled=enabled,
            id_range_start=start_id,
            id_range_end=end_id
        )
    
    def create_id_list_filter(self, name: str, id_list: List[int], enabled: bool = True) -> MonitorFilter:
        """创建ID列表过滤器"""
        return MonitorFilter(
            filter_type=MonitorFilterType.ID_LIST,
            name=name,
            enabled=enabled,
            id_list=id_list
        )
    
    def create_data_pattern_filter(self, name: str, pattern: str, enabled: bool = True) -> MonitorFilter:
        """创建数据模式过滤器"""
        return MonitorFilter(
            filter_type=MonitorFilterType.DATA_PATTERN,
            name=name,
            enabled=enabled,
            data_pattern=pattern
        )
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.running

class MonitorService:
    """监控服务（集成CAN和ISO-TP监控）"""
    
    def __init__(self, can_manager: CANInterfaceManager, isotp_manager: ISOTPManager = None):
        """
        初始化监控服务
        
        Args:
            can_manager: CAN接口管理器
            isotp_manager: ISO-TP管理器
        """
        self.can_manager = can_manager
        self.isotp_manager = isotp_manager
        
        # 创建监控管理器
        self.monitor_manager = MonitorManager()
        
        # 注册的回调
        self.registered_callbacks: Dict[str, List[Callable]] = {}
        
        # 接口状态
        self.monitored_interfaces: Dict[str, bool] = {}
        
        logger.info("Monitor service initialized")
    
    def start_monitoring(self, interface_id: str = "default") -> bool:
        """
        开始监控指定接口
        
        Args:
            interface_id: 接口ID
            
        Returns:
            bool: 是否成功
        """
        # 获取CAN接口
        interface = self.can_manager.get_interface(interface_id)
        if not interface:
            logger.error(f"CAN interface '{interface_id}' not found")
            return False
        
        # 启动监控管理器（如果未启动）
        if not self.monitor_manager.is_running():
            self.monitor_manager.start()
        
        # 注册回调函数
        def can_frame_callback(frame: CANFrame):
            self.monitor_manager.add_can_frame(frame, "RX", f"CAN-{interface_id}")
        
        interface.add_callback(can_frame_callback)
        
        # 保存回调引用
        callback_key = f"can_rx_{interface_id}"
        self.registered_callbacks[callback_key] = [can_frame_callback]
        
        # 标记接口为已监控
        self.monitored_interfaces[interface_id] = True
        
        logger.info(f"Started monitoring CAN interface '{interface_id}'")
        return True
    
    def stop_monitoring(self, interface_id: str = "default") -> bool:
        """
        停止监控指定接口
        
        Args:
            interface_id: 接口ID
            
        Returns:
            bool: 是否成功
        """
        # 获取CAN接口
        interface = self.can_manager.get_interface(interface_id)
        if not interface:
            return False
        
        # 移除回调函数
        callback_key = f"can_rx_{interface_id}"
        if callback_key in self.registered_callbacks:
            for callback in self.registered_callbacks[callback_key]:
                interface.remove_callback(callback)
            del self.registered_callbacks[callback_key]
        
        # 标记接口为未监控
        self.monitored_interfaces[interface_id] = False
        
        logger.info(f"Stopped monitoring CAN interface '{interface_id}'")
        return True
    
    def start_monitoring_all(self) -> Dict[str, bool]:
        """开始监控所有接口"""
        results = {}
        interfaces = self.can_manager.get_all_interfaces()
        
        for interface_id in interfaces:
            results[interface_id] = self.start_monitoring(interface_id)
        
        return results
    
    def stop_monitoring_all(self) -> Dict[str, bool]:
        """停止监控所有接口"""
        results = {}
        
        for interface_id in list(self.monitored_interfaces.keys()):
            results[interface_id] = self.stop_monitoring(interface_id)
        
        return results
    
    def monitor_tx_frame(self, interface_id: str, frame: CANFrame) -> bool:
        """
        监控发送的帧
        
        Args:
            interface_id: 接口ID
            frame: CAN帧
            
        Returns:
            bool: 是否成功
        """
        return self.monitor_manager.add_can_frame(frame, "TX", f"CAN-{interface_id}")
    
    def monitor_uds_request(self, request: 'UDSRequest', interface_id: str = "default") -> bool:
        """
        监控UDS请求
        
        Args:
            request: UDS请求
            interface_id: 接口ID
            
        Returns:
            bool: 是否成功
        """
        # 创建CAN帧（模拟）
        can_frame = CANFrame(
            timestamp=time.time(),
            arbitration_id=0x7E0,  # 默认请求ID
            data=request.encode(),
            is_extended_id=False
        )
        
        return self.monitor_manager.add_can_frame(can_frame, "TX", f"UDS-{interface_id}")
    
    def monitor_uds_response(self, response: 'UDSResponse', interface_id: str = "default") -> bool:
        """
        监控UDS响应
        
        Args:
            response: UDS响应
            interface_id: 接口ID
            
        Returns:
            bool: 是否成功
        """
        # 创建响应数据
        response_data = bytes([response.service_id + 0x40]) + response.data
        
        # 创建CAN帧（模拟）
        can_frame = CANFrame(
            timestamp=time.time(),
            arbitration_id=0x7E8,  # 默认响应ID
            data=response_data,
            is_extended_id=False
        )
        
        return self.monitor_manager.add_can_frame(can_frame, "RX", f"UDS-{interface_id}")
    
    def get_monitor_manager(self) -> MonitorManager:
        """获取监控管理器"""
        return self.monitor_manager
    
    def set_monitor_callbacks(self, **callbacks) -> None:
        """设置监控回调"""
        for callback_name, callback_func in callbacks.items():
            if hasattr(self.monitor_manager, callback_name):
                setattr(self.monitor_manager, callback_name, callback_func)
    
    def create_detached_monitor_window(self) -> Dict[str, Any]:
        """创建分离的监控窗口数据"""
        # 获取当前配置和过滤器
        config = copy.deepcopy(self.monitor_manager.config)
        filters = copy.deepcopy(self.monitor_manager.filters)
        statistics = self.monitor_manager.get_statistics()
        
        # 获取最近的帧
        recent_frames = self.monitor_manager.get_formatted_frames(100)
        
        return {
            'config': config,
            'filters': filters,
            'statistics': statistics,
            'recent_frames': recent_frames,
            'timestamp': time.time()
        }
    
    def apply_detached_monitor_data(self, data: Dict[str, Any]) -> bool:
        """应用分离的监控窗口数据"""
        try:
            if 'config' in data:
                self.monitor_manager.update_config(data['config'])
            
            if 'filters' in data:
                self.monitor_manager.filters = data['filters']
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying detached monitor data: {e}")
            return False
    
    def is_monitoring(self, interface_id: str) -> bool:
        """检查是否正在监控指定接口"""
        return self.monitored_interfaces.get(interface_id, False)
    
    def get_monitored_interfaces(self) -> List[str]:
        """获取正在监控的接口列表"""
        return [iface for iface, monitoring in self.monitored_interfaces.items() if monitoring]
    
    def close(self) -> None:
        """关闭监控服务"""
        # 停止监控所有接口
        self.stop_monitoring_all()
        
        # 停止监控管理器
        self.monitor_manager.stop()
        
        # 清理回调
        self.registered_callbacks.clear()
        
        logger.info("Monitor service closed")