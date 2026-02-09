#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ISO-TP协议实现 - 基于ISO 15765-2:2022标准
支持CAN FD和标准CAN，完整实现UDS over CAN协议
"""

import logging
import time
import threading
import queue
import struct
from enum import IntEnum, Enum
from typing import Optional, Dict, List, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
import traceback

from .can_interface import CANFrame, CANInterfaceManager

logger = logging.getLogger(__name__)

class ISOTPFrameType(IntEnum):
    """ISO-TP帧类型"""
    SINGLE_FRAME = 0x00
    FIRST_FRAME = 0x01
    CONSECUTIVE_FRAME = 0x02
    FLOW_CONTROL_FRAME = 0x03

class ISOTPFlowStatus(IntEnum):
    """ISO-TP流控制状态"""
    CONTINUE = 0x00  # 继续发送
    WAIT = 0x01      # 等待
    OVERFLOW = 0x02  # 溢出

class ISOTPAddressingMode(Enum):
    """ISO-TP寻址模式"""
    NORMAL = "normal"      # 正常模式 (11/29位ID)
    EXTENDED = "extended"  # 扩展模式 (带地址扩展)
    MIXED = "mixed"       # 混合模式 (带地址和长度扩展)

class ISOTPState(Enum):
    """ISO-TP状态"""
    IDLE = "idle"                 # 空闲状态
    WAITING_FOR_FC = "waiting_fc" # 等待流控制帧
    TRANSMITTING = "transmitting" # 正在传输
    RECEIVING = "receiving"       # 正在接收
    TIMEOUT = "timeout"           # 超时
    ERROR = "error"               # 错误

@dataclass
class ISOTPConfig:
    """ISO-TP配置"""
    # 基本配置
    rx_id: int = 0x7E0          # 接收CAN ID
    tx_id: int = 0x7E8          # 发送CAN ID
    addressing_mode: ISOTPAddressingMode = ISOTPAddressingMode.NORMAL
    frame_type: str = "standard"  # standard or extended
    
    # 流控制参数
    st_min: int = 0            # 最小分离时间 (ms)
    block_size: int = 8        # 块大小
    separation_time: int = 0   # 分离时间 (ms)
    
    # CAN FD配置
    can_fd_enabled: bool = False
    fd_baudrate_switch: bool = True
    fd_bitrate_switch: bool = True
    fd_dlc: int = 64           # CAN FD DLC (0-64字节)
    
    # 定时参数 (ms)
    p2_timeout: int = 50       # P2客户端超时
    p2_extended: int = 5000    # P2*服务器超时
    p4_timeout: int = 5000     # P4传输层超时
    
    # 高级参数
    max_frame_size: int = 4095  # 最大帧大小
    max_consecutive_frames: int = 4096  # 最大连续帧数
    receive_timeout: int = 1000  # 接收超时 (ms)
    tx_padding: bool = True    # 发送时填充
    tx_padding_value: int = 0xCC  # 填充值
    
    def validate(self) -> bool:
        """验证配置"""
        if not 0x000 <= self.rx_id <= 0x7FF and not 0x000 <= self.rx_id <= 0x1FFFFFFF:
            return False
        if not 0x000 <= self.tx_id <= 0x7FF and not 0x000 <= self.tx_id <= 0x1FFFFFFF:
            return False
        if self.st_min < 0 or self.st_min > 127:
            return False
        if self.block_size < 0 or self.block_size > 255:
            return False
        if self.fd_dlc < 0 or self.fd_dlc > 64:
            return False
        return True

@dataclass
class ISOTPFrame:
    """ISO-TP帧"""
    frame_type: ISOTPFrameType
    data: bytes
    sequence_number: int = 0  # 用于连续帧
    flow_status: ISOTPFlowStatus = ISOTPFlowStatus.CONTINUE
    block_size: int = 0
    st_min: int = 0
    
    @property
    def is_single_frame(self) -> bool:
        """是否为单帧"""
        return self.frame_type == ISOTPFrameType.SINGLE_FRAME
    
    @property
    def is_first_frame(self) -> bool:
        """是否为第一帧"""
        return self.frame_type == ISOTPFrameType.FIRST_FRAME
    
    @property
    def is_consecutive_frame(self) -> bool:
        """是否为连续帧"""
        return self.frame_type == ISOTPFrameType.CONSECUTIVE_FRAME
    
    @property
    def is_flow_control_frame(self) -> bool:
        """是否为流控制帧"""
        return self.frame_type == ISOTPFrameType.FLOW_CONTROL_FRAME
    
    @property
    def length(self) -> int:
        """数据长度"""
        return len(self.data)

class ISOTPError(Exception):
    """ISO-TP错误基类"""
    pass

class ISOTPTimeoutError(ISOTPError):
    """ISO-TP超时错误"""
    pass

class ISOTPFlowControlError(ISOTPError):
    """ISO-TP流控制错误"""
    pass

class ISOTPFrameError(ISOTPError):
    """ISO-TP帧错误"""
    pass

class ISOTPProtocol:
    """ISO-TP协议处理器"""
    
    def __init__(self, config: ISOTPConfig):
        """
        初始化ISO-TP协议处理器
        
        Args:
            config: ISO-TP配置
        """
        self.config = config
        self.state = ISOTPState.IDLE
        
        # 发送状态
        self.tx_buffer = bytearray()
        self.tx_sequence = 0
        self.tx_total_length = 0
        self.tx_remaining = 0
        self.tx_next_frame_index = 0
        self.tx_block_counter = 0
        self.tx_last_time = 0
        
        # 接收状态
        self.rx_buffer = bytearray()
        self.rx_expected_length = 0
        self.rx_sequence = 0
        self.rx_next_sequence = 1
        self.rx_block_counter = 0
        self.rx_flow_status = ISOTPFlowStatus.CONTINUE
        self.rx_flow_st_min = 0
        self.rx_flow_block_size = 0
        self.rx_last_time = 0
        
        # 定时器
        self.timer_lock = threading.RLock()
        self.timer_start_time = 0
        self.timer_running = False
        self.timer_thread = None
        self.timer_stop_event = threading.Event()
        
        # 回调函数
        self.on_data_received = None
        self.on_transmission_complete = None
        self.on_error = None
        
        # 线程同步
        self.lock = threading.RLock()
        self.rx_queue = queue.Queue(maxsize=1000)
        self.tx_queue = queue.Queue(maxsize=1000)
        
        logger.info(f"ISO-TP protocol initialized with config: {config}")
    
    def reset(self) -> None:
        """重置协议状态"""
        with self.lock:
            self.state = ISOTPState.IDLE
            
            # 重置发送状态
            self.tx_buffer.clear()
            self.tx_sequence = 0
            self.tx_total_length = 0
            self.tx_remaining = 0
            self.tx_next_frame_index = 0
            self.tx_block_counter = 0
            self.tx_last_time = 0
            
            # 重置接收状态
            self.rx_buffer.clear()
            self.rx_expected_length = 0
            self.rx_sequence = 0
            self.rx_next_sequence = 1
            self.rx_block_counter = 0
            self.rx_flow_status = ISOTPFlowStatus.CONTINUE
            self.rx_flow_st_min = 0
            self.rx_flow_block_size = 0
            self.rx_last_time = 0
            
            # 停止定时器
            self.stop_timer()
            
            # 清空队列
            while not self.rx_queue.empty():
                try:
                    self.rx_queue.get_nowait()
                except queue.Empty:
                    break
            
            logger.debug("ISO-TP protocol reset")
    
    def encode_frame(self, isotp_frame: ISOTPFrame, is_fd: bool = False) -> Tuple[bytes, int]:
        """
        编码ISO-TP帧为CAN数据
        
        Args:
            isotp_frame: ISO-TP帧
            is_fd: 是否为CAN FD
            
        Returns:
            tuple: (CAN数据, DLC)
        """
        try:
            if is_fd:
                max_payload = 64  # CAN FD最大载荷
                dlc_table = self._get_fd_dlc_table()
            else:
                max_payload = 8   # 标准CAN最大载荷
                dlc_table = self._get_standard_dlc_table()
            
            if isotp_frame.is_single_frame:
                # 单帧
                data_length = len(isotp_frame.data)
                if data_length <= max_payload - 1:  # 1字节用于PCI
                    # 使用标准单帧格式
                    pci = (ISOTPFrameType.SINGLE_FRAME << 4) | data_length
                    frame_data = bytes([pci]) + isotp_frame.data
                else:
                    # 使用扩展单帧格式 (仅CAN FD支持)
                    if not is_fd or data_length > 4095:
                        raise ISOTPFrameError(f"Data too long for single frame: {data_length}")
                    
                    pci_byte1 = (ISOTPFrameType.SINGLE_FRAME << 4) | 0x00
                    pci_byte2 = data_length >> 8
                    pci_byte3 = data_length & 0xFF
                    frame_data = bytes([pci_byte1, pci_byte2, pci_byte3]) + isotp_frame.data
                
            elif isotp_frame.is_first_frame:
                # 第一帧
                data_length = len(isotp_frame.data)
                if data_length > self.config.max_frame_size:
                    raise ISOTPFrameError(f"Data too long: {data_length}")
                
                if data_length <= 0xFFF:  # 12位长度
                    pci_byte1 = (ISOTPFrameType.FIRST_FRAME << 4) | (data_length >> 8)
                    pci_byte2 = data_length & 0xFF
                    frame_data = bytes([pci_byte1, pci_byte2]) + isotp_frame.data
                else:  # 扩展长度 (仅CAN FD)
                    if not is_fd:
                        raise ISOTPFrameError("Extended length only supported in CAN FD")
                    
                    pci_byte1 = (ISOTPFrameType.FIRST_FRAME << 4) | 0x00
                    pci_byte2 = data_length >> 8
                    pci_byte3 = data_length & 0xFF
                    frame_data = bytes([pci_byte1, pci_byte2, pci_byte3]) + isotp_frame.data
                
            elif isotp_frame.is_consecutive_frame:
                # 连续帧
                sequence_number = isotp_frame.sequence_number & 0x0F
                pci = (ISOTPFrameType.CONSECUTIVE_FRAME << 4) | sequence_number
                frame_data = bytes([pci]) + isotp_frame.data
                
            elif isotp_frame.is_flow_control_frame:
                # 流控制帧
                pci = (ISOTPFrameType.FLOW_CONTROL_FRAME << 4) | isotp_frame.flow_status
                frame_data = bytes([pci, isotp_frame.block_size, isotp_frame.st_min])
            else:
                raise ISOTPFrameError(f"Unknown frame type: {isotp_frame.frame_type}")
            
            # 填充数据 (如果需要)
            if self.config.tx_padding and len(frame_data) < max_payload:
                padding = bytes([self.config.tx_padding_value] * (max_payload - len(frame_data)))
                frame_data += padding
            
            # 计算DLC
            dlc = self._calculate_dlc(len(frame_data), is_fd, dlc_table)
            
            return frame_data, dlc
            
        except Exception as e:
            logger.error(f"Error encoding ISO-TP frame: {e}")
            raise
    
    def decode_frame(self, can_data: bytes, is_fd: bool = False) -> Optional[ISOTPFrame]:
        """
        解码CAN数据为ISO-TP帧
        
        Args:
            can_data: CAN数据
            is_fd: 是否为CAN FD
            
        Returns:
            ISOTPFrame or None: 解码后的帧
        """
        try:
            if not can_data:
                return None
            
            # 获取PCI字节
            pci_byte = can_data[0]
            frame_type = (pci_byte >> 4) & 0x0F
            pci_low = pci_byte & 0x0F
            
            if frame_type == ISOTPFrameType.SINGLE_FRAME:
                # 单帧
                if pci_low == 0x00:
                    # 扩展单帧格式 (仅CAN FD)
                    if len(can_data) < 3:
                        return None
                    data_length = (can_data[1] << 8) | can_data[2]
                    data = can_data[3:3+data_length]
                else:
                    # 标准单帧格式
                    data_length = pci_low
                    data = can_data[1:1+data_length]
                
                return ISOTPFrame(
                    frame_type=ISOTPFrameType.SINGLE_FRAME,
                    data=data
                )
                
            elif frame_type == ISOTPFrameType.FIRST_FRAME:
                # 第一帧
                if pci_low == 0x00:
                    # 扩展长度格式
                    if len(can_data) < 4:
                        return None
                    data_length = (can_data[1] << 8) | can_data[2]
                    data = can_data[3:]
                else:
                    # 标准长度格式
                    data_length = ((pci_low & 0x0F) << 8) | can_data[1]
                    data = can_data[2:]
                
                return ISOTPFrame(
                    frame_type=ISOTPFrameType.FIRST_FRAME,
                    data=data,
                    sequence_number=0
                )
                
            elif frame_type == ISOTPFrameType.CONSECUTIVE_FRAME:
                # 连续帧
                sequence_number = pci_low
                data = can_data[1:]
                
                return ISOTPFrame(
                    frame_type=ISOTPFrameType.CONSECUTIVE_FRAME,
                    data=data,
                    sequence_number=sequence_number
                )
                
            elif frame_type == ISOTPFrameType.FLOW_CONTROL_FRAME:
                # 流控制帧
                if len(can_data) < 3:
                    return None
                
                flow_status = ISOTPFlowStatus(pci_low)
                block_size = can_data[1]
                st_min = can_data[2]
                
                return ISOTPFrame(
                    frame_type=ISOTPFrameType.FLOW_CONTROL_FRAME,
                    data=b'',
                    flow_status=flow_status,
                    block_size=block_size,
                    st_min=st_min
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error decoding ISO-TP frame: {e}")
            return None
    
    def send_data(self, data: bytes, callback: Optional[Callable] = None) -> bool:
        """
        发送数据
        
        Args:
            data: 要发送的数据
            callback: 发送完成回调
            
        Returns:
            bool: 是否成功启动发送
        """
        with self.lock:
            if self.state != ISOTPState.IDLE:
                logger.warning(f"Cannot send data in state: {self.state}")
                return False
            
            if len(data) > self.config.max_frame_size:
                logger.error(f"Data too long: {len(data)} > {self.config.max_frame_size}")
                return False
            
            # 设置发送状态
            self.tx_buffer = bytearray(data)
            self.tx_total_length = len(data)
            self.tx_remaining = len(data)
            self.tx_sequence = 0
            self.tx_next_frame_index = 0
            self.tx_block_counter = 0
            self.tx_last_time = time.time()
            
            # 设置回调
            if callback:
                self.on_transmission_complete = callback
            
            # 根据数据长度选择发送方式
            max_payload = 64 if self.config.can_fd_enabled else 7  # 减去PCI字节
            
            if len(data) <= max_payload:
                # 单帧传输
                self.state = ISOTPState.TRANSMITTING
                self._send_single_frame(data)
            else:
                # 多帧传输
                self.state = ISOTPState.WAITING_FOR_FC
                self._send_first_frame(data)
            
            # 启动定时器
            self.start_timer(self.config.p2_timeout / 1000.0)
            
            logger.debug(f"Started sending data, length: {len(data)}, multi-frame: {len(data) > max_payload}")
            return True
    
    def receive_data(self, timeout: float = None) -> Optional[bytes]:
        """
        接收数据
        
        Args:
            timeout: 超时时间 (秒)
            
        Returns:
            bytes or None: 接收到的数据
        """
        try:
            if timeout is None:
                timeout = self.config.receive_timeout / 1000.0
            
            return self.rx_queue.get(timeout=timeout)
        except queue.Empty:
            return None
        except Exception as e:
            logger.error(f"Error receiving data: {e}")
            return None
    
    def process_can_frame(self, can_frame: CANFrame) -> bool:
        """
        处理接收到的CAN帧
        
        Args:
            can_frame: CAN帧
            
        Returns:
            bool: 是否成功处理
        """
        try:
            # 检查CAN ID
            if can_frame.arbitration_id != self.config.rx_id:
                return False
            
            # 解码ISO-TP帧
            isotp_frame = self.decode_frame(can_frame.data, can_frame.is_fd)
            if not isotp_frame:
                return False
            
            # 处理帧
            if isotp_frame.is_single_frame:
                return self._process_single_frame(isotp_frame)
            elif isotp_frame.is_first_frame:
                return self._process_first_frame(isotp_frame)
            elif isotp_frame.is_consecutive_frame:
                return self._process_consecutive_frame(isotp_frame)
            elif isotp_frame.is_flow_control_frame:
                return self._process_flow_control_frame(isotp_frame)
            
            return False
            
        except Exception as e:
            logger.error(f"Error processing CAN frame: {e}")
            if self.on_error:
                self.on_error(f"Frame processing error: {e}")
            return False
    
    def _send_single_frame(self, data: bytes) -> None:
        """发送单帧"""
        isotp_frame = ISOTPFrame(
            frame_type=ISOTPFrameType.SINGLE_FRAME,
            data=data
        )
        
        # 编码并发送
        frame_data, dlc = self.encode_frame(isotp_frame, self.config.can_fd_enabled)
        
        # 将帧放入发送队列
        try:
            can_frame = CANFrame(
                timestamp=time.time(),
                arbitration_id=self.config.tx_id,
                data=frame_data,
                is_extended_id=(self.config.frame_type == "extended"),
                is_fd=self.config.can_fd_enabled,
                dlc=dlc
            )
            
            self.tx_queue.put(can_frame)
            
            # 更新状态
            self.state = ISOTPState.IDLE
            self.tx_buffer.clear()
            self.tx_total_length = 0
            
            # 停止定时器
            self.stop_timer()
            
            # 调用回调
            if self.on_transmission_complete:
                self.on_transmission_complete(True, data)
            
            logger.debug(f"Single frame sent, length: {len(data)}")
            
        except Exception as e:
            logger.error(f"Error sending single frame: {e}")
            self.state = ISOTPState.ERROR
            if self.on_error:
                self.on_error(f"Send error: {e}")
    
    def _send_first_frame(self, data: bytes) -> None:
        """发送第一帧"""
        # 计算第一帧的最大数据长度
        max_payload = 64 if self.config.can_fd_enabled else 6  # 减去PCI字节
        
        # 确保不超过最大长度
        first_frame_data = data[:max_payload]
        
        isotp_frame = ISOTPFrame(
            frame_type=ISOTPFrameType.FIRST_FRAME,
            data=first_frame_data
        )
        
        # 编码并发送
        frame_data, dlc = self.encode_frame(isotp_frame, self.config.can_fd_enabled)
        
        try:
            can_frame = CANFrame(
                timestamp=time.time(),
                arbitration_id=self.config.tx_id,
                data=frame_data,
                is_extended_id=(self.config.frame_type == "extended"),
                is_fd=self.config.can_fd_enabled,
                dlc=dlc
            )
            
            self.tx_queue.put(can_frame)
            
            # 更新状态
            self.tx_next_frame_index = len(first_frame_data)
            self.tx_remaining -= len(first_frame_data)
            
            logger.debug(f"First frame sent, remaining: {self.tx_remaining}")
            
        except Exception as e:
            logger.error(f"Error sending first frame: {e}")
            self.state = ISOTPState.ERROR
            if self.on_error:
                self.on_error(f"Send error: {e}")
    
    def _send_consecutive_frame(self) -> None:
        """发送连续帧"""
        if self.tx_remaining <= 0:
            logger.warning("No data remaining to send")
            return
        
        # 计算连续帧的最大数据长度
        max_payload = 64 if self.config.can_fd_enabled else 7  # 减去PCI字节
        
        # 获取数据
        start = self.tx_next_frame_index
        end = min(start + max_payload, self.tx_total_length)
        frame_data = self.tx_buffer[start:end]
        
        isotp_frame = ISOTPFrame(
            frame_type=ISOTPFrameType.CONSECUTIVE_FRAME,
            data=frame_data,
            sequence_number=self.tx_sequence
        )
        
        # 编码并发送
        can_frame_data, dlc = self.encode_frame(isotp_frame, self.config.can_fd_enabled)
        
        try:
            can_frame = CANFrame(
                timestamp=time.time(),
                arbitration_id=self.config.tx_id,
                data=can_frame_data,
                is_extended_id=(self.config.frame_type == "extended"),
                is_fd=self.config.can_fd_enabled,
                dlc=dlc
            )
            
            self.tx_queue.put(can_frame)
            
            # 更新状态
            self.tx_next_frame_index = end
            self.tx_remaining -= len(frame_data)
            self.tx_sequence = (self.tx_sequence + 1) & 0x0F
            self.tx_block_counter += 1
            self.tx_last_time = time.time()
            
            logger.debug(f"Consecutive frame {self.tx_sequence-1} sent, remaining: {self.tx_remaining}")
            
            # 检查是否完成
            if self.tx_remaining <= 0:
                self.state = ISOTPState.IDLE
                self.tx_buffer.clear()
                self.tx_total_length = 0
                
                # 停止定时器
                self.stop_timer()
                
                # 调用回调
                if self.on_transmission_complete:
                    self.on_transmission_complete(True, bytes(self.tx_buffer))
                
                logger.debug("Transmission complete")
            
        except Exception as e:
            logger.error(f"Error sending consecutive frame: {e}")
            self.state = ISOTPState.ERROR
            if self.on_error:
                self.on_error(f"Send error: {e}")
    
    def _send_flow_control_frame(self, status: ISOTPFlowStatus, block_size: int = 0, st_min: int = 0) -> None:
        """发送流控制帧"""
        isotp_frame = ISOTPFrame(
            frame_type=ISOTPFrameType.FLOW_CONTROL_FRAME,
            data=b'',
            flow_status=status,
            block_size=block_size,
            st_min=st_min
        )
        
        # 编码并发送
        frame_data, dlc = self.encode_frame(isotp_frame, self.config.can_fd_enabled)
        
        try:
            can_frame = CANFrame(
                timestamp=time.time(),
                arbitration_id=self.config.tx_id,
                data=frame_data,
                is_extended_id=(self.config.frame_type == "extended"),
                is_fd=self.config.can_fd_enabled,
                dlc=dlc
            )
            
            self.tx_queue.put(can_frame)
            
            logger.debug(f"Flow control frame sent: status={status}, block_size={block_size}, st_min={st_min}")
            
        except Exception as e:
            logger.error(f"Error sending flow control frame: {e}")
    
    def _process_single_frame(self, isotp_frame: ISOTPFrame) -> bool:
        """处理单帧"""
        try:
            # 将数据放入接收队列
            self.rx_queue.put(bytes(isotp_frame.data))
            
            logger.debug(f"Single frame received, length: {len(isotp_frame.data)}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing single frame: {e}")
            return False
    
    def _process_first_frame(self, isotp_frame: ISOTPFrame) -> bool:
        """处理第一帧"""
        try:
            # 检查状态
            if self.state != ISOTPState.IDLE:
                logger.warning(f"Cannot process first frame in state: {self.state}")
                return False
            
            # 计算总长度
            if len(isotp_frame.data) >= 2:
                # 从第一帧数据中提取长度
                length_bytes = isotp_frame.data[:2]
                self.rx_expected_length = (length_bytes[0] << 8) | length_bytes[1]
                
                # 保存数据
                self.rx_buffer = bytearray(isotp_frame.data[2:])
            else:
                logger.error("Invalid first frame data")
                return False
            
            # 更新状态
            self.state = ISOTPState.RECEIVING
            self.rx_sequence = 0
            self.rx_next_sequence = 1
            self.rx_block_counter = 0
            self.rx_last_time = time.time()
            
            # 发送流控制帧
            self._send_flow_control_frame(
                status=ISOTPFlowStatus.CONTINUE,
                block_size=self.config.block_size,
                st_min=self.config.st_min
            )
            
            # 启动定时器
            self.start_timer(self.config.p4_timeout / 1000.0)
            
            logger.debug(f"First frame received, expected length: {self.rx_expected_length}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing first frame: {e}")
            self.state = ISOTPState.ERROR
            return False
    
    def _process_consecutive_frame(self, isotp_frame: ISOTPFrame) -> bool:
        """处理连续帧"""
        try:
            # 检查状态
            if self.state != ISOTPState.RECEIVING:
                logger.warning(f"Cannot process consecutive frame in state: {self.state}")
                return False
            
            # 检查序列号
            expected_sequence = self.rx_next_sequence & 0x0F
            if isotp_frame.sequence_number != expected_sequence:
                logger.error(f"Sequence mismatch: expected {expected_sequence}, got {isotp_frame.sequence_number}")
                self.state = ISOTPState.ERROR
                return False
            
            # 添加数据到缓冲区
            self.rx_buffer.extend(isotp_frame.data)
            
            # 更新序列号
            self.rx_sequence = isotp_frame.sequence_number
            self.rx_next_sequence = (self.rx_next_sequence + 1) & 0x0F
            self.rx_block_counter += 1
            self.rx_last_time = time.time()
            
            # 检查是否完成
            if len(self.rx_buffer) >= self.rx_expected_length:
                # 接收完成
                received_data = bytes(self.rx_buffer[:self.rx_expected_length])
                self.rx_queue.put(received_data)
                
                # 重置状态
                self.state = ISOTPState.IDLE
                self.rx_buffer.clear()
                self.rx_expected_length = 0
                
                # 停止定时器
                self.stop_timer()
                
                logger.debug(f"Reception complete, length: {len(received_data)}")
            
            # 检查是否需要发送流控制帧
            elif self.rx_block_counter >= self.rx_flow_block_size and self.rx_flow_block_size > 0:
                self._send_flow_control_frame(
                    status=ISOTPFlowStatus.CONTINUE,
                    block_size=self.config.block_size,
                    st_min=self.config.st_min
                )
                self.rx_block_counter = 0
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing consecutive frame: {e}")
            self.state = ISOTPState.ERROR
            return False
    
    def _process_flow_control_frame(self, isotp_frame: ISOTPFrame) -> bool:
        """处理流控制帧"""
        try:
            # 检查状态
            if self.state != ISOTPState.WAITING_FOR_FC:
                logger.warning(f"Cannot process flow control frame in state: {self.state}")
                return False
            
            # 处理流控制状态
            if isotp_frame.flow_status == ISOTPFlowStatus.CONTINUE:
                # 继续发送
                self.state = ISOTPState.TRANSMITTING
                self.rx_flow_block_size = isotp_frame.block_size
                self.rx_flow_st_min = isotp_frame.st_min
                self.tx_block_counter = 0
                
                # 发送第一组连续帧
                for _ in range(min(isotp_frame.block_size, self.tx_remaining)):
                    if self.tx_remaining > 0:
                        self._send_consecutive_frame()
                    else:
                        break
                
                # 重启定时器
                self.start_timer(self.config.p2_timeout / 1000.0)
                
            elif isotp_frame.flow_status == ISOTPFlowStatus.WAIT:
                # 等待
                self.state = ISOTPState.WAITING_FOR_FC
                
                # 重启定时器，使用更长的超时
                self.start_timer(self.config.p2_extended / 1000.0)
                
            elif isotp_frame.flow_status == ISOTPFlowStatus.OVERFLOW:
                # 溢出错误
                logger.error("Flow control overflow")
                self.state = ISOTPState.ERROR
                if self.on_error:
                    self.on_error("Flow control overflow")
                return False
            
            logger.debug(f"Flow control frame processed: status={isotp_frame.flow_status}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing flow control frame: {e}")
            self.state = ISOTPState.ERROR
            return False
    
    def start_timer(self, timeout: float) -> None:
        """启动定时器"""
        with self.timer_lock:
            if self.timer_running:
                self.stop_timer()
            
            self.timer_start_time = time.time()
            self.timer_running = True
            self.timer_stop_event.clear()
            
            self.timer_thread = threading.Thread(
                target=self._timer_thread_func,
                args=(timeout,),
                daemon=True
            )
            self.timer_thread.start()
    
    def stop_timer(self) -> None:
        """停止定时器"""
        with self.timer_lock:
            self.timer_running = False
            self.timer_stop_event.set()
            
            if self.timer_thread and self.timer_thread.is_alive():
                self.timer_thread.join(timeout=0.1)
                self.timer_thread = None
    
    def _timer_thread_func(self, timeout: float) -> None:
        """定时器线程函数"""
        try:
            while self.timer_running and not self.timer_stop_event.is_set():
                elapsed = time.time() - self.timer_start_time
                
                if elapsed >= timeout:
                    # 超时处理
                    with self.lock:
                        if self.timer_running:
                            self.state = ISOTPState.TIMEOUT
                            
                            # 重置状态
                            self.reset()
                            
                            # 调用错误回调
                            if self.on_error:
                                self.on_error(f"Timeout after {elapsed:.2f}s")
                            
                            logger.warning(f"ISO-TP timeout after {elapsed:.2f}s")
                    
                    break
                
                # 休眠一段时间
                time.sleep(0.01)
                
        except Exception as e:
            logger.error(f"Timer thread error: {e}")
    
    def _calculate_dlc(self, data_length: int, is_fd: bool, dlc_table: Dict[int, int]) -> int:
        """计算DLC值"""
        for dlc, max_length in dlc_table.items():
            if data_length <= max_length:
                return dlc
        
        # 如果数据长度超过最大值，返回最大DLC
        return max(dlc_table.keys())
    
    def _get_standard_dlc_table(self) -> Dict[int, int]:
        """获取标准CAN DLC表"""
        return {
            0: 0, 1: 1, 2: 2, 3: 3, 4: 4,
            5: 5, 6: 6, 7: 7, 8: 8
        }
    
    def _get_fd_dlc_table(self) -> Dict[int, int]:
        """获取CAN FD DLC表"""
        return {
            0: 0, 1: 1, 2: 2, 3: 3, 4: 4,
            5: 5, 6: 6, 7: 7, 8: 8,
            9: 12, 10: 16, 11: 20, 12: 24,
            13: 32, 14: 48, 15: 64
        }
    
    def get_state(self) -> ISOTPState:
        """获取当前状态"""
        return self.state
    
    def get_tx_queue(self) -> queue.Queue:
        """获取发送队列"""
        return self.tx_queue
    
    def get_rx_queue(self) -> queue.Queue:
        """获取接收队列"""
        return self.rx_queue
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'state': self.state.value,
            'tx_total_length': self.tx_total_length,
            'tx_remaining': self.tx_remaining,
            'tx_sequence': self.tx_sequence,
            'tx_block_counter': self.tx_block_counter,
            'rx_expected_length': self.rx_expected_length,
            'rx_buffer_length': len(self.rx_buffer),
            'rx_sequence': self.rx_sequence,
            'rx_block_counter': self.rx_block_counter,
            'timer_running': self.timer_running,
            'tx_queue_size': self.tx_queue.qsize(),
            'rx_queue_size': self.rx_queue.qsize(),
        }

class ISOTPManager:
    """ISO-TP管理器"""
    
    def __init__(self):
        self.protocols: Dict[str, ISOTPProtocol] = {}
        self.lock = threading.RLock()
    
    def create_protocol(self, protocol_id: str, config: ISOTPConfig) -> Optional[ISOTPProtocol]:
        """
        创建ISO-TP协议实例
        
        Args:
            protocol_id: 协议ID
            config: 配置
            
        Returns:
            ISOTPProtocol or None: 协议实例
        """
        with self.lock:
            if protocol_id in self.protocols:
                logger.warning(f"Protocol '{protocol_id}' already exists")
                return self.protocols[protocol_id]
            
            try:
                if not config.validate():
                    logger.error(f"Invalid ISO-TP config: {config}")
                    return None
                
                protocol = ISOTPProtocol(config)
                self.protocols[protocol_id] = protocol
                
                logger.info(f"Created ISO-TP protocol '{protocol_id}'")
                return protocol
                
            except Exception as e:
                logger.error(f"Error creating ISO-TP protocol: {e}")
                return None
    
    def get_protocol(self, protocol_id: str) -> Optional[ISOTPProtocol]:
        """
        获取ISO-TP协议实例
        
        Args:
            protocol_id: 协议ID
            
        Returns:
            ISOTPProtocol or None: 协议实例
        """
        with self.lock:
            return self.protocols.get(protocol_id)
    
    def remove_protocol(self, protocol_id: str) -> bool:
        """
        移除ISO-TP协议实例
        
        Args:
            protocol_id: 协议ID
            
        Returns:
            bool: 是否成功移除
        """
        with self.lock:
            if protocol_id not in self.protocols:
                return False
            
            protocol = self.protocols[protocol_id]
            protocol.reset()
            del self.protocols[protocol_id]
            
            logger.info(f"Removed ISO-TP protocol '{protocol_id}'")
            return True
    
    def send_data(self, protocol_id: str, data: bytes, callback: Optional[Callable] = None) -> bool:
        """
        发送数据
        
        Args:
            protocol_id: 协议ID
            data: 要发送的数据
            callback: 回调函数
            
        Returns:
            bool: 是否成功发送
        """
        protocol = self.get_protocol(protocol_id)
        if not protocol:
            logger.error(f"Protocol '{protocol_id}' not found")
            return False
        
        return protocol.send_data(data, callback)
    
    def receive_data(self, protocol_id: str, timeout: float = None) -> Optional[bytes]:
        """
        接收数据
        
        Args:
            protocol_id: 协议ID
            timeout: 超时时间
            
        Returns:
            bytes or None: 接收到的数据
        """
        protocol = self.get_protocol(protocol_id)
        if not protocol:
            logger.error(f"Protocol '{protocol_id}' not found")
            return None
        
        return protocol.receive_data(timeout)
    
    def process_can_frame(self, can_frame: CANFrame) -> bool:
        """
        处理CAN帧
        
        Args:
            can_frame: CAN帧
            
        Returns:
            bool: 是否成功处理
        """
        with self.lock:
            for protocol_id, protocol in self.protocols.items():
                try:
                    if protocol.process_can_frame(can_frame):
                        logger.debug(f"CAN frame processed by protocol '{protocol_id}'")
                        return True
                except Exception as e:
                    logger.error(f"Error processing CAN frame in protocol '{protocol_id}': {e}")
            
            return False
    
    def get_all_protocols(self) -> Dict[str, ISOTPProtocol]:
        """获取所有协议"""
        with self.lock:
            return self.protocols.copy()
    
    def get_protocol_state(self, protocol_id: str) -> Optional[ISOTPState]:
        """获取协议状态"""
        protocol = self.get_protocol(protocol_id)
        if not protocol:
            return None
        
        return protocol.get_state()
    
    def get_protocol_statistics(self, protocol_id: str) -> Optional[Dict[str, Any]]:
        """获取协议统计信息"""
        protocol = self.get_protocol(protocol_id)
        if not protocol:
            return None
        
        return protocol.get_statistics()
    
    def reset_all_protocols(self) -> None:
        """重置所有协议"""
        with self.lock:
            for protocol_id in list(self.protocols.keys()):
                protocol = self.protocols[protocol_id]
                protocol.reset()
            
            logger.info("All ISO-TP protocols reset")