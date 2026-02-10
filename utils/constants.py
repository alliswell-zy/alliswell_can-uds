#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
常量定义 - 应用程序中使用的所有常量
"""

import os
from pathlib import Path

# ========== 应用程序信息 ==========
APP_NAME = "UDS诊断工具"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "支持多种CAN卡的UDS诊断工具，支持CAN FD UDS协议"
APP_AUTHOR = "UDS Diagnostics Team"
APP_COPYRIGHT = "© 2024 UDS Diagnostics Team"

# ========== 文件路径常量 ==========
# 获取项目根目录
if 'UDS_TOOL_HOME' in os.environ:
    PROJECT_ROOT = Path(os.environ['UDS_TOOL_HOME'])
else:
    PROJECT_ROOT = Path(__file__).parent.parent

# 目录路径
CONFIG_DIR = PROJECT_ROOT / "config"
CORE_DIR = PROJECT_ROOT / "core"
UI_DIR = PROJECT_ROOT / "ui"
UTILS_DIR = PROJECT_ROOT / "utils"
ICONS_DIR = PROJECT_ROOT / "icons"
LOGS_DIR = PROJECT_ROOT / "logs"
PROJECTS_DIR = PROJECT_ROOT / "projects"
TEMP_DIR = PROJECT_ROOT / "temp"

# 确保目录存在
for directory in [LOGS_DIR, PROJECTS_DIR, TEMP_DIR]:
    directory.mkdir(exist_ok=True, parents=True)

# 文件路径
LOG_FILE = LOGS_DIR / "uds_tool.log"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
DEFAULT_PROJECT_FILE = PROJECTS_DIR / "default.udsp"

# ========== 用户界面常量 ==========
# 窗口尺寸
MAIN_WINDOW_WIDTH = 1400
MAIN_WINDOW_HEIGHT = 900
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600

# 对话框尺寸
SETTINGS_DIALOG_WIDTH = 800
SETTINGS_DIALOG_HEIGHT = 600
ABOUT_DIALOG_WIDTH = 400
ABOUT_DIALOG_HEIGHT = 300

# 表格尺寸
TABLE_ROW_HEIGHT = 25
TABLE_HEADER_HEIGHT = 30

# 字体
FONT_FAMILY = "Microsoft YaHei"
FONT_SIZE_SMALL = 9
FONT_SIZE_NORMAL = 10
FONT_SIZE_LARGE = 12
FONT_SIZE_TITLE = 14
FONT_SIZE_HEADER = 16

# 颜色 (明亮风格)
COLOR_PRIMARY = "#0078D7"      # 主色调 - 蓝色
COLOR_SECONDARY = "#605E5C"    # 次要色调 - 灰色
COLOR_SUCCESS = "#107C10"      # 成功 - 绿色
COLOR_WARNING = "#FFB900"      # 警告 - 黄色
COLOR_ERROR = "#D13438"        # 错误 - 红色
COLOR_INFO = "#0078D7"         # 信息 - 蓝色
COLOR_DISABLED = "#C8C6C4"     # 禁用 - 浅灰

# 背景颜色
BG_LIGHT = "#FFFFFF"           # 浅色背景
BG_DARK = "#F3F2F1"            # 深色背景
BG_ALTERNATE = "#FAF9F8"       # 交替行背景

# 文本颜色
TEXT_PRIMARY = "#323130"       # 主要文本
TEXT_SECONDARY = "#605E5C"     # 次要文本
TEXT_DISABLED = "#A19F9D"      # 禁用文本
TEXT_LIGHT = "#FFFFFF"         # 浅色背景上的文本

# 边框颜色
BORDER_LIGHT = "#EDEBE9"       # 浅色边框
BORDER_MEDIUM = "#C8C6C4"      # 中等边框
BORDER_DARK = "#8A8886"        # 深色边框

# ========== CAN总线常量 ==========
# 标准波特率
CAN_STANDARD_BAUDRATES = [
    10000,    # 10 kbps
    20000,    # 20 kbps
    50000,    # 50 kbps
    100000,   # 100 kbps
    125000,   # 125 kbps
    250000,   # 250 kbps
    500000,   # 500 kbps
    800000,   # 800 kbps
    1000000,  # 1 Mbps
]

# CAN FD波特率
CANFD_DATA_BAUDRATES = [
    500000,    # 0.5 Mbps
    1000000,   # 1 Mbps
    2000000,   # 2 Mbps
    5000000,   # 5 Mbps
    8000000,   # 8 Mbps
    10000000,  # 10 Mbps
]

# DLC值
CAN_DLC_VALUES = list(range(0, 9))  # 0-8
CANFD_DLC_VALUES = list(range(0, 16))  # 0-15

# DLC到数据长度映射 (CAN FD)
CANFD_DLC_TO_LENGTH = {
    0: 0, 1: 1, 2: 2, 3: 3, 4: 4,
    5: 5, 6: 6, 7: 7, 8: 8,
    9: 12, 10: 16, 11: 20, 12: 24,
    13: 32, 14: 48, 15: 64
}

# ========== UDS协议常量 ==========
# UDS服务ID范围
UDS_SERVICE_ID_MIN = 0x00
UDS_SERVICE_ID_MAX = 0xFF

# 数据标识符范围
UDS_DID_MIN = 0x0000
UDS_DID_MAX = 0xFFFF

# 默认会话参数
UDS_DEFAULT_P2_TIMEOUT = 50      # ms
UDS_DEFAULT_P2STAR_TIMEOUT = 5000  # ms
UDS_DEFAULT_P4_TIMEOUT = 5000    # ms

# ISO-TP参数
ISOTP_DEFAULT_STMIN = 0          # ms
ISOTP_DEFAULT_BLOCK_SIZE = 8
ISOTP_DEFAULT_SEPARATION_TIME = 0  # ms

# ========== 通信常量 ==========
# 默认CAN ID
DEFAULT_CAN_RX_ID = 0x7E0
DEFAULT_CAN_TX_ID = 0x7E8

# 帧类型
FRAME_TYPE_STANDARD = "standard"
FRAME_TYPE_EXTENDED = "extended"

# 寻址模式
ADDRESSING_MODE_NORMAL = "normal"
ADDRESSING_MODE_EXTENDED = "extended"
ADDRESSING_MODE_MIXED = "mixed"

# ========== 时间常量 ==========
# 时间格式
TIME_FORMAT_ABSOLUTE = "absolute"   # 绝对时间
TIME_FORMAT_RELATIVE = "relative"   # 相对时间
TIME_FORMAT_DELTA = "delta"         # 增量时间

# 超时时间 (毫秒)
TIMEOUT_CAN_SEND = 100      # CAN发送超时
TIMEOUT_UDS_RESPONSE = 2000 # UDS响应超时
TIMEOUT_CONNECTION = 5000   # 连接超时

# ========== 错误代码常量 ==========
# 应用程序错误代码
ERROR_SUCCESS = 0
ERROR_GENERAL = 1
ERROR_CONFIG = 2
ERROR_CAN_INTERFACE = 3
ERROR_UDS_PROTOCOL = 4
ERROR_FILE_IO = 5
ERROR_VALIDATION = 6
ERROR_TIMEOUT = 7
ERROR_NOT_CONNECTED = 8

# ========== 正则表达式常量 ==========
# 十六进制字符串
REGEX_HEX_STRING = r'^[0-9A-Fa-f\s]+$'

# CAN ID (标准或扩展)
REGEX_CAN_ID_STANDARD = r'^[0-7][0-9A-Fa-f]{0,2}$|^[0-9A-Fa-f]{1,3}$'
REGEX_CAN_ID_EXTENDED = r'^[0-9A-Fa-f]{1,8}$'

# 数据字节 (十六进制，空格分隔)
REGEX_DATA_BYTES = r'^([0-9A-Fa-f]{2}\s*)*$'

# 文件名 (Windows/Linux兼容)
REGEX_FILENAME = r'^[^<>:"/\\|?*]+$'

# ========== 配置常量 ==========
# 配置版本
CONFIG_VERSION = "1.0"

# 默认配置值
DEFAULT_CAN_INTERFACE = "virtual"
DEFAULT_CAN_CHANNEL = "0"
DEFAULT_CAN_BAUDRATE = 500000
DEFAULT_CANFD_BAUDRATE = 2000000

# ========== 日志常量 ==========
# 日志级别
LOG_LEVEL_DEBUG = "DEBUG"
LOG_LEVEL_INFO = "INFO"
LOG_LEVEL_WARNING = "WARNING"
LOG_LEVEL_ERROR = "ERROR"
LOG_LEVEL_CRITICAL = "CRITICAL"

# 日志格式
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# ========== 键值常量 ==========
# 快捷键
KEY_NEW_PROJECT = "Ctrl+N"
KEY_OPEN_PROJECT = "Ctrl+O"
KEY_SAVE_PROJECT = "Ctrl+S"
KEY_SAVE_AS_PROJECT = "Ctrl+Shift+S"
KEY_CONNECT = "Ctrl+C"
KEY_DISCONNECT = "Ctrl+D"
KEY_SEND = "Ctrl+Enter"
KEY_CLEAR = "Ctrl+L"
KEY_EXIT = "Ctrl+Q"
KEY_HELP = "F1"
KEY_ABOUT = "F2"

# ========== 资源常量 ==========
# 图标名称
ICON_APP = "app_icon.png"
ICON_CONNECT = "connect.png"
ICON_DISCONNECT = "disconnect.png"
ICON_SEND = "send.png"
ICON_CLEAR = "clear.png"
ICON_SAVE = "save.png"
ICON_LOAD = "load.png"
ICON_SETTINGS = "settings.png"
ICON_HELP = "help.png"
ICON_ABOUT = "about.png"
ICON_PLAY = "play.png"
ICON_STOP = "stop.png"
ICON_PAUSE = "pause.png"
ICON_ADD = "add.png"
ICON_REMOVE = "remove.png"
ICON_EDIT = "edit.png"
ICON_COPY = "copy.png"
ICON_PASTE = "paste.png"
ICON_SEARCH = "search.png"
ICON_FILTER = "filter.png"
ICON_EXPORT = "export.png"
ICON_IMPORT = "import.png"

# ========== 国际化常量 ==========
# 支持的语言
LANGUAGES = {
    "en": "English",
    "zh_CN": "简体中文",
    "zh_TW": "繁體中文",
    "ja": "日本語",
    "ko": "한국어",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
}

# 默认语言
DEFAULT_LANGUAGE = "zh_CN"

# ========== 其他常量 ==========
# 最大限制
MAX_CAN_ID = 0x1FFFFFFF  # 29位扩展ID
MAX_DATA_LENGTH = 64     # CAN FD最大数据长度
MAX_FRAME_SIZE = 4095    # ISO-TP最大帧大小
MAX_LOG_LINES = 10000    # 最大日志行数

# 更新检查
UPDATE_CHECK_URL = "https://api.github.com/repos/uds-diagnostics/uds-tool/releases/latest"
UPDATE_CHECK_INTERVAL = 86400  # 24小时

# 版本检查
MIN_PYTHON_VERSION = (3, 8)
RECOMMENDED_PYTHON_VERSION = (3, 13)

# 许可证信息
LICENSE_TEXT = """
UDS诊断工具 - 开源诊断工具
版权所有 © 2024 UDS Diagnostics Team

本程序是自由软件：您可以根据自由软件基金会发布的GNU通用公共许可证的条款重新分发和/或修改它，许可证版本为3或更高版本。

本程序是希望它有用，但没有任何保证；甚至没有适销性或特定用途适用性的隐含保证。有关更多详细信息，请参阅GNU通用公共许可证。

您应该已经收到了一份GNU通用公共许可证的副本。如果没有，请参阅<http://www.gnu.org/licenses/>。
"""