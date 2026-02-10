#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UDS协议定义 - 完整的UDS服务定义和子功能
基于ISO 14229-1:2020标准
"""

from enum import IntEnum, Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple

class UDSServiceID(IntEnum):
    """UDS服务ID枚举"""
    # 诊断和通信管理功能单元
    DIAGNOSTIC_SESSION_CONTROL = 0x10
    ECU_RESET = 0x11
    CLEAR_DIAGNOSTIC_INFORMATION = 0x14
    READ_DTC_INFORMATION = 0x19
    READ_DATA_BY_IDENTIFIER = 0x22
    READ_MEMORY_BY_ADDRESS = 0x23
    READ_SCALING_DATA_BY_IDENTIFIER = 0x24
    READ_DATA_BY_PERIODIC_IDENTIFIER = 0x2A
    DYNAMICALLY_DEFINE_DATA_IDENTIFIER = 0x2C
    WRITE_DATA_BY_IDENTIFIER = 0x2E
    WRITE_MEMORY_BY_ADDRESS = 0x3D
    TESTER_PRESENT = 0x3E
    ACCESS_TIMING_PARAMETER = 0x83
    SECURED_DATA_TRANSMISSION = 0x84
    CONTROL_DTC_SETTING = 0x85
    RESPONSE_ON_EVENT = 0x86
    LINK_CONTROL = 0x87
    
    # 数据传输功能单元
    REQUEST_DOWNLOAD = 0x34
    REQUEST_UPLOAD = 0x35
    TRANSFER_DATA = 0x36
    REQUEST_TRANSFER_EXIT = 0x37
    REQUEST_FILE_TRANSFER = 0x38
    
    # 输入输出控制功能单元
    ROUTINE_CONTROL = 0x31
    
    # 远程激活例程
    START_ROUTINE_BY_LOCAL_IDENTIFIER = 0x32
    STOP_ROUTINE_BY_LOCAL_IDENTIFIER = 0x33
    
    # 通信控制
    COMMUNICATION_CONTROL = 0x28
    
    # 安全访问
    SECURITY_ACCESS = 0x27

class DiagnosticSessionType(IntEnum):
    """诊断会话类型"""
    DEFAULT_SESSION = 0x01
    PROGRAMMING_SESSION = 0x02
    EXTENDED_DIAGNOSTIC_SESSION = 0x03
    SAFETY_SYSTEM_DIAGNOSTIC_SESSION = 0x04
    # ISO 14229-1:2020新增
    MANUFACTURER_SPECIFIC_1 = 0x40
    MANUFACTURER_SPECIFIC_2 = 0x41
    MANUFACTURER_SPECIFIC_3 = 0x42
    MANUFACTURER_SPECIFIC_4 = 0x43

class ResetType(IntEnum):
    """ECU复位类型"""
    HARD_RESET = 0x01
    KEY_OFF_ON_RESET = 0x02
    SOFT_RESET = 0x03
    ENABLE_RAPID_POWER_SHUTDOWN = 0x04
    DISABLE_RAPID_POWER_SHUTDOWN = 0x05

class AccessMode(IntEnum):
    """安全访问模式"""
    REQUEST_SEED = 0x01
    SEND_KEY = 0x02

class CommunicationControlType(IntEnum):
    """通信控制类型"""
    ENABLE_RX_AND_TX = 0x00
    ENABLE_RX_DISABLE_TX = 0x01
    DISABLE_RX_ENABLE_TX = 0x02
    DISABLE_RX_AND_TX = 0x03
    ENABLE_RX_DISABLE_TX_WITH_ENHANCED_ADDRESS = 0x04
    DISABLE_RX_ENABLE_TX_WITH_ENHANCED_ADDRESS = 0x05

class DTCFormat(IntEnum):
    """DTC格式"""
    ISO_15031_6 = 0x00
    ISO_14229_1 = 0x01
    SAE_J1939_73 = 0x02
    ISO_11992_4 = 0x03

class RoutineControlType(IntEnum):
    """例程控制类型"""
    START_ROUTINE = 0x01
    STOP_ROUTINE = 0x02
    REQUEST_ROUTINE_RESULTS = 0x03

class ControlDTCSettingType(IntEnum):
    """DTC设置控制类型"""
    ON = 0x01
    OFF = 0x02

class LinkControlType(IntEnum):
):
    """链接控制类型"""
    VERIFY_BAUDRATE_TRANSITION_WITH_FIXED_BAUDRATE = 0x01
    VERIFY_BAUDRATE_TRANSITION_WITH_SPECIFIC_BAUDRATE = 0x02
    TRANSITION_BAUDRATE = 0x03

@dataclass
class UDSServiceDefinition:
    """UDS服务定义"""
    service_id: int
    name: str
    description: str
    request_format: List[Tuple[str, str]]  # [(参数名, 参数类型), ...]
    response_format: List[Tuple[str, str]]
    subfunctions: Optional[Dict[int, str]] = None
    supports_fd: bool = True
    min_length: int = 1
    max_length: int = 4095
    
class ProtocolDefinitions:
    """协议定义管理器"""
    
    def __init__(self):
        self.services: Dict[int, UDSServiceDefinition] = self._initialize_services()
        self.data_identifiers: Dict[int, str] = self._initialize_data_identifiers()
        
    def _initialize_services(self) -> Dict[int, UDSServiceDefinition]:
        """初始化UDS服务定义"""
        services = {}
        
        # 1. Diagnostic Session Control (0x10)
        services[0x10] = UDSServiceDefinition(
            service_id=0x10,
            name="DiagnosticSessionControl",
            description="诊断会话控制",
            request_format=[
                ("service_id", "uint8"),
                ("subfunction", "uint8"),  # session_type
            ],
            response_format=[
                ("service_id", "uint8"),
                ("subfunction", "uint8"),
                ("p2_server_max", "uint16"),
                ("p2_star_server_max", "uint16"),
            ],
            subfunctions={
                0x01: "Default Session",
                0x02: "Programming Session",
                0x03: "Extended Diagnostic Session",
                0x04: "Safety System Diagnostic Session",
                0x40: "Manufacturer Specific 1",
                0x41: "Manufacturer Specific 2",
                0x42: "Manufacturer Specific 3",
                0x43: "Manufacturer Specific 4",
            }
        )
        
        # 2. ECU Reset (0x11)
        services[0x11] = UDSServiceDefinition(
            service_id=0x11,
            name="ECUReset",
            description="ECU复位",
            request_format=[
                ("service_id", "uint8"),
                ("subfunction", "uint8"),  # reset_type
            ],
            response_format=[
                ("service_id", "uint8"),
                ("subfunction", "uint8"),
                ("power_down_time", "uint8"),
            ],
            subfunctions={
                0x01: "Hard Reset",
                0x02: "Key Off On Reset",
                0x03: "Soft Reset",
                0x04: "Enable Rapid Power Shutdown",
                0x05: "Disable Rapid Power Shutdown",
            }
        )
        
        # 3. Clear Diagnostic Information (0x14)
        services[0x14] = UDSServiceDefinition(
            service_id=0x14,
            name="ClearDiagnosticInformation",
            description="清除诊断信息",
            request_format=[
                ("service_id", "uint8"),
                ("group_of_dtc", "uint24"),
            ],
            response_format=[
                ("service_id", "uint8"),
            ]
        )
        
        # 4. Read DTC Information (0x19)
        dtc_subfunctions = {
            0x01: "reportNumberOfDTCByStatusMask",
            0x02: "reportDTCByStatusMask",
            0x03: "reportDTCSnapshotIdentification",
            0x04: "reportDTCSnapshotRecordByDTCNumber",
            0x05: "reportDTCExtendedDataRecordByDTCNumber",
            0x06: "reportNumberOfDTCBySeverityMaskRecord",
            0x07: "reportDTCBySeverityMaskRecord",
            0x08: "reportSeverityInformationOfDTC",
            0x09: "reportSupportedDTC",
            0x0A: "reportFirstTestFailedDTC",
            0x0B: "reportFirstConfirmedDTC",
            0x0C: "reportMostRecentTestFailedDTC",
            0x0D: "reportMostRecentConfirmedDTC",
            0x0E: "reportMirrorMemoryDTCByStatusMask",
            0x0F: "reportMirrorMemoryDTCExtendedDataRecordByDTCNumber",
            0x10: "reportNumberOfMirrorMemoryDTCByStatusMask",
            0x11: "reportNumberOfEmissionsRelatedOBDDTCByStatusMask",
            0x12: "reportEmissionsRelatedOBDDTCByStatusMask",
            0x13: "reportDTCFaultDetectionCounter",
            0x14: "reportDTCWithPermanentStatus",
            0x15: "reportDTCExtendedDataRecordByRecordNumber",
            0x16: "reportUserDefinedMemoryDTCByStatusMask",
            0x17: "reportUserDefinedMemoryDTCExtendedDataRecordByDTCNumber",
            0x18: "reportNumberOfUserDefinedMemoryDTCByStatusMask",
            0x19: "reportManufacturerDefinedDTCByStatusMask",
        }
        
        services[0x19] = UDSServiceDefinition(
            service_id=0x19,
            name="ReadDTCInformation",
            description="读取DTC信息",
            request_format=[
                ("service_id", "uint8"),
                ("subfunction", "uint8"),
            ],
            response_format=[
                ("service_id", "uint8"),
                ("subfunction", "uint8"),
            ],
            subfunctions=dtc_subfunctions
        )
        
        # 5. Read Data By Identifier (0x22)
        services[0x22] = UDSServiceDefinition(
            service_id=0x22,
            name="ReadDataByIdentifier",
            description="通过标识符读取数据",
            request_format=[
                ("service_id", "uint8"),
                ("data_identifier", "uint16"),
            ],
            response_format=[
                ("service_id", "uint8"),
                ("data_identifier", "uint16"),
                ("data_record", "bytes"),
            ]
        )
        
        # 6. Read Memory By Address (0x23)
        services[0x23] = UDSServiceDefinition(
            service_id=0x23,
            name="ReadMemoryByAddress",
            description="通过地址读取内存",
            request_format=[
                ("service_id", "uint8"),
                ("memory_address", "uint32"),
                ("memory_size", "uint24"),
            ],
            response_format=[
                ("service_id", "uint8"),
                ("data_record", "bytes"),
            ]
        )
        
        # 7. Read Scaling Data By Identifier (0x24)
        services[0x24] = UDSServiceDefinition(
            service_id=0x24,
            name="ReadScalingDataByIdentifier",
            description="通过标识符读取缩放数据",
            request_format=[
                ("service_id", "uint8"),
                ("data_identifier", "uint16"),
            ],
            response_format=[
                ("service_id", "uint8"),
                ("data_identifier", "uint16"),
                ("scaling_byte", "uint8"),
                ("data_record", "bytes"),
            ]
        )
        
        # 8. Security Access (0x27)
        services[0x27] = UDSServiceDefinition(
            service_id=0x27,
            name="SecurityAccess",
            description="安全访问",
            request_format=[
                ("service_id", "uint8"),
                ("subfunction", "uint8"),  # 奇数：请求种子，偶数：发送密钥
            ],
            response_format=[
                ("service_id", "uint8"),
                ("subfunction", "uint8"),
                ("security_seed_or_key", "bytes"),
            ],
            subfunctions={
                0x01: "Request Seed",
                0x02: "Send Key",
                0x03: "Request Seed (level 2)",
                0x04: "Send Key (level 2)",
                0x05: "Request Seed (level 3)",
                0x06: "Send Key (level 3)",
                0x07: "Request Seed (level 4)",
                0x08: "Send Key (level 4)",
                0x09: "Request Seed (level 5)",
                0x0A: "Send Key (level 5)",
            }
        )
        
        # 9. Communication Control (0x28)
        services[0x28] = UDSServiceDefinition(
            service_id=0x28,
            name="CommunicationControl",
            description="通信控制",
            request_format=[
                ("service_id", "uint8"),
                ("subfunction", "uint8"),  # control_type
                ("communication_type", "uint8"),
            ],
            response_format=[
                ("service_id", "uint8"),
                ("subfunction", "uint8"),
            ],
            subfunctions={
                0x00: "Enable Rx and Tx",
                0x01: "Enable Rx Disable Tx",
                0x02: "Disable Rx Enable Tx",
                0x03: "Disable Rx and Tx",
                0x04: "Enable Rx Disable Tx with Enhanced Address",
                0x05: "Disable Rx Enable Tx with Enhanced Address",
            }
        )
        
        # 10. Tester Present (0x3E)
        services[0x3E] = UDSServiceDefinition(
            service_id=0x3E,
            name="TesterPresent",
            description="测试器保持连接",
            request_format=[
                ("service_id", "uint8"),
                ("subfunction", "uint8"),
            ],
            response_format=[
                ("service_id", "uint8"),
                ("subfunction", "uint8"),
            ],
            subfunctions={
                0x00: "Zero Sub-function",
                0x80: "Suppress Positive Response",
            }
        )
        
        # 11. Write Data By Identifier (0x2E)
        services[0x2E] = UDSServiceDefinition(
            service_id=0x2E,
            name="WriteDataByIdentifier",
            description="通过标识符写入数据",
            request_format=[
                ("service_id", "uint8"),
                ("data_identifier", "uint16"),
                ("data_record", "bytes"),
            ],
            response_format=[
                ("service_id", "uint8"),
                ("data_identifier", "uint16"),
            ]
        )
        
        # 12. Routine Control (0x31)
        services[0x31] = UDSServiceDefinition(
            service_id=0x31,
            name="RoutineControl",
            description="例程控制",
            request_format=[
                ("service_id", "uint8"),
                ("subfunction", "uint8"),
                ("routine_identifier", "uint16"),
                ("routine_control_option_record", "bytes"),
            ],
            response_format=[
                ("service_id", "uint8"),
                ("subfunction", "uint8"),
                ("routine_identifier", "uint16"),
                ("routine_status_record", "bytes"),
            ],
            subfunctions={
                0x01: "Start Routine",
                0x02: "Stop Routine",
                0x03: "Request Routine Results",
            }
        )
        
        # 13. Request Download (0x34)
        services[0x34] = UDSServiceDefinition(
            service_id=0x34,
            name="RequestDownload",
            description="请求下载",
            request_format=[
                ("service_id", "uint8"),
                ("data_format_identifier", "uint8"),
                ("memory_address", "uint32"),
                ("memory_size", "uint32"),
            ],
            response_format=[
                ("service_id", "uint8"),
                ("length_format_identifier", "uint8"),
                ("max_number_of_blocks", "uint32"),
            ]
        )
        
        # 14. Request Upload (0x35)
        services[0x35] = UDSServiceDefinition(
            service_id=0x35,
            name="RequestUpload",
            description="请求上传",
            request_format=[
                ("service_id", "uint8"),
                ("data_format_identifier", "uint8"),
                ("memory_address", "uint32"),
                ("memory_size", "uint32"),
            ],
            response_format=[
                ("service_id", "uint8"),
                ("length_format_identifier", "uint8"),
                ("max_number_of_blocks", "uint32"),
            ]
        )
        
        # 15. Transfer Data (0x36)
        services[0x36] = UDSServiceDefinition(
            service_id=0x36,
            name="TransferData",
            description="传输数据",
            request_format=[
                ("service_id", "uint8"),
                ("block_sequence_counter", "uint8"),
                ("transfer_request_data_record", "bytes"),
            ],
            response_format=[
                ("service_id", "uint8"),
                ("block_sequence_counter", "uint8"),
                ("transfer_response_data_record", "bytes"),
            ]
        )
        
        # 16. Request Transfer Exit (0x37)
        services[0x37] = UDSServiceDefinition(
            service_id=0x37,
            name="RequestTransferExit",
            description="请求传输退出",
            request_format=[
                ("service_id", "uint8"),
            ],
            response_format=[
                ("service_id", "uint8"),
            ]
        )
        
        return services
    
    def _initialize_data_identifiers(self) -> Dict[int, str]:
        """初始化数据标识符定义"""
        data_ids = {}
        
        # ISO 14229-1 标准数据标识符
        data_ids.update({
            # ECU识别信息
            0xF180: "ECU Identification",
            0xF181: "VIN",
            0xF182: "Vehicle Manufacturer Name",
            0xF183: "Vehicle Make",
            0xF184: "Vehicle Model",
            0xF185: "Vehicle Model Year",
            0xF186: "Vehicle Trim Level",
            0xF187: "ECU Hardware Number",
            0xF188: "ECU Software Number",
            0xF189: "ECU Manufacturing Date",
            0xF18A: "ECU Serial Number",
            0xF18B: "System Name",
            0xF18C: "System Supplier",
            
            # 诊断信息
            0xF190: "Active Diagnostic Session",
            0xF191: "Boot Software Identification",
            0xF192: "Application Software Identification",
            0xF193: "Application Data Identification",
            0xF194: "Bootloader Software Identification",
            0xF195: "Calibration Identification",
            0xF196: "Calibration Verification Numbers",
            0xF197: "ECU Diagnostic Address",
            0xF198: "ECU Name",
            0xF199: "Programming Date",
            
            # 网络管理
            0xF1A0: "CAN Network Configuration",
            0xF1A1: "LIN Network Configuration",
            0xF1A2: "FlexRay Network Configuration",
            0xF1A3: "Ethernet Network Configuration",
            
            # 安全信息
            0xF1B0: "Security Access Configuration",
            0xF1B1: "Security Certificate",
            0xF1B2: "Security Key",
            
            # 制造商特定范围
            0xF200: "Manufacturer Specific 1",
            0xF201: "Manufacturer Specific 2",
            0xF202: "Manufacturer Specific 3",
            0xF203: "Manufacturer Specific 4",
            0xF204: "Manufacturer Specific 5",
            0xF205: "Manufacturer Specific 6",
        })
        
        return data_ids
    
    def get_service_definition(self, service_id: int) -> Optional[UDSServiceDefinition]:
        """获取服务定义"""
        return self.services.get(service_id)
    
    def get_all_services(self) -> List[UDSServiceDefinition]:
        """获取所有服务定义"""
        return list(self.services.values())
    
    def get_data_identifier_name(self, data_id: int) -> str:
        """获取数据标识符名称"""
        return self.data_identifiers.get(data_id, f"Unknown (0x{data_id:04X})")
    
    def add_custom_service(self, service_def: UDSServiceDefinition) -> bool:
        """添加自定义服务"""
        if service_def.service_id in self.services:
            return False
        
        self.services[service_def.service_id] = service_def
        return True
    
    def add_custom_data_identifier(self, data_id: int, name: str) -> bool:
        """添加自定义数据标识符"""
        if data_id in self.data_identifiers:
            return False
        
        self.data_identifiers[data_id] = name
        return True