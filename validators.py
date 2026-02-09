#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证器 - 数据验证和校验函数
"""

import re
import struct
import ipaddress
from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum

from .constants import *

logger = __import__('logging').getLogger(__name__)

class ValidationError(Exception):
    """验证错误异常"""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(self.message)

class Validator:
    """验证器基类"""
    
    def __init__(self, required: bool = True):
        self.required = required
        self.error_message = ""
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        """
        验证值
        
        Args:
            value: 要验证的值
            
        Returns:
            tuple: (是否有效, 错误消息)
        """
        if self.required and value is None:
            return False, "字段为必填项"
        
        return True, ""
    
    def __call__(self, value: Any) -> Tuple[bool, str]:
        return self.validate(value)

class StringValidator(Validator):
    """字符串验证器"""
    
    def __init__(self, min_length: int = 0, max_length: int = None, 
                 pattern: str = None, **kwargs):
        super().__init__(**kwargs)
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = pattern
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        # 调用父类验证
        valid, error = super().validate(value)
        if not valid:
            return False, error
        
        # 检查是否为字符串
        if value is not None and not isinstance(value, str):
            return False, "必须为字符串类型"
        
        # 检查长度
        if value is not None:
            if len(value) < self.min_length:
                return False, f"长度不能少于 {self.min_length} 个字符"
            
            if self.max_length is not None and len(value) > self.max_length:
                return False, f"长度不能超过 {self.max_length} 个字符"
            
            # 检查正则表达式
            if self.pattern and not re.match(self.pattern, value):
                return False, f"格式无效，必须匹配模式: {self.pattern}"
        
        return True, ""

class IntegerValidator(Validator):
    """整数验证器"""
    
    def __init__(self, min_value: int = None, max_value: int = None, **kwargs):
        super().__init__(**kwargs)
        self.min_value = min_value
        self.max_value = max_value
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        # 调用父类验证
        valid, error = super().validate(value)
        if not valid:
            return False, error
        
        # 检查是否为整数
        if value is not None:
            try:
                int_value = int(value)
            except (ValueError, TypeError):
                return False, "必须为整数类型"
            
            # 检查范围
            if self.min_value is not None and int_value < self.min_value:
                return False, f"不能小于 {self.min_value}"
            
            if self.max_value is not None and int_value > self.max_value:
                return False, f"不能大于 {self.max_value}"
        
        return True, ""

class FloatValidator(Validator):
    """浮点数验证器"""
    
    def __init__(self, min_value: float = None, max_value: float = None, 
                 precision: int = None, **kwargs):
        super().__init__(**kwargs)
        self.min_value = min_value
        self.max_value = max_value
        self.precision = precision
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        # 调用父类验证
        valid, error = super().validate(value)
        if not valid:
            return False, error
        
        # 检查是否为浮点数
        if value is not None:
            try:
                float_value = float(value)
            except (ValueError, TypeError):
                return False, "必须为数字类型"
            
            # 检查范围
            if self.min_value is not None and float_value < self.min_value:
                return False, f"不能小于 {self.min_value}"
            
            if self.max_value is not None and float_value > self.max_value:
                return False, f"不能大于 {self.max_value}"
            
            # 检查精度
            if self.precision is not None:
                str_value = str(value)
                if '.' in str_value:
                    decimal_places = len(str_value.split('.')[1])
                    if decimal_places > self.precision:
                        return False, f"精度不能超过 {self.precision} 位小数"
        
        return True, ""

class HexValidator(Validator):
    """十六进制验证器"""
    
    def __init__(self, min_length: int = 0, max_length: int = None, 
                 byte_aligned: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.min_length = min_length
        self.max_length = max_length
        self.byte_aligned = byte_aligned
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        # 调用父类验证
        valid, error = super().validate(value)
        if not valid:
            return False, error
        
        if value is None:
            return True, ""
        
        # 转换为字符串
        str_value = str(value).strip()
        
        # 移除空格和0x前缀
        str_value = str_value.replace(' ', '').replace('0x', '').replace('0X', '')
        
        if not str_value:
            if self.required:
                return False, "不能为空"
            return True, ""
        
        # 检查是否为有效的十六进制字符串
        if not re.match(r'^[0-9A-Fa-f]+$', str_value):
            return False, "必须为有效的十六进制字符串"
        
        # 检查长度
        if len(str_value) < self.min_length:
            return False, f"长度不能少于 {self.min_length} 个字符"
        
        if self.max_length is not None and len(str_value) > self.max_length:
            return False, f"长度不能超过 {self.max_length} 个字符"
        
        # 检查字节对齐
        if self.byte_aligned and len(str_value) % 2 != 0:
            return False, "必须为字节对齐 (长度必须为偶数)"
        
        return True, ""

class CANIdValidator(Validator):
    """CAN ID验证器"""
    
    def __init__(self, extended: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.extended = extended
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        # 调用父类验证
        valid, error = super().validate(value)
        if not valid:
            return False, error
        
        if value is None:
            return True, ""
        
        # 尝试解析CAN ID
        try:
            if isinstance(value, str):
                # 移除空格和0x前缀
                can_id_str = value.strip().replace(' ', '').replace('0x', '').replace('0X', '')
                
                if not can_id_str:
                    if self.required:
                        return False, "不能为空"
                    return True, ""
                
                can_id_int = int(can_id_str, 16)
            else:
                can_id_int = int(value)
            
            # 检查范围
            if self.extended:
                if not (0 <= can_id_int <= 0x1FFFFFFF):
                    return False, f"扩展CAN ID必须在 0x00000000 到 0x1FFFFFFF 之间"
            else:
                if not (0 <= can_id_int <= 0x7FF):
                    return False, f"标准CAN ID必须在 0x000 到 0x7FF 之间"
            
            return True, ""
            
        except ValueError:
            return False, "无效的CAN ID格式"
        except Exception as e:
            return False, f"验证失败: {e}"

class IPAddressValidator(Validator):
    """IP地址验证器"""
    
    def __init__(self, version: int = 4, **kwargs):
        super().__init__(**kwargs)
        self.version = version  # 4 for IPv4, 6 for IPv6
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        # 调用父类验证
        valid, error = super().validate(value)
        if not valid:
            return False, error
        
        if value is None:
            return True, ""
        
        try:
            ip = ipaddress.ip_address(str(value))
            
            if self.version == 4 and ip.version != 4:
                return False, "必须为IPv4地址"
            
            if self.version == 6 and ip.version != 6:
                return False, "必须为IPv6地址"
            
            return True, ""
            
        except ValueError:
            return False, "无效的IP地址格式"

class MACAddressValidator(Validator):
    """MAC地址验证器"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        # 调用父类验证
        valid, error = super().validate(value)
        if not valid:
            return False, error
        
        if value is None:
            return True, ""
        
        mac_patterns = [
            r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$',
            r'^([0-9A-Fa-f]{4}\.){2}([0-9A-Fa-f]{4})$',
            r'^[0-9A-Fa-f]{12}$'
        ]
        
        for pattern in mac_patterns:
            if re.match(pattern, str(value)):
                return True, ""
        
        return False, "无效的MAC地址格式"

class PortValidator(Validator):
    """端口验证器"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        # 调用父类验证
        valid, error = super().validate(value)
        if not valid:
            return False, error
        
        if value is None:
            return True, ""
        
        try:
            port = int(value)
            
            if not (0 <= port <= 65535):
                return False, "端口必须在 0 到 65535 之间"
            
            # 避免使用保留端口
            if port < 1024:
                logger.warning(f"使用保留端口: {port}")
            
            return True, ""
            
        except ValueError:
            return False, "必须为有效的端口号"

class EnumValidator(Validator):
    """枚举验证器"""
    
    def __init__(self, enum_class: Enum, **kwargs):
        super().__init__(**kwargs)
        self.enum_class = enum_class
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        # 调用父类验证
        valid, error = super().validate(value)
        if not valid:
            return False, error
        
        if value is None:
            return True, ""
        
        try:
            # 尝试转换为枚举值
            if isinstance(value, self.enum_class):
                return True, ""
            
            # 尝试从值创建枚举
            if isinstance(value, (int, str)):
                if isinstance(value, str):
                    # 尝试按名称匹配
                    if value in self.enum_class.__members__:
                        return True, ""
                    
                    # 尝试按值匹配（如果是数字字符串）
                    try:
                        int_value = int(value)
                        self.enum_class(int_value)
                        return True, ""
                    except ValueError:
                        pass
                else:
                    # 整数直接检查
                    self.enum_class(value)
                    return True, ""
            
            return False, f"无效的值，必须为 {self.enum_class.__name__} 枚举值"
            
        except ValueError:
            return False, f"无效的值，必须为 {self.enum_class.__name__} 枚举值"

class RangeValidator(Validator):
    """范围验证器"""
    
    def __init__(self, min_value: Any = None, max_value: Any = None, 
                 inclusive: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.min_value = min_value
        self.max_value = max_value
        self.inclusive = inclusive
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        # 调用父类验证
        valid, error = super().validate(value)
        if not valid:
            return False, error
        
        if value is None:
            return True, ""
        
        try:
            # 尝试转换为可比较的值
            value_num = float(value) if '.' in str(value) else int(value)
            
            # 检查最小值
            if self.min_value is not None:
                min_num = float(self.min_value) if '.' in str(self.min_value) else int(self.min_value)
                
                if self.inclusive:
                    if value_num < min_num:
                        return False, f"不能小于 {self.min_value}"
                else:
                    if value_num <= min_num:
                        return False, f"必须大于 {self.min_value}"
            
            # 检查最大值
            if self.max_value is not None:
                max_num = float(self.max_value) if '.' in str(self.max_value) else int(self.max_value)
                
                if self.inclusive:
                    if value_num > max_num:
                        return False, f"不能大于 {self.max_value}"
                else:
                    if value_num >= max_num:
                        return False, f"必须小于 {self.max_value}"
            
            return True, ""
            
        except ValueError:
            return False, "必须为数字类型"

class ListValidator(Validator):
    """列表验证器"""
    
    def __init__(self, item_validator: Validator = None, min_items: int = 0, 
                 max_items: int = None, unique: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.item_validator = item_validator
        self.min_items = min_items
        self.max_items = max_items
        self.unique = unique
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        # 调用父类验证
        valid, error = super().validate(value)
        if not valid:
            return False, error
        
        if value is None:
            return True, ""
        
        # 检查是否为列表
        if not isinstance(value, (list, tuple)):
            return False, "必须为列表或元组"
        
        # 检查列表长度
        if len(value) < self.min_items:
            return False, f"不能少于 {self.min_items} 个元素"
        
        if self.max_items is not None and len(value) > self.max_items:
            return False, f"不能超过 {self.max_items} 个元素"
        
        # 检查唯一性
        if self.unique:
            if len(value) != len(set(value)):
                return False, "元素必须唯一"
        
        # 验证每个元素
        if self.item_validator:
            for i, item in enumerate(value):
                valid, error = self.item_validator.validate(item)
                if not valid:
                    return False, f"元素 {i}: {error}"
        
        return True, ""

class DictValidator(Validator):
    """字典验证器"""
    
    def __init__(self, schema: Dict[str, Validator] = None, **kwargs):
        super().__init__(**kwargs)
        self.schema = schema or {}
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        # 调用父类验证
        valid, error = super().validate(value)
        if not valid:
            return False, error
        
        if value is None:
            return True, ""
        
        # 检查是否为字典
        if not isinstance(value, dict):
            return False, "必须为字典类型"
        
        # 验证每个字段
        for field_name, validator in self.schema.items():
            field_value = value.get(field_name)
            valid, error = validator.validate(field_value)
            if not valid:
                return False, f"字段 '{field_name}': {error}"
        
        return True, ""

class CompositeValidator(Validator):
    """复合验证器（多个验证器的组合）"""
    
    def __init__(self, validators: List[Validator], **kwargs):
        super().__init__(**kwargs)
        self.validators = validators
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        # 调用父类验证
        valid, error = super().validate(value)
        if not valid:
            return False, error
        
        # 依次应用所有验证器
        for validator in self.validators:
            valid, error = validator.validate(value)
            if not valid:
                return False, error
        
        return True, ""

# ========== 特定验证器工厂函数 ==========

def create_can_config_validator() -> DictValidator:
    """创建CAN配置验证器"""
    return DictValidator({
        'interface_type': StringValidator(required=True),
        'channel': StringValidator(required=True),
        'bitrate': IntegerValidator(min_value=10000, max_value=1000000, required=True),
        'data_bitrate': IntegerValidator(min_value=10000, max_value=10000000, required=False),
        'fd_enabled': Validator(required=False),
        'frame_type': EnumValidator(
            enum_class=type('FrameType', (), {
                'STANDARD': FRAME_TYPE_STANDARD,
                'EXTENDED': FRAME_TYPE_EXTENDED
            }),
            required=True
        ),
    })

def create_uds_config_validator() -> DictValidator:
    """创建UDS配置验证器"""
    return DictValidator({
        'rx_id': CANIdValidator(extended=True, required=True),
        'tx_id': CANIdValidator(extended=True, required=True),
        'addressing_mode': EnumValidator(
            enum_class=type('AddressingMode', (), {
                'NORMAL': ADDRESSING_MODE_NORMAL,
                'EXTENDED': ADDRESSING_MODE_EXTENDED,
                'MIXED': ADDRESSING_MODE_MIXED
            }),
            required=True
        ),
        'frame_type': EnumValidator(
            enum_class=type('FrameType', (), {
                'STANDARD': FRAME_TYPE_STANDARD,
                'EXTENDED': FRAME_TYPE_EXTENDED
            }),
            required=True
        ),
        'st_min': IntegerValidator(min_value=0, max_value=127, required=True),
        'block_size': IntegerValidator(min_value=0, max_value=255, required=True),
        'can_fd_enabled': Validator(required=False),
        'fd_dlc': IntegerValidator(min_value=0, max_value=64, required=False),
        'p2_timeout': IntegerValidator(min_value=1, max_value=60000, required=True),
        'p2_extended': IntegerValidator(min_value=1, max_value=60000, required=True),
        'p4_timeout': IntegerValidator(min_value=1, max_value=60000, required=True),
    })

def create_project_validator() -> DictValidator:
    """创建项目验证器"""
    return DictValidator({
        'id': StringValidator(min_length=1, max_length=100, required=True),
        'name': StringValidator(min_length=1, max_length=200, required=True),
        'description': StringValidator(max_length=1000, required=False),
        'version': StringValidator(max_length=20, required=False),
        'groups': ListValidator(
            item_validator=DictValidator({
                'id': StringValidator(min_length=1, max_length=100, required=True),
                'name': StringValidator(min_length=1, max_length=200, required=True),
                'enabled': Validator(required=False),
                'commands': ListValidator(
                    item_validator=DictValidator({
                        'id': StringValidator(min_length=1, max_length=100, required=True),
                        'name': StringValidator(min_length=1, max_length=200, required=True),
                        'command_type': StringValidator(required=True),
                        'send_mode': StringValidator(required=True),
                        'period': IntegerValidator(min_value=1, max_value=60000, required=False),
                        'enabled': Validator(required=False),
                    }),
                    required=False
                ),
            }),
            required=False
        ),
    })

# ========== 验证函数 ==========

def validate_can_frame_data(data: Any) -> Tuple[bool, Optional[bytes], str]:
    """
    验证CAN帧数据
    
    Args:
        data: 要验证的数据
        
    Returns:
        tuple: (是否有效, 解析后的数据, 错误消息)
    """
    if data is None or data == "":
        return True, b'', ""
    
    # 如果已经是bytes或bytearray，直接返回
    if isinstance(data, (bytes, bytearray)):
        if len(data) <= 64:  # CAN FD最大长度
            return True, bytes(data), ""
        else:
            return False, None, f"数据长度不能超过64字节，当前为{len(data)}字节"
    
    # 如果是字符串，尝试解析为十六进制
    if isinstance(data, str):
        # 移除空格和前缀
        hex_str = data.strip().replace(' ', '').replace('0x', '').replace('0X', '')
        
        if not hex_str:
            return True, b'', ""
        
        # 检查是否为有效的十六进制字符串
        if not re.match(r'^[0-9A-Fa-f]+$', hex_str):
            return False, None, "无效的十六进制数据格式"
        
        # 检查长度是否为偶数
        if len(hex_str) % 2 != 0:
            return False, None, "十六进制数据长度必须为偶数"
        
        try:
            data_bytes = bytes.fromhex(hex_str)
            if len(data_bytes) <= 64:
                return True, data_bytes, ""
            else:
                return False, None, f"数据长度不能超过64字节，当前为{len(data_bytes)}字节"
        except ValueError as e:
            return False, None, f"解析十六进制数据失败: {e}"
    
    # 如果是整数列表
    if isinstance(data, list):
        try:
            # 验证每个元素是否为有效的字节值
            for i, item in enumerate(data):
                if not isinstance(item, int):
                    return False, None, f"元素{i}必须为整数，实际为{type(item)}"
                if not 0 <= item <= 255:
                    return False, None, f"元素{i}的值必须在0-255之间，实际为{item}"
            
            data_bytes = bytes(data)
            if len(data_bytes) <= 64:
                return True, data_bytes, ""
            else:
                return False, None, f"数据长度不能超过64字节，当前为{len(data_bytes)}字节"
        except Exception as e:
            return False, None, f"转换列表为字节数据失败: {e}"
    
    return False, None, "不支持的数据格式"

def validate_can_id(can_id: Any, extended: bool = False) -> Tuple[bool, Optional[int], str]:
    """
    验证CAN ID
    
    Args:
        can_id: 要验证的CAN ID
        extended: 是否为扩展ID
        
    Returns:
        tuple: (是否有效, 解析后的ID, 错误消息)
    """
    if can_id is None or can_id == "":
        return False, None, "CAN ID不能为空"
    
    try:
        if isinstance(can_id, (int, float)):
            can_id_int = int(can_id)
        elif isinstance(can_id, str):
            # 移除空格和前缀
            can_id_str = can_id.strip().replace(' ', '').replace('0x', '').replace('0X', '')
            
            if not can_id_str:
                return False, None, "CAN ID不能为空"
            
            can_id_int = int(can_id_str, 16)
        else:
            return False, None, f"不支持的CAN ID类型: {type(can_id)}"
        
        # 检查范围
        if extended:
            if 0 <= can_id_int <= 0x1FFFFFFF:
                return True, can_id_int, ""
            else:
                return False, None, f"扩展CAN ID必须在0x00000000到0x1FFFFFFF之间"
        else:
            if 0 <= can_id_int <= 0x7FF:
                return True, can_id_int, ""
            else:
                return False, None, f"标准CAN ID必须在0x000到0x7FF之间"
                
    except ValueError:
        return False, None, "无效的CAN ID格式"
    except Exception as e:
        return False, None, f"验证CAN ID失败: {e}"

def validate_dlc(dlc: Any, can_fd: bool = False) -> Tuple[bool, Optional[int], str]:
    """
    验证DLC值
    
    Args:
        dlc: 要验证的DLC值
        can_fd: 是否为CAN FD
        
    Returns:
        tuple: (是否有效, 解析后的DLC, 错误消息)
    """
    if dlc is None:
        return False, None, "DLC不能为空"
    
    try:
        if isinstance(dlc, (int, float)):
            dlc_int = int(dlc)
        elif isinstance(dlc, str):
            dlc_str = dlc.strip()
            if not dlc_str:
                return False, None, "DLC不能为空"
            dlc_int = int(dlc_str)
        else:
            return False, None, f"不支持的DLC类型: {type(dlc)}"
        
        # 检查范围
        if can_fd:
            if 0 <= dlc_int <= 15:
                return True, dlc_int, ""
            else:
                return False, None, "CAN FD DLC必须在0-15之间"
        else:
            if 0 <= dlc_int <= 8:
                return True, dlc_int, ""
            else:
                return False, None, "标准CAN DLC必须在0-8之间"
                
    except ValueError:
        return False, None, "无效的DLC格式"
    except Exception as e:
        return False, None, f"验证DLC失败: {e}"

def validate_uds_service_id(service_id: Any) -> Tuple[bool, Optional[int], str]:
    """
    验证UDS服务ID
    
    Args:
        service_id: 要验证的服务ID
        
    Returns:
        tuple: (是否有效, 解析后的ID, 错误消息)
    """
    if service_id is None or service_id == "":
        return False, None, "服务ID不能为空"
    
    try:
        if isinstance(service_id, (int, float)):
            sid_int = int(service_id)
        elif isinstance(service_id, str):
            # 移除空格和前缀
            sid_str = service_id.strip().replace(' ', '').replace('0x', '').replace('0X', '')
            
            if not sid_str:
                return False, None, "服务ID不能为空"
            
            sid_int = int(sid_str, 16)
        else:
            return False, None, f"不支持的服务ID类型: {type(service_id)}"
        
        # 检查范围
        if 0x00 <= sid_int <= 0xFF:
            return True, sid_int, ""
        else:
            return False, None, f"服务ID必须在0x00到0xFF之间"
                
    except ValueError:
        return False, None, "无效的服务ID格式"
    except Exception as e:
        return False, None, f"验证服务ID失败: {e}"

def validate_uds_subfunction(subfunction: Any) -> Tuple[bool, Optional[int], str]:
    """
    验证UDS子功能
    
    Args:
        subfunction: 要验证的子功能
        
    Returns:
        tuple: (是否有效, 解析后的子功能, 错误消息)
    """
    if subfunction is None:
        return True, None, ""  # 子功能是可选的
    
    try:
        if isinstance(subfunction, (int, float)):
            subfunc_int = int(subfunction)
        elif isinstance(subfunction, str):
            # 移除空格和前缀
            subfunc_str = subfunction.strip().replace(' ', '').replace('0x', '').replace('0X', '')
            
            if not subfunc_str:
                return True, None, ""  # 空字符串表示无子功能
            
            subfunc_int = int(subfunc_str, 16)
        else:
            return False, None, f"不支持的子功能类型: {type(subfunction)}"
        
        # 检查范围
        if 0x00 <= subfunc_int <= 0xFF:
            return True, subfunc_int, ""
        else:
            return False, None, f"子功能必须在0x00到0xFF之间"
                
    except ValueError:
        return False, None, "无效的子功能格式"
    except Exception as e:
        return False, None, f"验证子功能失败: {e}"

def validate_file_path(file_path: str, check_exists: bool = True, 
                      check_writable: bool = False) -> Tuple[bool, str]:
    """
    验证文件路径
    
    Args:
        file_path: 文件路径
        check_exists: 是否检查文件存在
        check_writable: 是否检查可写
        
    Returns:
        tuple: (是否有效, 错误消息)
    """
    if not file_path or not isinstance(file_path, str):
        return False, "文件路径不能为空"
    
    # 检查路径格式
    try:
        path = Path(file_path)
        
        # 检查文件名有效性
        if not re.match(REGEX_FILENAME, path.name):
            return False, "文件名包含无效字符"
        
        # 检查文件存在
        if check_exists and not path.exists():
            return False, f"文件不存在: {file_path}"
        
        # 检查可写
        if check_writable:
            # 检查目录是否可写
            parent_dir = path.parent
            if parent_dir.exists() and not os.access(parent_dir, os.W_OK):
                return False, f"目录不可写: {parent_dir}"
            
            # 如果文件存在，检查是否可写
            if path.exists() and not os.access(path, os.W_OK):
                return False, f"文件不可写: {file_path}"
        
        return True, ""
        
    except Exception as e:
        return False, f"文件路径验证失败: {e}"

def validate_json_data(json_str: str, schema: Dict = None) -> Tuple[bool, Optional[Dict], str]:
    """
    验证JSON数据
    
    Args:
        json_str: JSON字符串
        schema: JSON Schema（可选）
        
    Returns:
        tuple: (是否有效, 解析后的数据, 错误消息)
    """
    if not json_str:
        return False, None, "JSON数据不能为空"
    
    try:
        import json
        data = json.loads(json_str)
        
        # 如果提供了schema，验证schema
        if schema:
            try:
                from jsonschema import validate
                validate(instance=data, schema=schema)
            except ImportError:
                logger.warning("jsonschema未安装，跳过schema验证")
            except Exception as e:
                return False, None, f"JSON Schema验证失败: {e}"
        
        return True, data, ""
        
    except json.JSONDecodeError as e:
        return False, None, f"无效的JSON格式: {e}"
    except Exception as e:
        return False, None, f"验证JSON数据失败: {e}"

def validate_yaml_data(yaml_str: str) -> Tuple[bool, Optional[Dict], str]:
    """
    验证YAML数据
    
    Args:
        yaml_str: YAML字符串
        
    Returns:
        tuple: (是否有效, 解析后的数据, 错误消息)
    """
    if not yaml_str:
        return False, None, "YAML数据不能为空"
    
    try:
        import yaml
        data = yaml.safe_load(yaml_str)
        
        return True, data, ""
        
    except yaml.YAMLError as e:
        return False, None, f"无效的YAML格式: {e}"
    except Exception as e:
        return False, None, f"验证YAML数据失败: {e}"

def validate_email(email: str) -> Tuple[bool, str]:
    """
    验证电子邮件地址
    
    Args:
        email: 电子邮件地址
        
    Returns:
        tuple: (是否有效, 错误消息)
    """
    if not email:
        return False, "电子邮件地址不能为空"
    
    # 简单的电子邮件验证正则表达式
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if re.match(pattern, email):
        return True, ""
    else:
        return False, "无效的电子邮件地址格式"

def validate_phone_number(phone: str) -> Tuple[bool, str]:
    """
    验证电话号码
    
    Args:
        phone: 电话号码
        
    Returns:
        tuple: (是否有效, 错误消息)
    """
    if not phone:
        return False, "电话号码不能为空"
    
    # 简单的电话号码验证（支持国际格式）
    pattern = r'^\+?[1-9]\d{1,14}$'
    
    if re.match(pattern, phone):
        return True, ""
    else:
        return False, "无效的电话号码格式"

def validate_url(url: str) -> Tuple[bool, str]:
    """
    验证URL
    
    Args:
        url: URL地址
        
    Returns:
        tuple: (是否有效, 错误消息)
    """
    if not url:
        return False, "URL不能为空"
    
    # 简单的URL验证
    pattern = r'^(https?|ftp)://[^\s/$.?#].[^\s]*$'
    
    if re.match(pattern, url, re.IGNORECASE):
        return True, ""
    else:
        return False, "无效的URL格式"

# ========== 批量验证函数 ==========

def batch_validate(data: Dict[str, Any], validators: Dict[str, Validator]) -> Tuple[bool, Dict[str, str]]:
    """
    批量验证数据
    
    Args:
        data: 要验证的数据字典
        validators: 验证器字典
        
    Returns:
        tuple: (是否全部有效, 错误消息字典)
    """
    errors = {}
    all_valid = True
    
    for field_name, validator in validators.items():
        field_value = data.get(field_name)
        valid, error = validator.validate(field_value)
        
        if not valid:
            errors[field_name] = error
            all_valid = False
    
    return all_valid, errors

def validate_form(fields: Dict[str, Dict]) -> Tuple[bool, Dict[str, str]]:
    """
    验证表单数据
    
    Args:
        fields: 字段定义字典，格式为 {field_name: {value: ..., validator: ...}}
        
    Returns:
        tuple: (是否全部有效, 错误消息字典)
    """
    errors = {}
    all_valid = True
    
    for field_name, field_info in fields.items():
        value = field_info.get('value')
        validator = field_info.get('validator')
        
        if validator:
            valid, error = validator.validate(value)
            
            if not valid:
                errors[field_name] = error
                all_valid = False
    
    return all_valid, errors