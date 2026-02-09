#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UDS会话管理器 - 实现ISO 14229-1诊断协议
支持完整的UDS服务，包括CAN FD UDS
"""

import logging
import time
import threading
import struct
import queue
from enum import IntEnum
from typing import Optional, Dict, List, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
import traceback

from .isotp_protocol import ISOTPManager, ISOTPConfig, ISOTPProtocol
from .can_interface import CANFrame, CANInterfaceManager
from config.protocol_definitions import (
    UDSServiceID, DiagnosticSessionType, ResetType, AccessMode,
    CommunicationControlType, RoutineControlType, ControlDTCSettingType,
    LinkControlType, ProtocolDefinitions, UDSServiceDefinition
)

logger = logging.getLogger(__name__)

class UDSResponseCode(IntEnum):
    """UDS响应码"""
    POSITIVE_RESPONSE = 0x40
    NEGATIVE_RESPONSE = 0x7F

class UDSNegativeResponseCode(IntEnum):
    """UDS否定响应码"""
    GENERAL_REJECT = 0x10
    SERVICE_NOT_SUPPORTED = 0x11
    SUBFUNCTION_NOT_SUPPORTED = 0x12
    INCORRECT_MESSAGE_LENGTH_OR_FORMAT = 0x13
    RESPONSE_TOO_LONG = 0x14
    BUSY_REPEAT_REQUEST = 0x21
    CONDITIONS_NOT_CORRECT = 0x22
    REQUEST_SEQUENCE_ERROR = 0x24
    NO_RESPONSE_FROM_SUBNET_COMPONENT = 0x25
    FAILURE_PREVENTS_EXECUTION_OF_REQUESTED_ACTION = 0x26
    REQUEST_OUT_OF_RANGE = 0x31
    SECURITY_ACCESS_DENIED = 0x33
    INVALID_KEY = 0x35
    EXCEEDED_NUMBER_OF_ATTEMPTS = 0x36
    REQUIRED_TIME_DELAY_NOT_EXPIRED = 0x37
    UPLOAD_DOWNLOAD_NOT_ACCEPTED = 0x70
    TRANSFER_DATA_SUSPENDED = 0x71
    GENERAL_PROGRAMMING_FAILURE = 0x72
    WRONG_BLOCK_SEQUENCE_COUNTER = 0x73
    REQUEST_CORRECTLY_RECEIVED_RESPONSE_PENDING = 0x78
    SUBFUNCTION_NOT_SUPPORTED_IN_ACTIVE_SESSION = 0x7E
    SERVICE_NOT_SUPPORTED_IN_ACTIVE_SESSION = 0x7F
    RPM_TOO_HIGH = 0x81
    RPM_TOO_LOW = 0x82
    ENGINE_IS_RUNNING = 0x83
    ENGINE_IS_NOT_RUNNING = 0x84
    ENGINE_RUN_TIME_TOO_LOW = 0x85
    TEMPERATURE_TOO_HIGH = 0x86
    TEMPERATURE_TOO_LOW = 0x87
    VEHICLE_SPEED_TOO_HIGH = 0x88
    VEHICLE_SPEED_TOO_LOW = 0x89
    THROTTLE_PEDAL_TOO_HIGH = 0x8A
    THROTTLE_PEDAL_TOO_LOW = 0x8B
    TRANSMISSION_RANGE_NOT_IN_NEUTRAL = 0x8C
    TRANSMISSION_RANGE_NOT_IN_GEAR = 0x8D
    BRAKE_SWITCH_NOT_CLOSED = 0x8F
    SHIFTER_LEVER_NOT_IN_PARK = 0x90
    TORQUE_CONVERTER_CLUTCH_LOCKED = 0x91
    VOLTAGE_TOO_HIGH = 0x92
    VOLTAGE_TOO_LOW = 0x93
    RESOURCE_TEMPORARILY_NOT_AVAILABLE = 0x94

@dataclass
class UDSRequest:
    """UDS请求"""
    service_id: int
    data: bytes = field(default_factory=bytes)
    subfunction: Optional[int] = None
    timeout: int = 2000  # 毫秒
    expect_response: bool = True
    
    def encode(self) -> bytes:
        """编码UDS请求"""
        if self.subfunction is not None:
            return bytes([self.service_id, self.subfunction]) + self.data
        else:
            return bytes([self.service_id]) + self.data

@dataclass
class UDSResponse:
    """UDS响应"""
    service_id: int
    data: bytes = field(default_factory=bytes)
    subfunction: Optional[int] = None
    response_code: UDSResponseCode = UDSResponseCode.POSITIVE_RESPONSE
    negative_response_code: Optional[UDSNegativeResponseCode] = None
    timestamp: float = field(default_factory=time.time)
    request: Optional[UDSRequest] = None
    
    @property
    def is_positive(self) -> bool:
        """是否为肯定响应"""
        return self.response_code == UDSResponseCode.POSITIVE_RESPONSE
    
    @property
    def is_negative(self) -> bool:
        """是否为否定响应"""
        return self.response_code == UDSResponseCode.NEGATIVE_RESPONSE
    
    def decode(self) -> Dict[str, Any]:
        """解码响应数据"""
        result = {
            'service_id': self.service_id,
            'is_positive': self.is_positive,
            'is_negative': self.is_negative,
            'timestamp': self.timestamp,
            'raw_data': self.data.hex().upper(),
        }
        
        if self.is_negative and self.negative_response_code:
            result['negative_response_code'] = self.negative_response_code.name
            result['negative_response_description'] = self._get_nrc_description(self.negative_response_code)
        
        return result
    
    def _get_nrc_description(self, nrc: UDSNegativeResponseCode) -> str:
        """获取否定响应码描述"""
        descriptions = {
            UDSNegativeResponseCode.GENERAL_REJECT: "一般拒绝",
            UDSNegativeResponseCode.SERVICE_NOT_SUPPORTED: "不支持的服务",
            UDSNegativeResponseCode.SUBFUNCTION_NOT_SUPPORTED: "不支持的子功能",
            UDSNegativeResponseCode.INCORRECT_MESSAGE_LENGTH_OR_FORMAT: "消息长度或格式不正确",
            UDSNegativeResponseCode.RESPONSE_TOO_LONG: "响应太长",
            UDSNegativeResponseCode.BUSY_REPEAT_REQUEST: "忙，重复请求",
            UDSNegativeResponseCode.CONDITIONS_NOT_CORRECT: "条件不正确",
            UDSNegativeResponseCode.REQUEST_SEQUENCE_ERROR: "请求序列错误",
            UDSNegativeResponseCode.NO_RESPONSE_FROM_SUBNET_COMPONENT: "子网组件无响应",
            UDSNegativeResponseCode.FAILURE_PREVENTS_EXECUTION_OF_REQUESTED_ACTION: "故障阻止执行请求的操作",
            UDSNegativeResponseCode.REQUEST_OUT_OF_RANGE: "请求超出范围",
            UDSNegativeResponseCode.SECURITY_ACCESS_DENIED: "安全访问被拒绝",
            UDSNegativeResponseCode.INVALID_KEY: "无效密钥",
            UDSNegativeResponseCode.EXCEEDED_NUMBER_OF_ATTEMPTS: "超过尝试次数",
            UDSNegativeResponseCode.REQUIRED_TIME_DELAY_NOT_EXPIRED: "所需时间延迟未到期",
            UDSNegativeResponseCode.UPLOAD_DOWNLOAD_NOT_ACCEPTED: "上传/下载不被接受",
            UDSNegativeResponseCode.TRANSFER_DATA_SUSPENDED: "传输数据已暂停",
            UDSNegativeResponseCode.GENERAL_PROGRAMMING_FAILURE: "一般编程失败",
            UDSNegativeResponseCode.WRONG_BLOCK_SEQUENCE_COUNTER: "错误的块序列计数器",
            UDSNegativeResponseCode.REQUEST_CORRECTLY_RECEIVED_RESPONSE_PENDING: "请求正确接收，响应待定",
            UDSNegativeResponseCode.SUBFUNCTION_NOT_SUPPORTED_IN_ACTIVE_SESSION: "活动会话中不支持的子功能",
            UDSNegativeResponseCode.SERVICE_NOT_SUPPORTED_IN_ACTIVE_SESSION: "活动会话中不支持的服务",
            UDSNegativeResponseCode.RPM_TOO_HIGH: "RPM过高",
            UDSNegativeResponseCode.RPM_TOO_LOW: "RPM过低",
            UDSNegativeResponseCode.ENGINE_IS_RUNNING: "发动机正在运行",
            UDSNegativeResponseCode.ENGINE_IS_NOT_RUNNING: "发动机未运行",
            UDSNegativeResponseCode.ENGINE_RUN_TIME_TOO_LOW: "发动机运行时间太短",
            UDSNegativeResponseCode.TEMPERATURE_TOO_HIGH: "温度过高",
            UDSNegativeResponseCode.TEMPERATURE_TOO_LOW: "温度过低",
            UDSNegativeResponseCode.VEHICLE_SPEED_TOO_HIGH: "车速过高",
            UDSNegativeResponseCode.VEHICLE_SPEED_TOO_LOW: "车速过低",
            UDSNegativeResponseCode.THROTTLE_PEDAL_TOO_HIGH: "油门踏板过高",
            UDSNegativeResponseCode.THROTTLE_PEDAL_TOO_LOW: "油门踏板过低",
            UDSNegativeResponseCode.TRANSMISSION_RANGE_NOT_IN_NEUTRAL: "变速器不在空档",
            UDSNegativeResponseCode.TRANSMISSION_RANGE_NOT_IN_GEAR: "变速器不在档位",
            UDSNegativeResponseCode.BRAKE_SWITCH_NOT_CLOSED: "刹车开关未闭合",
            UDSNegativeResponseCode.SHIFTER_LEVER_NOT_IN_PARK: "换档杆不在停车档",
            UDSNegativeResponseCode.TORQUE_CONVERTER_CLUTCH_LOCKED: "变矩器离合器锁定",
            UDSNegativeResponseCode.VOLTAGE_TOO_HIGH: "电压过高",
            UDSNegativeResponseCode.VOLTAGE_TOO_LOW: "电压过低",
            UDSNegativeResponseCode.RESOURCE_TEMPORARILY_NOT_AVAILABLE: "资源暂时不可用",
        }
        
        return descriptions.get(nrc, "未知错误")

@dataclass
class UDSSessionInfo:
    """UDS会话信息"""
    current_session: DiagnosticSessionType = DiagnosticSessionType.DEFAULT_SESSION
    security_level: int = 0
    p2_server_max: int = 50  # ms
    p2_star_server_max: int = 5000  # ms
    session_start_time: float = field(default_factory=time.time)
    
    @property
    def session_duration(self) -> float:
        """会话持续时间"""
        return time.time() - self.session_start_time

class UDSSessionManager:
    """UDS会话管理器"""
    
    def __init__(self, isotp_manager: ISOTPManager, protocol_id: str = "uds"):
        """
        初始化UDS会话管理器
        
        Args:
            isotp_manager: ISO-TP管理器
            protocol_id: 协议ID
        """
        self.isotp_manager = isotp_manager
        self.protocol_id = protocol_id
        
        # 协议定义
        self.protocol_defs = ProtocolDefinitions()
        
        # 会话状态
        self.session_info = UDSSessionInfo()
        self.security_seed: Optional[bytes] = None
        self.security_key: Optional[bytes] = None
        self.ecu_reset_allowed: bool = True
        
        # 响应队列
        self.response_queue = queue.Queue(maxsize=100)
        self.response_callbacks: Dict[int, Callable] = {}
        
        # 线程同步
        self.lock = threading.RLock()
        self.response_timeout = 2000  # 默认超时2秒
        self.response_thread = None
        self.response_thread_running = False
        
        # 启动响应处理线程
        self.start_response_thread()
        
        logger.info(f"UDS session manager initialized with protocol ID: {protocol_id}")
    
    def start_response_thread(self) -> None:
        """启动响应处理线程"""
        if self.response_thread_running:
            return
        
        self.response_thread_running = True
        self.response_thread = threading.Thread(
            target=self._response_thread_func,
            daemon=True,
            name="UDSResponseThread"
        )
        self.response_thread.start()
        
        logger.debug("UDS response thread started")
    
    def stop_response_thread(self) -> None:
        """停止响应处理线程"""
        self.response_thread_running = False
        if self.response_thread and self.response_thread.is_alive():
            self.response_thread.join(timeout=1.0)
            self.response_thread = None
        
        logger.debug("UDS response thread stopped")
    
    def _response_thread_func(self) -> None:
        """响应处理线程函数"""
        while self.response_thread_running:
            try:
                # 从ISO-TP接收数据
                data = self.isotp_manager.receive_data(self.protocol_id, timeout=0.1)
                if data:
                    self._process_response(data)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in response thread: {e}")
                time.sleep(0.1)
    
    def _process_response(self, data: bytes) -> None:
        """处理响应数据"""
        try:
            if len(data) < 1:
                logger.warning("Empty response data")
                return
            
            # 检查是否为否定响应
            if data[0] == UDSResponseCode.NEGATIVE_RESPONSE and len(data) >= 3:
                # 否定响应格式: 0x7F SID NRC
                service_id = data[1]
                negative_response_code = UDSNegativeResponseCode(data[2])
                
                response = UDSResponse(
                    service_id=service_id,
                    data=data[3:] if len(data) > 3 else b'',
                    response_code=UDSResponseCode.NEGATIVE_RESPONSE,
                    negative_response_code=negative_response_code,
                    timestamp=time.time()
                )
                
                logger.warning(f"Negative response: SID=0x{service_id:02X}, NRC=0x{negative_response_code.value:02X}")
                
            elif data[0] == UDSResponseCode.POSITIVE_RESPONSE and len(data) >= 1:
                # 肯定响应格式: SID+0x40 [data]
                service_id = data[0] - UDSResponseCode.POSITIVE_RESPONSE
                response_data = data[1:]
                
                response = UDSResponse(
                    service_id=service_id,
                    data=response_data,
                    response_code=UDSResponseCode.POSITIVE_RESPONSE,
                    timestamp=time.time()
                )
                
                logger.debug(f"Positive response: SID=0x{service_id:02X}, length={len(response_data)}")
            else:
                logger.warning(f"Invalid response format: {data.hex()}")
                return
            
            # 将响应放入队列
            self.response_queue.put(response)
            
            # 调用回调函数（如果有）
            if service_id in self.response_callbacks:
                try:
                    self.response_callbacks[service_id](response)
                except Exception as e:
                    logger.error(f"Error in response callback for SID 0x{service_id:02X}: {e}")
            
        except Exception as e:
            logger.error(f"Error processing response: {e}")
            traceback.print_exc()
    
    def send_request(self, request: UDSRequest, timeout: int = None) -> Optional[UDSResponse]:
        """
        发送UDS请求并等待响应
        
        Args:
            request: UDS请求
            timeout: 超时时间（毫秒），None使用默认值
            
        Returns:
            UDSResponse or None: 响应数据
        """
        if timeout is None:
            timeout = request.timeout if request.timeout else self.response_timeout
        
        # 编码请求数据
        request_data = request.encode()
        
        # 注册响应回调（如果需要）
        if request.expect_response:
            response_received = threading.Event()
            response_data = []
            
            def response_callback(response: UDSResponse):
                if response.service_id == request.service_id:
                    response_data.append(response)
                    response_received.set()
            
            self.response_callbacks[request.service_id] = response_callback
        
        try:
            # 发送请求
            logger.debug(f"Sending UDS request: SID=0x{request.service_id:02X}, data={request_data.hex().upper()}")
            
            success = self.isotp_manager.send_data(
                self.protocol_id,
                request_data,
                callback=None  # 我们使用单独的响应处理
            )
            
            if not success:
                logger.error("Failed to send UDS request")
                if request.expect_response and request.service_id in self.response_callbacks:
                    del self.response_callbacks[request.service_id]
                return None
            
            # 等待响应
            if request.expect_response:
                if response_received.wait(timeout / 1000.0):
                    if response_data:
                        response = response_data[0]
                        response.request = request
                        return response
                else:
                    logger.warning(f"Timeout waiting for response to SID 0x{request.service_id:02X}")
                    return None
            else:
                # 不需要响应
                return UDSResponse(
                    service_id=request.service_id,
                    response_code=UDSResponseCode.POSITIVE_RESPONSE,
                    timestamp=time.time(),
                    request=request
                )
                
        except Exception as e:
            logger.error(f"Error sending UDS request: {e}")
            return None
        finally:
            # 清理回调
            if request.expect_response and request.service_id in self.response_callbacks:
                del self.response_callbacks[request.service_id]
    
    # ========== 标准UDS服务方法 ==========
    
    def diagnostic_session_control(self, session_type: DiagnosticSessionType) -> Optional[UDSResponse]:
        """
        诊断会话控制 (0x10)
        
        Args:
            session_type: 会话类型
            
        Returns:
            UDSResponse or None: 响应
        """
        request = UDSRequest(
            service_id=UDSServiceID.DIAGNOSTIC_SESSION_CONTROL,
            subfunction=session_type,
            timeout=5000
        )
        
        response = self.send_request(request)
        if response and response.is_positive and len(response.data) >= 4:
            # 解析P2和P2*参数
            try:
                self.session_info.p2_server_max = struct.unpack('>H', response.data[0:2])[0]
                self.session_info.p2_star_server_max = struct.unpack('>H', response.data[2:4])[0]
                self.session_info.current_session = session_type
                self.session_info.session_start_time = time.time()
                logger.info(f"Session changed to {session_type.name}, P2={self.session_info.p2_server_max}ms, P2*={self.session_info.p2_star_server_max}ms")
            except Exception as e:
                logger.error(f"Error parsing session control response: {e}")
        
        return response
    
    def ecu_reset(self, reset_type: ResetType) -> Optional[UDSResponse]:
        """
        ECU复位 (0x11)
        
        Args:
            reset_type: 复位类型
            
        Returns:
            UDSResponse or None: 响应
        """
        request = UDSRequest(
            service_id=UDSServiceID.ECU_RESET,
            subfunction=reset_type,
            timeout=10000  # 复位可能需要更长时间
        )
        
        return self.send_request(request)
    
    def clear_diagnostic_information(self, group_of_dtc: int) -> Optional[UDSResponse]:
        """
        清除诊断信息 (0x14)
        
        Args:
            group_of_dtc: DTC组
            
        Returns:
            UDSResponse or None: 响应
        """
        # 编码DTC组 (3字节)
        dtc_bytes = group_of_dtc.to_bytes(3, 'big')
        
        request = UDSRequest(
            service_id=UDSServiceID.CLEAR_DIAGNOSTIC_INFORMATION,
            data=dtc_bytes,
            timeout=5000
        )
        
        return self.send_request(request)
    
    def read_dtc_information(self, subfunction: int, **kwargs) -> Optional[UDSResponse]:
        """
        读取DTC信息 (0x19)
        
        Args:
            subfunction: 子功能
            **kwargs: 额外参数
            
        Returns:
            UDSResponse or None: 响应
        """
        # 构建请求数据
        data = bytes([subfunction])
        
        # 根据子功能添加额外参数
        if subfunction == 0x01:  # reportNumberOfDTCByStatusMask
            if 'status_mask' in kwargs:
                data += kwargs['status_mask'].to_bytes(1, 'big')
        elif subfunction == 0x02:  # reportDTCByStatusMask
            if 'status_mask' in kwargs:
                data += kwargs['status_mask'].to_bytes(1, 'big')
            if 'dtc_format' in kwargs:
                data += kwargs['dtc_format'].to_bytes(1, 'big')
        elif subfunction == 0x03:  # reportDTCSnapshotIdentification
            if 'dtc' in kwargs:
                data += kwargs['dtc'].to_bytes(3, 'big')
        elif subfunction == 0x04:  # reportDTCSnapshotRecordByDTCNumber
            if 'dtc' in kwargs:
                data += kwargs['dtc'].to_bytes(3, 'big')
            if 'record_number' in kwargs:
                data += kwargs['record_number'].to_bytes(1, 'big')
        
        request = UDSRequest(
            service_id=UDSServiceID.READ_DTC_INFORMATION,
            subfunction=subfunction,
            data=data,
            timeout=5000
        )
        
        return self.send_request(request)
    
    def read_data_by_identifier(self, data_identifier: int) -> Optional[UDSResponse]:
        """
        通过标识符读取数据 (0x22)
        
        Args:
            data_identifier: 数据标识符
            
        Returns:
            UDSResponse or None: 响应
        """
        data = data_identifier.to_bytes(2, 'big')
        
        request = UDSRequest(
            service_id=UDSServiceID.READ_DATA_BY_IDENTIFIER,
            data=data,
            timeout=2000
        )
        
        return self.send_request(request)
    
    def read_memory_by_address(self, memory_address: int, memory_size: int) -> Optional[UDSResponse]:
        """
        通过地址读取内存 (0x23)
        
        Args:
            memory_address: 内存地址
            memory_size: 内存大小
            
        Returns:
            UDSResponse or None: 响应
        """
        # 地址和大小格式
        address_and_length_format = 0x44  # 4字节地址，4字节长度
        data = bytes([address_and_length_format])
        
        # 添加地址和大小
        data += memory_address.to_bytes(4, 'big')
        data += memory_size.to_bytes(4, 'big')
        
        request = UDSRequest(
            service_id=UDSServiceID.READ_MEMORY_BY_ADDRESS,
            data=data,
            timeout=5000
        )
        
        return self.send_request(request)
    
    def read_scaling_data_by_identifier(self, data_identifier: int) -> Optional[UDSResponse]:
        """
        通过标识符读取缩放数据 (0x24)
        
        Args:
            data_identifier: 数据标识符
            
        Returns:
            UDSResponse or None: 响应
        """
        data = data_identifier.to_bytes(2, 'big')
        
        request = UDSRequest(
            service_id=UDSServiceID.READ_SCALING_DATA_BY_IDENTIFIER,
            data=data,
            timeout=2000
        )
        
        return self.send_request(request)
    
    def security_access(self, access_mode: AccessMode, security_key: bytes = None) -> Optional[UDSResponse]:
        """
        安全访问 (0x27)
        
        Args:
            access_mode: 访问模式
            security_key: 安全密钥（仅当access_mode为偶数时）
            
        Returns:
            UDSResponse or None: 响应
        """
        if access_mode % 2 == 1:
            # 请求种子
            request = UDSRequest(
                service_id=UDSServiceID.SECURITY_ACCESS,
                subfunction=access_mode,
                timeout=2000
            )
            
            response = self.send_request(request)
            if response and response.is_positive:
                self.security_seed = response.data
                logger.info(f"Security seed received: {self.security_seed.hex().upper()}")
            
            return response
        else:
            # 发送密钥
            if not security_key:
                logger.error("Security key required for even access modes")
                return None
            
            request = UDSRequest(
                service_id=UDSServiceID.SECURITY_ACCESS,
                subfunction=access_mode,
                data=security_key,
                timeout=2000
            )
            
            response = self.send_request(request)
            if response and response.is_positive:
                self.security_level = access_mode // 2
                logger.info(f"Security access granted, level: {self.security_level}")
            
            return response
    
    def communication_control(self, control_type: CommunicationControlType, communication_type: int) -> Optional[UDSResponse]:
        """
        通信控制 (0x28)
        
        Args:
            control_type: 控制类型
            communication_type: 通信类型
            
        Returns:
            UDSResponse or None: 响应
        """
        data = bytes([control_type, communication_type])
        
        request = UDSRequest(
            service_id=UDSServiceID.COMMUNICATION_CONTROL,
            subfunction=control_type,
            data=data,
            timeout=2000
        )
        
        return self.send_request(request)
    
    def tester_present(self, suppress_response: bool = False) -> Optional[UDSResponse]:
        """
        测试器保持连接 (0x3E)
        
        Args:
            suppress_response: 是否抑制响应
            
        Returns:
            UDSResponse or None: 响应
        """
        subfunction = 0x80 if suppress_response else 0x00
        
        request = UDSRequest(
            service_id=UDSServiceID.TESTER_PRESENT,
            subfunction=subfunction,
            timeout=2000,
            expect_response=not suppress_response
        )
        
        return self.send_request(request)
    
    def write_data_by_identifier(self, data_identifier: int, data_record: bytes) -> Optional[UDSResponse]:
        """
        通过标识符写入数据 (0x2E)
        
        Args:
            data_identifier: 数据标识符
            data_record: 数据记录
            
        Returns:
            UDSResponse or None: 响应
        """
        data = data_identifier.to_bytes(2, 'big') + data_record
        
        request = UDSRequest(
            service_id=UDSServiceID.WRITE_DATA_BY_IDENTIFIER,
            data=data,
            timeout=5000
        )
        
        return self.send_request(request)
    
    def routine_control(self, control_type: RoutineControlType, routine_identifier: int, routine_data: bytes = b'') -> Optional[UDSResponse]:
        """
        例程控制 (0x31)
        
        Args:
            control_type: 控制类型
            routine_identifier: 例程标识符
            routine_data: 例程数据
            
        Returns:
            UDSResponse or None: 响应
        """
        data = routine_identifier.to_bytes(2, 'big') + routine_data
        
        request = UDSRequest(
            service_id=UDSServiceID.ROUTINE_CONTROL,
            subfunction=control_type,
            data=data,
            timeout=10000  # 例程可能需要更长时间
        )
        
        return self.send_request(request)
    
    def request_download(self, memory_address: int, memory_size: int, data_format: int = 0x00) -> Optional[UDSResponse]:
        """
        请求下载 (0x34)
        
        Args:
            memory_address: 内存地址
            memory_size: 内存大小
            data_format: 数据格式标识符
            
        Returns:
            UDSResponse or None: 响应
        """
        # 地址和长度格式
        address_and_length_format = 0x44  # 4字节地址，4字节长度
        
        data = bytes([data_format, address_and_length_format])
        data += memory_address.to_bytes(4, 'big')
        data += memory_size.to_bytes(4, 'big')
        
        request = UDSRequest(
            service_id=UDSServiceID.REQUEST_DOWNLOAD,
            data=data,
            timeout=5000
        )
        
        return self.send_request(request)
    
    def request_upload(self, memory_address: int, memory_size: int, data_format: int = 0x00) -> Optional[UDSResponse]:
        """
        请求上传 (0x35)
        
        Args:
            memory_address: 内存地址
            memory_size: 内存大小
            data_format: 数据格式标识符
            
        Returns:
            UDSResponse or None: 响应
        """
        # 地址和长度格式
        address_and_length_format = 0x44  # 4字节地址，4字节长度
        
        data = bytes([data_format, address_and_length_format])
        data += memory_address.to_bytes(4, 'big')
        data += memory_size.to_bytes(4, 'big')
        
        request = UDSRequest(
            service_id=UDSServiceID.REQUEST_UPLOAD,
            data=data,
            timeout=5000
        )
        
        return self.send_request(request)
    
    def transfer_data(self, block_sequence_counter: int, transfer_data: bytes) -> Optional[UDSResponse]:
        """
        传输数据 (0x36)
        
        Args:
            block_sequence_counter: 块序列计数器
            transfer_data: 传输数据
            
        Returns:
            UDSResponse or None: 响应
        """
        data = bytes([block_sequence_counter]) + transfer_data
        
        request = UDSRequest(
            service_id=UDSServiceID.TRANSFER_DATA,
            data=data,
            timeout=5000
        )
        
        return self.send_request(request)
    
    def request_transfer_exit(self) -> Optional[UDSResponse]:
        """
        请求传输退出 (0x37)
        
        Returns:
            UDSResponse or None: 响应
        """
        request = UDSRequest(
            service_id=UDSServiceID.REQUEST_TRANSFER_EXIT,
            timeout=5000
        )
        
        return self.send_request(request)
    
    def control_dtc_setting(self, setting_type: ControlDTCSettingType) -> Optional[UDSResponse]:
        """
        控制DTC设置 (0x85)
        
        Args:
            setting_type: 设置类型
            
        Returns:
            UDSResponse or None: 响应
        """
        request = UDSRequest(
            service_id=UDSServiceID.CONTROL_DTC_SETTING,
            subfunction=setting_type,
            timeout=2000
        )
        
        return self.send_request(request)
    
    def response_on_event(self, event_type: int, **kwargs) -> Optional[UDSResponse]:
        """
        事件响应 (0x86)
        
        Args:
            event_type: 事件类型
            **kwargs: 额外参数
            
        Returns:
            UDSResponse or None: 响应
        """
        data = bytes([event_type])
        
        # 根据事件类型添加额外参数
        if 'window_time' in kwargs:
            data += kwargs['window_time'].to_bytes(2, 'big')
        
        request = UDSRequest(
            service_id=UDSServiceID.RESPONSE_ON_EVENT,
            subfunction=event_type,
            data=data,
            timeout=5000
        )
        
        return self.send_request(request)
    
    def link_control(self, control_type: LinkControlType, baudrate: int = 0) -> Optional[UDSResponse]:
        """
        链接控制 (0x87)
        
        Args:
            control_type: 控制类型
            baudrate: 波特率
            
        Returns:
            UDSResponse or None: 响应
        """
        data = bytes([control_type])
        
        if control_type == LinkControlType.VERIFY_BAUDRATE_TRANSITION_WITH_SPECIFIC_BAUDRATE:
            data += baudrate.to_bytes(4, 'big')
        
        request = UDSRequest(
            service_id=UDSServiceID.LINK_CONTROL,
            subfunction=control_type,
            data=data,
            timeout=5000
        )
        
        return self.send_request(request)
    
    # ========== 高级功能 ==========
    
    def keep_alive(self, interval: int = 2000) -> None:
        """
        保持连接活跃（周期性发送TesterPresent）
        
        Args:
            interval: 发送间隔（毫秒）
        """
        def keep_alive_thread():
            while getattr(self, '_keep_alive_running', False):
                try:
                    self.tester_present(suppress_response=True)
                    time.sleep(interval / 1000.0)
                except Exception as e:
                    logger.error(f"Error in keep-alive thread: {e}")
                    time.sleep(1.0)
        
        # 启动保持连接线程
        self._keep_alive_running = True
        self._keep_alive_thread = threading.Thread(
            target=keep_alive_thread,
            daemon=True,
            name="UDKeepAlive"
        )
        self._keep_alive_thread.start()
        
        logger.info(f"Keep-alive started with interval {interval}ms")
    
    def stop_keep_alive(self) -> None:
        """停止保持连接"""
        self._keep_alive_running = False
        if self._keep_alive_thread and self._keep_alive_thread.is_alive():
            self._keep_alive_thread.join(timeout=1.0)
        
        logger.info("Keep-alive stopped")
    
    def read_ecu_identification(self) -> Optional[Dict[str, Any]]:
        """
        读取ECU识别信息
        
        Returns:
            dict or None: ECU识别信息
        """
        ecu_info = {}
        
        # 读取常见的数据标识符
        data_identifiers = [
            0xF180,  # ECU Identification
            0xF181,  # VIN
            0xF187,  # ECU Hardware Number
            0xF188,  # ECU Software Number
            0xF18A,  # ECU Serial Number
            0xF18B,  # System Name
        ]
        
        for did in data_identifiers:
            response = self.read_data_by_identifier(did)
            if response and response.is_positive and response.data:
                try:
                    # 尝试解码为ASCII字符串
                    value = response.data.decode('ascii', errors='ignore').strip()
                    ecu_info[f"0x{did:04X}"] = value
                    logger.debug(f"DID 0x{did:04X}: {value}")
                except Exception as e:
                    logger.warning(f"Failed to decode DID 0x{did:04X}: {e}")
                    ecu_info[f"0x{did:04X}"] = response.data.hex().upper()
        
        return ecu_info if ecu_info else None
    
    def get_session_info(self) -> UDSSessionInfo:
        """获取会话信息"""
        return self.session_info
    
    def get_protocol_definitions(self) -> ProtocolDefinitions:
        """获取协议定义"""
        return self.protocol_defs
    
    def create_custom_request(self, service_id: int, data: bytes = b'', subfunction: Optional[int] = None) -> Optional[UDSResponse]:
        """
        创建自定义请求
        
        Args:
            service_id: 服务ID
            data: 数据
            subfunction: 子功能
            
        Returns:
            UDSResponse or None: 响应
        """
        request = UDSRequest(
            service_id=service_id,
            data=data,
            subfunction=subfunction,
            timeout=2000
        )
        
        return self.send_request(request)
    
    def close(self) -> None:
        """关闭UDS会话管理器"""
        self.stop_keep_alive()
        self.stop_response_thread()
        
        # 清理回调
        self.response_callbacks.clear()
        
        # 清空队列
        while not self.response_queue.empty():
            try:
                self.response_queue.get_nowait()
            except queue.Empty:
                break
        
        logger.info("UDS session manager closed")

class UDSManager:
    """UDS管理器（多会话管理）"""
    
    def __init__(self, isotp_manager: ISOTPManager):
        """
        初始化UDS管理器
        
        Args:
            isotp_manager: ISO-TP管理器
        """
        self.isotp_manager = isotp_manager
        self.sessions: Dict[str, UDSSessionManager] = {}
        self.lock = threading.RLock()
        
        logger.info("UDS manager initialized")
    
    def create_session(self, session_id: str, isotp_config: ISOTPConfig) -> Optional[UDSSessionManager]:
        """
        创建UDS会话
        
        Args:
            session_id: 会话ID
            isotp_config: ISO-TP配置
            
        Returns:
            UDSSessionManager or None: UDS会话管理器
        """
        with self.lock:
            if session_id in self.sessions:
                logger.warning(f"Session '{session_id}' already exists")
                return self.sessions[session_id]
            
            try:
                # 创建ISO-TP协议
                isotp_protocol = self.isotp_manager.create_protocol(session_id, isotp_config)
                if not isotp_protocol:
                    logger.error(f"Failed to create ISO-TP protocol for session '{session_id}'")
                    return None
                
                # 创建UDS会话管理器
                session_manager = UDSSessionManager(self.isotp_manager, session_id)
                self.sessions[session_id] = session_manager
                
                logger.info(f"Created UDS session '{session_id}'")
                return session_manager
                
            except Exception as e:
                logger.error(f"Error creating UDS session '{session_id}': {e}")
                return None
    
    def get_session(self, session_id: str) -> Optional[UDSSessionManager]:
        """
        获取UDS会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            UDSSessionManager or None: UDS会话管理器
        """
        with self.lock:
            return self.sessions.get(session_id)
    
    def remove_session(self, session_id: str) -> bool:
        """
        移除UDS会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 是否成功移除
        """
        with self.lock:
            if session_id not in self.sessions:
                return False
            
            session = self.sessions[session_id]
            session.close()
            del self.sessions[session_id]
            
            # 移除ISO-TP协议
            self.isotp_manager.remove_protocol(session_id)
            
            logger.info(f"Removed UDS session '{session_id}'")
            return True
    
    def get_all_sessions(self) -> Dict[str, UDSSessionManager]:
        """获取所有会话"""
        with self.lock:
            return self.sessions.copy()
    
    def close_all_sessions(self) -> None:
        """关闭所有会话"""
        with self.lock:
            for session_id in list(self.sessions.keys()):
                self.remove_session(session_id)
            
            logger.info("All UDS sessions closed")