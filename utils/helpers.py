#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
辅助函数 - 各种通用辅助函数
"""

import os
import sys
import logging
import platform
import subprocess
import traceback
import inspect
import json
import yaml
import hashlib
import time
import re
import csv
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
from enum import Enum
import threading
import queue
import struct

from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog, QInputDialog, QLineEdit
from PyQt5.QtCore import Qt, QTimer, QSettings, QUrl, QSize, QByteArray
from PyQt5.QtGui import QIcon, QPixmap, QDesktopServices, QFont, QFontDatabase

from .constants import *

logger = logging.getLogger(__name__)

def setup_logging(log_file: str = None, log_level: str = LOG_LEVEL_INFO) -> logging.Logger:
    """
    设置应用程序日志
    
    Args:
        log_file: 日志文件路径
        log_level: 日志级别
        
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    # 创建日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # 清除现有处理器
    root_logger.handlers.clear()
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 创建文件处理器（如果指定了日志文件）
    if log_file:
        try:
            # 确保日志目录存在
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
            
            logger.info(f"日志文件: {log_file}")
        except Exception as e:
            logger.error(f"无法创建日志文件: {e}")
    
    logger.info(f"日志级别设置为: {log_level}")
    return root_logger

def check_environment() -> bool:
    """
    检查运行环境
    
    Returns:
        bool: 环境检查是否通过
    """
    try:
        # 检查Python版本
        python_version = sys.version_info
        logger.info(f"Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
        
        if python_version < MIN_PYTHON_VERSION:
            logger.error(f"Python版本过低，需要 {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} 或更高版本")
            return False
        
        # 检查操作系统
        system_info = platform.system()
        system_version = platform.version()
        logger.info(f"操作系统: {system_info} {system_version}")
        
        # 检查必要的库
        required_libraries = [
            'PyQt5', 'can', 'pyqtgraph', 'serial', 'numpy', 
            'yaml', 'cantools', 'psutil', 'packaging'
        ]
        
        missing_libraries = []
        for lib in required_libraries:
            try:
                __import__(lib)
                logger.debug(f"库检查: {lib} ✓")
            except ImportError:
                missing_libraries.append(lib)
                logger.warning(f"库检查: {lib} ✗")
        
        if missing_libraries:
            logger.warning(f"缺少库: {', '.join(missing_libraries)}")
            # 这里不返回False，因为有些库是可选的
        
        # 检查CAN驱动
        try:
            import can
            available_interfaces = can.detect_available_configs()
            logger.info(f"检测到CAN接口: {len(available_interfaces)} 个")
        except ImportError:
            logger.warning("python-can库未安装")
        except Exception as e:
            logger.warning(f"CAN接口检测失败: {e}")
        
        logger.info("环境检查完成")
        return True
        
    except Exception as e:
        logger.error(f"环境检查失败: {e}")
        return False

def load_stylesheet(style_file: str = None) -> str:
    """
    加载样式表
    
    Args:
        style_file: 样式表文件路径
        
    Returns:
        str: 样式表内容
    """
    default_stylesheet = """
    /* 主窗口样式 */
    QMainWindow {
        background-color: #FFFFFF;
    }
    
    /* 按钮样式 */
    QPushButton {
        background-color: #0078D7;
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 4px;
        font-weight: bold;
    }
    
    QPushButton:hover {
        background-color: #106EBE;
    }
    
    QPushButton:pressed {
        background-color: #005A9E;
    }
    
    QPushButton:disabled {
        background-color: #C8C6C4;
        color: #A19F9D;
    }
    
    /* 文本输入框样式 */
    QLineEdit, QTextEdit, QPlainTextEdit {
        border: 1px solid #C8C6C4;
        border-radius: 2px;
        padding: 4px;
        background-color: white;
        selection-background-color: #0078D7;
        selection-color: white;
    }
    
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
        border: 2px solid #0078D7;
    }
    
    /* 组合框样式 */
    QComboBox {
        border: 1px solid #C8C6C4;
        border-radius: 2px;
        padding: 4px;
        background-color: white;
        min-height: 20px;
    }
    
    QComboBox:editable {
        background-color: white;
    }
    
    QComboBox:on {
        border: 2px solid #0078D7;
    }
    
    /* 表格样式 */
    QTableView, QTableWidget {
        background-color: white;
        alternate-background-color: #FAF9F8;
        gridline-color: #EDEBE9;
        selection-background-color: #0078D7;
        selection-color: white;
        border: 1px solid #EDEBE9;
    }
    
    QHeaderView::section {
        background-color: #F3F2F1;
        padding: 4px;
        border: 1px solid #EDEBE9;
        font-weight: bold;
    }
    
    /* 标签页样式 */
    QTabWidget::pane {
        border: 1px solid #C8C6C4;
        background-color: white;
    }
    
    QTabBar::tab {
        background-color: #F3F2F1;
        padding: 8px 16px;
        margin-right: 2px;
        border: 1px solid #C8C6C4;
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }
    
    QTabBar::tab:selected {
        background-color: white;
        border-bottom: 2px solid #0078D7;
    }
    
    QTabBar::tab:hover:!selected {
        background-color: #E1DFDD;
    }
    
    /* 标签样式 */
    QLabel {
        color: #323130;
    }
    
    /* 进度条样式 */
    QProgressBar {
        border: 1px solid #C8C6C4;
        border-radius: 4px;
        text-align: center;
        background-color: #F3F2F1;
    }
    
    QProgressBar::chunk {
        background-color: #0078D7;
        border-radius: 3px;
    }
    
    /* 滚动条样式 */
    QScrollBar:vertical {
        border: none;
        background-color: #F3F2F1;
        width: 12px;
        border-radius: 6px;
    }
    
    QScrollBar::handle:vertical {
        background-color: #C8C6C4;
        border-radius: 6px;
        min-height: 20px;
    }
    
    QScrollBar::handle:vertical:hover {
        background-color: #A19F9D;
    }
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    
    /* 菜单栏样式 */
    QMenuBar {
        background-color: #F3F2F1;
        border-bottom: 1px solid #EDEBE9;
    }
    
    QMenuBar::item {
        padding: 4px 8px;
        background-color: transparent;
    }
    
    QMenuBar::item:selected {
        background-color: #E1DFDD;
    }
    
    /* 状态栏样式 */
    QStatusBar {
        background-color: #F3F2F1;
        border-top: 1px solid #EDEBE9;
    }
    
    /* 分组框样式 */
    QGroupBox {
        border: 1px solid #C8C6C4;
        border-radius: 4px;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: bold;
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px 0 5px;
    }
    
    /* 工具提示样式 */
    QToolTip {
        background-color: #323130;
        color: white;
        border: 1px solid #323130;
        padding: 4px;
        border-radius: 2px;
    }
    """
    
    if style_file and os.path.exists(style_file):
        try:
            with open(style_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"无法加载样式表文件: {e}")
            return default_stylesheet
    else:
        return default_stylesheet

def get_icon_path(icon_name: str) -> str:
    """
    获取图标路径
    
    Args:
        icon_name: 图标文件名
        
    Returns:
        str: 图标完整路径
    """
    # 首先检查icons目录
    icon_path = ICONS_DIR / icon_name
    if icon_path.exists():
        return str(icon_path)
    
    # 如果图标不存在，尝试使用系统图标或默认图标
    logger.warning(f"图标未找到: {icon_name}")
    
    # 返回默认图标路径
    default_icon = ICONS_DIR / "app_icon.png"
    if default_icon.exists():
        return str(default_icon)
    
    return ""

def create_icon(icon_name: str) -> QIcon:
    """
    创建QIcon
    
    Args:
        icon_name: 图标文件名
        
    Returns:
        QIcon: 图标对象
    """
    icon_path = get_icon_path(icon_name)
    if icon_path:
        return QIcon(icon_path)
    else:
        # 返回空图标
        return QIcon()

def format_hex(data: Union[bytes, bytearray, list, int], prefix: bool = True) -> str:
    """
    格式化数据为十六进制字符串
    
    Args:
        data: 要格式化的数据
        prefix: 是否添加0x前缀
        
    Returns:
        str: 十六进制字符串
    """
    if isinstance(data, (bytes, bytearray)):
        if not data:
            return ""
        hex_str = data.hex().upper()
        # 每2个字符添加空格
        spaced_str = ' '.join(hex_str[i:i+2] for i in range(0, len(hex_str), 2))
        return spaced_str
    elif isinstance(data, list):
        return ' '.join(f"{byte:02X}" for byte in data)
    elif isinstance(data, int):
        if prefix:
            return f"0x{data:X}"
        else:
            return f"{data:X}"
    else:
        return str(data)

def parse_hex_string(hex_str: str) -> bytes:
    """
    解析十六进制字符串为bytes
    
    Args:
        hex_str: 十六进制字符串
        
    Returns:
        bytes: 解析后的字节数据
    """
    if not hex_str:
        return b''
    
    # 移除空格和0x前缀
    hex_str = hex_str.strip().replace(' ', '').replace('0x', '').replace('0X', '')
    
    # 确保长度为偶数
    if len(hex_str) % 2 != 0:
        hex_str = '0' + hex_str
    
    try:
        return bytes.fromhex(hex_str)
    except ValueError as e:
        logger.error(f"无效的十六进制字符串: {hex_str}, 错误: {e}")
        return b''

def format_timestamp(timestamp: float, format_type: str = TIME_FORMAT_ABSOLUTE, 
                    reference_time: float = None) -> str:
    """
    格式化时间戳
    
    Args:
        timestamp: 时间戳
        format_type: 时间格式类型
        reference_time: 参考时间（用于相对时间）
        
    Returns:
        str: 格式化后的时间字符串
    """
    if format_type == TIME_FORMAT_ABSOLUTE:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%H:%M:%S.%f")[:-3]  # 毫秒级精度
        
    elif format_type == TIME_FORMAT_RELATIVE:
        if reference_time is None:
            reference_time = timestamp
        
        delta = timestamp - reference_time
        return f"{delta:.6f}"
        
    elif format_type == TIME_FORMAT_DELTA:
        if reference_time is None:
            return "0.000000"
        
        delta = timestamp - reference_time
        return f"+{delta:.6f}"
    
    else:
        return str(timestamp)

def calculate_crc(data: bytes, crc_type: str = "CRC16") -> int:
    """
    计算CRC校验码
    
    Args:
        data: 数据
        crc_type: CRC类型
        
    Returns:
        int: CRC值
    """
    if not data:
        return 0
    
    if crc_type == "CRC8":
        # CRC8简单实现
        crc = 0x00
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x07
                else:
                    crc <<= 1
                crc &= 0xFF
        return crc
        
    elif crc_type == "CRC16":
        # CRC16-CCITT (0x1021)
        crc = 0xFFFF
        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc <<= 1
                crc &= 0xFFFF
        return crc
        
    elif crc_type == "CRC32":
        # CRC32
        return hashlib.crc32(data) & 0xFFFFFFFF
        
    else:
        logger.warning(f"不支持的CRC类型: {crc_type}")
        return 0

def byte_to_bits(byte: int) -> List[int]:
    """
    将字节转换为位列表
    
    Args:
        byte: 字节值
        
    Returns:
        list: 位列表 (LSB first)
    """
    return [(byte >> i) & 1 for i in range(8)]

def bits_to_byte(bits: List[int]) -> int:
    """
    将位列表转换为字节
    
    Args:
        bits: 位列表 (LSB first)
        
    Returns:
        int: 字节值
    """
    byte = 0
    for i, bit in enumerate(bits):
        if bit:
            byte |= 1 << i
    return byte

def int_to_bytes(value: int, length: int, byteorder: str = 'big') -> bytes:
    """
    将整数转换为bytes
    
    Args:
        value: 整数值
        length: 字节长度
        byteorder: 字节序
        
    Returns:
        bytes: 字节数据
    """
    try:
        return value.to_bytes(length, byteorder)
    except OverflowError:
        logger.error(f"数值 {value} 超出 {length} 字节范围")
        return b'\x00' * length

def bytes_to_int(data: bytes, byteorder: str = 'big') -> int:
    """
    将bytes转换为整数
    
    Args:
        data: 字节数据
        byteorder: 字节序
        
    Returns:
        int: 整数值
    """
    try:
        return int.from_bytes(data, byteorder)
    except ValueError:
        logger.error(f"无效的字节数据: {data}")
        return 0

def get_system_info() -> Dict[str, str]:
    """
    获取系统信息
    
    Returns:
        dict: 系统信息
    """
    info = {
        'system': platform.system(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'python_version': platform.python_version(),
        'python_implementation': platform.python_implementation(),
    }
    
    # 添加内存信息
    try:
        import psutil
        memory = psutil.virtual_memory()
        info['memory_total'] = f"{memory.total / 1024**3:.2f} GB"
        info['memory_available'] = f"{memory.available / 1024**3:.2f} GB"
    except ImportError:
        info['memory_info'] = "psutil未安装"
    
    # 添加CPU信息
    try:
        info['cpu_count'] = str(os.cpu_count())
    except:
        info['cpu_count'] = "未知"
    
    return info

def open_file_dialog(parent=None, title: str = "打开文件", 
                    file_filter: str = "所有文件 (*.*)") -> str:
    """
    打开文件对话框
    
    Args:
        parent: 父窗口
        title: 对话框标题
        file_filter: 文件过滤器
        
    Returns:
        str: 选择的文件路径
    """
    file_path, _ = QFileDialog.getOpenFileName(parent, title, "", file_filter)
    return file_path

def save_file_dialog(parent=None, title: str = "保存文件",
                    file_filter: str = "所有文件 (*.*)",
                    default_name: str = "") -> str:
    """
    保存文件对话框
    
    Args:
        parent: 父窗口
        title: 对话框标题
        file_filter: 文件过滤器
        default_name: 默认文件名
        
    Returns:
        str: 保存的文件路径
    """
    file_path, _ = QFileDialog.getSaveFileName(parent, title, default_name, file_filter)
    return file_path

def select_directory_dialog(parent=None, title: str = "选择目录") -> str:
    """
    选择目录对话框
    
    Args:
        parent: 父窗口
        title: 对话框标题
        
    Returns:
        str: 选择的目录路径
    """
    dir_path = QFileDialog.getExistingDirectory(parent, title, "")
    return dir_path

def show_message_box(parent=None, title: str = "消息", 
                    message: str = "", message_type: str = "info") -> int:
    """
    显示消息框
    
    Args:
        parent: 父窗口
        title: 标题
        message: 消息内容
        message_type: 消息类型 (info, warning, error, question)
        
    Returns:
        int: 用户选择的按钮
    """
    if message_type == "info":
        return QMessageBox.information(parent, title, message)
    elif message_type == "warning":
        return QMessageBox.warning(parent, title, message)
    elif message_type == "error":
        return QMessageBox.critical(parent, title, message)
    elif message_type == "question":
        return QMessageBox.question(parent, title, message)
    else:
        return QMessageBox.information(parent, title, message)

def show_input_dialog(parent=None, title: str = "输入", 
                     label: str = "请输入:", default_text: str = "",
                     echo_mode: QLineEdit.EchoMode = QLineEdit.Normal) -> Tuple[str, bool]:
    """
    显示输入对话框
    
    Args:
        parent: 父窗口
        title: 标题
        label: 标签文本
        default_text: 默认文本
        echo_mode: 回显模式
        
    Returns:
        tuple: (输入的文本, 是否成功)
    """
    text, ok = QInputDialog.getText(parent, title, label, echo_mode, default_text)
    return text, ok

def show_about_dialog(parent=None) -> None:
    """
    显示关于对话框
    """
    about_text = f"""
    <h2>{APP_NAME}</h2>
    <p>版本: {APP_VERSION}</p>
    <p>{APP_DESCRIPTION}</p>
    <p>作者: {APP_AUTHOR}</p>
    <p>{APP_COPYRIGHT}</p>
    <hr>
    <p>这是一个功能强大的UDS诊断工具，支持多种CAN卡和完整的UDS协议。</p>
    <p>如需帮助，请访问项目主页或查看用户手册。</p>
    """
    
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle("关于")
    msg_box.setTextFormat(Qt.RichText)
    msg_box.setText(about_text)
    msg_box.setIconPixmap(QPixmap(get_icon_path(ICON_APP)).scaled(64, 64, Qt.KeepAspectRatio))
    msg_box.exec_()

def validate_can_id(can_id: str, extended: bool = False) -> Tuple[bool, Optional[int]]:
    """
    验证CAN ID
    
    Args:
        can_id: CAN ID字符串
        extended: 是否为扩展ID
        
    Returns:
        tuple: (是否有效, 转换后的ID)
    """
    if not can_id:
        return False, None
    
    # 移除空格和0x前缀
    can_id = can_id.strip().replace(' ', '').replace('0x', '').replace('0X', '')
    
    if not can_id:
        return False, None
    
    try:
        # 转换为整数
        can_id_int = int(can_id, 16)
        
        # 检查范围
        if extended:
            if 0 <= can_id_int <= 0x1FFFFFFF:
                return True, can_id_int
        else:
            if 0 <= can_id_int <= 0x7FF:
                return True, can_id_int
        
        return False, None
        
    except ValueError:
        return False, None

def validate_hex_data(hex_data: str) -> Tuple[bool, Optional[bytes]]:
    """
    验证十六进制数据
    
    Args:
        hex_data: 十六进制数据字符串
        
    Returns:
        tuple: (是否有效, 转换后的bytes)
    """
    if not hex_data:
        return True, b''
    
    # 移除空格
    hex_data = hex_data.strip().replace(' ', '')
    
    if not hex_data:
        return True, b''
    
    # 检查是否为有效的十六进制字符串
    if not re.match(r'^[0-9A-Fa-f]+$', hex_data):
        return False, None
    
    # 检查长度是否为偶数
    if len(hex_data) % 2 != 0:
        return False, None
    
    try:
        data_bytes = bytes.fromhex(hex_data)
        return True, data_bytes
    except ValueError:
        return False, None

def safe_execute(func: Callable, *args, **kwargs) -> Tuple[bool, Any]:
    """
    安全执行函数，捕获异常
    
    Args:
        func: 要执行的函数
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        tuple: (是否成功, 返回值)
    """
    try:
        result = func(*args, **kwargs)
        return True, result
    except Exception as e:
        logger.error(f"函数执行失败 {func.__name__}: {e}")
        traceback.print_exc()
        return False, None

def retry_on_failure(func: Callable, max_retries: int = 3, 
                    delay: float = 1.0, *args, **kwargs) -> Tuple[bool, Any]:
    """
    失败重试
    
    Args:
        func: 要执行的函数
        max_retries: 最大重试次数
        delay: 重试延迟（秒）
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        tuple: (是否成功, 返回值)
    """
    for attempt in range(max_retries):
        success, result = safe_execute(func, *args, **kwargs)
        
        if success:
            return True, result
        
        if attempt < max_retries - 1:
            logger.warning(f"重试 {func.__name__} ({attempt + 1}/{max_retries})")
            time.sleep(delay)
    
    return False, None

def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小
    
    Args:
        size_bytes: 文件大小（字节）
        
    Returns:
        str: 格式化后的文件大小
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    
    return f"{s} {size_names[i]}"

def get_file_hash(file_path: str, algorithm: str = "md5") -> str:
    """
    计算文件哈希值
    
    Args:
        file_path: 文件路径
        algorithm: 哈希算法
        
    Returns:
        str: 哈希值
    """
    if not os.path.exists(file_path):
        return ""
    
    hash_func = hashlib.new(algorithm)
    
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        
        return hash_func.hexdigest()
    except Exception as e:
        logger.error(f"计算文件哈希失败: {e}")
        return ""

def create_backup(file_path: str, backup_dir: str = None) -> bool:
    """
    创建文件备份
    
    Args:
        file_path: 文件路径
        backup_dir: 备份目录
        
    Returns:
        bool: 是否成功
    """
    if not os.path.exists(file_path):
        return False
    
    try:
        # 确定备份目录
        if backup_dir is None:
            backup_dir = os.path.join(os.path.dirname(file_path), "backup")
        
        # 创建备份目录
        os.makedirs(backup_dir, exist_ok=True)
        
        # 生成备份文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = os.path.basename(file_path)
        backup_name = f"{file_name}.backup_{timestamp}"
        backup_path = os.path.join(backup_dir, backup_name)
        
        # 复制文件
        import shutil
        shutil.copy2(file_path, backup_path)
        
        logger.info(f"创建备份: {backup_path}")
        return True
        
    except Exception as e:
        logger.error(f"创建备份失败: {e}")
        return False

def cleanup_old_files(directory: str, pattern: str, max_files: int = 10) -> None:
    """
    清理旧文件
    
    Args:
        directory: 目录路径
        pattern: 文件名模式
        max_files: 保留的最大文件数
    """
    try:
        import glob
        import os
        
        files = glob.glob(os.path.join(directory, pattern))
        
        # 按修改时间排序
        files.sort(key=os.path.getmtime, reverse=True)
        
        # 删除旧文件
        for file_path in files[max_files:]:
            try:
                os.remove(file_path)
                logger.debug(f"删除旧文件: {file_path}")
            except Exception as e:
                logger.warning(f"无法删除文件 {file_path}: {e}")
                
    except Exception as e:
        logger.error(f"清理旧文件失败: {e}")

def check_for_updates(current_version: str) -> Dict[str, Any]:
    """
    检查更新
    
    Args:
        current_version: 当前版本
        
    Returns:
        dict: 更新信息
    """
    import requests
    
    try:
        response = requests.get(UPDATE_CHECK_URL, timeout=5)
        
        if response.status_code == 200:
            release_info = response.json()
            
            latest_version = release_info.get('tag_name', '').lstrip('v')
            update_available = latest_version > current_version
            
            return {
                'update_available': update_available,
                'current_version': current_version,
                'latest_version': latest_version,
                'release_notes': release_info.get('body', ''),
                'download_url': release_info.get('html_url', ''),
                'published_at': release_info.get('published_at', '')
            }
        else:
            logger.warning(f"更新检查失败: HTTP {response.status_code}")
            
    except requests.RequestException as e:
        logger.debug(f"更新检查失败: {e}")
    
    return {
        'update_available': False,
        'current_version': current_version,
        'latest_version': current_version,
        'release_notes': '',
        'download_url': '',
        'published_at': ''
    }