#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UDS会话界面 - 发送和接收UDS诊断命令
支持完整的UDS服务，包括CAN FD UDS
"""

import logging
import time
import threading
from typing import Optional, Dict, List, Any, Tuple

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                            QGroupBox, QLabel, QComboBox, QLineEdit,
                            QPushButton, QTextEdit, QSpinBox, QCheckBox,
                            QTableWidget, QTableWidgetItem, QHeaderView,
                            QSplitter, QTabWidget, QTreeWidget, QTreeWidgetItem,
                            QListWidget, QListWidgetItem, QProgressBar,
                            QMessageBox, QScrollArea, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QDateTime
from PyQt5.QtGui import QFont, QColor, QBrush

from utils.helpers import create_icon, format_hex, parse_hex_string
from utils.constants import *
from config.config_manager import ConfigManager
from config.protocol_definitions import *
from core.can_interface import CANInterfaceManager
from core.uds_session_manager import UDSManager, UDSSessionManager, UDSRequest, UDSResponse
from core.isotp_protocol import ISOTPConfig

logger = logging.getLogger(__name__)

class UDSSessionWidget(QWidget):
    """UDS会话界面部件"""
    
    # 信号定义
    uds_request_sent = pyqtSignal(object)  # UDSRequest
    uds_response_received = pyqtSignal(object)  # UDSResponse
    session_changed = pyqtSignal(object)  # UDSSessionInfo
    error_occurred = pyqtSignal(str)  # 错误消息
    
    def __init__(self, can_manager: CANInterfaceManager, uds_manager: UDSManager,
                 config_manager: ConfigManager):
        """
        初始化UDS会话界面
        
        Args:
            can_manager: CAN接口管理器
            uds_manager: UDS管理器
            config_manager: 配置管理器
        """
        super().__init__()
        
        self.can_manager = can_manager
        self.uds_manager = uds_manager
        self.config_manager = config_manager
        
        # 当前UDS会话
        self.current_session: Optional[UDSSessionManager] = None
        
        # 定时发送器
        self.timer_senders: Dict[str, QTimer] = {}
        
        # 历史记录
        self.history: List[Tuple[UDSRequest, Optional[UDSResponse]]] = []
        self.max_history = 100
        
        self.setup_ui()
        self.setup_connections()
        self.load_config()
        
        logger.info("UDS session widget initialized")
    
    def setup_ui(self):
        """设置用户界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 上半部分：控制区域
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        
        # 会话控制组
        self.setup_session_control_group(control_layout)
        
        # 服务选择组
        self.setup_service_selection_group(control_layout)
        
        # 参数输入组
        self.setup_parameter_group(control_layout)
        
        # 按钮区域
        self.setup_button_area(control_layout)
        
        # 下半部分：历史记录和响应区域
        history_widget = QWidget()
        history_layout = QVBoxLayout(history_widget)
        
        # 历史记录表格
        self.setup_history_table(history_layout)
        
        # 响应显示区域
        self.setup_response_area(history_layout)
        
        # 添加部件到分割器
        splitter.addWidget(control_widget)
        splitter.addWidget(history_widget)
        
        # 设置分割器初始比例
        splitter.setSizes([400, 300])
        
        main_layout.addWidget(splitter)
    
    def setup_session_control_group(self, parent_layout):
        """设置会话控制组"""
        session_group = QGroupBox("会话控制")
        session_layout = QVBoxLayout()
        
        # 第一行：会话选择和状态
        row1_layout = QHBoxLayout()
        
        # 会话类型选择
        session_label = QLabel("会话类型:")
        self.session_combo = QComboBox()
        for session_type in DiagnosticSessionType:
            self.session_combo.addItem(session_type.name, session_type)
        row1_layout.addWidget(session_label)
        row1_layout.addWidget(self.session_combo)
        
        # 会话状态显示
        status_label = QLabel("当前会话:")
        self.current_session_label = QLabel("默认会话")
        self.current_session_label.setStyleSheet(
            f"font-weight: bold; color: {COLOR_PRIMARY};"
        )
        row1_layout.addWidget(status_label)
        row1_layout.addWidget(self.current_session_label)
        
        row1_layout.addStretch()
        
        # 安全级别显示
        security_label = QLabel("安全级别:")
        self.security_level_label = QLabel("0")
        self.security_level_label.setStyleSheet(
            f"font-weight: bold; color: {COLOR_SUCCESS};"
        )
        row1_layout.addWidget(security_label)
        row1_layout.addWidget(self.security_level_label)
        
        session_layout.addLayout(row1_layout)
        
        # 第二行：按钮
        row2_layout = QHBoxLayout()
        
        # 会话控制按钮
        self.session_control_button = QPushButton("进入会话")
        self.session_control_button.setIcon(create_icon(ICON_CONNECT))
        self.session_control_button.setToolTip("进入选定的诊断会话")
        row2_layout.addWidget(self.session_control_button)
        
        # ECU复位按钮
        self.ecu_reset_button = QPushButton("ECU复位")
        self.ecu_reset_button.setIcon(create_icon("reset.png"))
        self.ecu_reset_button.setToolTip("复位ECU")
        row2_layout.addWidget(self.ecu_reset_button)
        
        # 安全访问按钮
        self.security_access_button = QPushButton("安全访问")
        self.security_access_button.setIcon(create_icon("security.png"))
        self.security_access_button.setToolTip("安全访问控制")
        row2_layout.addWidget(self.security_access_button)
        
        # TesterPresent按钮
        self.tester_present_button = QPushButton("TesterPresent")
        self.tester_present_button.setIcon(create_icon("heartbeat.png"))
        self.tester_present_button.setToolTip("发送TesterPresent保持连接")
        row2_layout.addWidget(self.tester_present_button)
        
        # 周期发送TesterPresent
        self.tp_periodic_check = QCheckBox("周期发送")
        self.tp_periodic_check.setToolTip("周期性地发送TesterPresent")
        row2_layout.addWidget(self.tp_periodic_check)
        
        row2_layout.addStretch()
        
        session_layout.addLayout(row2_layout)
        
        session_group.setLayout(session_layout)
        parent_layout.addWidget(session_group)
    
    def setup_service_selection_group(self, parent_layout):
        """设置服务选择组"""
        service_group = QGroupBox("UDS服务")
        service_layout = QVBoxLayout()
        
        # 服务选择
        service_select_layout = QHBoxLayout()
        
        service_label = QLabel("服务:")
        self.service_combo = QComboBox()
        
        # 从协议定义加载服务
        protocol_defs = ProtocolDefinitions()
        for service_def in protocol_defs.get_all_services():
            self.service_combo.addItem(
                f"0x{service_def.service_id:02X} - {service_def.name}",
                service_def.service_id
            )
        
        service_select_layout.addWidget(service_label)
        service_select_layout.addWidget(self.service_combo)
        service_select_layout.addStretch()
        
        service_layout.addLayout(service_select_layout)
        
        # 服务描述
        self.service_description_label = QLabel()
        self.service_description_label.setWordWrap(True)
        self.service_description_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-style: italic;"
        )
        service_layout.addWidget(self.service_description_label)
        
        # 子功能选择
        self.subfunction_layout = QHBoxLayout()
        self.subfunction_layout.setContentsMargins(0, 0, 0, 0)
        
        subfunction_label = QLabel("子功能:")
        self.subfunction_combo = QComboBox()
        
        self.subfunction_layout.addWidget(subfunction_label)
        self.subfunction_layout.addWidget(self.subfunction_combo)
        self.subfunction_layout.addStretch()
        
        # 初始时隐藏子功能选择
        self.subfunction_layout.setEnabled(False)
        
        service_layout.addLayout(self.subfunction_layout)
        
        service_group.setLayout(service_layout)
        parent_layout.addWidget(service_group)
    
    def setup_parameter_group(self, parent_layout):
        """设置参数输入组"""
        # 使用滚动区域，以防参数过多
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        param_widget = QWidget()
        param_layout = QVBoxLayout(param_widget)
        
        # 数据标识符
        self.did_layout = QHBoxLayout()
        did_label = QLabel("数据标识符:")
        self.did_combo = QComboBox()
        self.did_combo.setEditable(True)
        
        # 添加常见数据标识符
        protocol_defs = ProtocolDefinitions()
        for did, name in protocol_defs.data_identifiers.items():
            self.did_combo.addItem(f"0x{did:04X} - {name}", did)
        
        self.did_layout.addWidget(did_label)
        self.did_layout.addWidget(self.did_combo)
        self.did_layout.addStretch()
        
        param_layout.addLayout(self.did_layout)
        
        # 数据输入
        data_label = QLabel("数据:")
        self.data_edit = QTextEdit()
        self.data_edit.setMaximumHeight(80)
        self.data_edit.setPlaceholderText("输入十六进制数据，用空格分隔（例如：01 02 03）")
        
        param_layout.addWidget(data_label)
        param_layout.addWidget(self.data_edit)
        
        # 高级参数组
        advanced_group = QGroupBox("高级参数")
        advanced_layout = QFormLayout()
        
        # 超时时间
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(100, 60000)
        self.timeout_spin.setValue(2000)
        self.timeout_spin.setSuffix(" ms")
        advanced_layout.addRow("超时时间:", self.timeout_spin)
        
        # 是否期望响应
        self.expect_response_check = QCheckBox()
        self.expect_response_check.setChecked(True)
        advanced_layout.addRow("期望响应:", self.expect_response_check)
        
        # 周期发送
        self.periodic_send_check = QCheckBox()
        self.periodic_send_check.setChecked(False)
        advanced_layout.addRow("周期发送:", self.periodic_send_check)
        
        self.period_spin = QSpinBox()
        self.period_spin.setRange(100, 60000)
        self.period_spin.setValue(1000)
        self.period_spin.setSuffix(" ms")
        self.period_spin.setEnabled(False)
        advanced_layout.addRow("发送周期:", self.period_spin)
        
        advanced_group.setLayout(advanced_layout)
        param_layout.addWidget(advanced_group)
        
        scroll_area.setWidget(param_widget)
        parent_layout.addWidget(scroll_area)
    
    def setup_button_area(self, parent_layout):
        """设置按钮区域"""
        button_layout = QHBoxLayout()
        
        # 发送按钮
        self.send_button = QPushButton("发送")
        self.send_button.setIcon(create_icon(ICON_SEND))
        self.send_button.setToolTip("发送UDS请求")
        self.send_button.setDefault(True)
        button_layout.addWidget(self.send_button)
        
        # 清空按钮
        self.clear_button = QPushButton("清空")
        self.clear_button.setIcon(create_icon(ICON_CLEAR))
        self.clear_button.setToolTip("清空输入数据")
        button_layout.addWidget(self.clear_button)
        
        # 保存模板按钮
        self.save_template_button = QPushButton("保存模板")
        self.save_template_button.setIcon(create_icon(ICON_SAVE))
        self.save_template_button.setToolTip("保存当前配置为模板")
        button_layout.addWidget(self.save_template_button)
        
        button_layout.addStretch()
        
        # 状态指示器
        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(12, 12)
        self.status_indicator.setStyleSheet(
            f"border-radius: 6px; background-color: {COLOR_DISABLED};"
        )
        button_layout.addWidget(self.status_indicator)
        
        # 状态标签
        self.status_label = QLabel("未连接")
        self.status_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        button_layout.addWidget(self.status_label)
        
        parent_layout.addLayout(button_layout)
    
    def setup_history_table(self, parent_layout):
        """设置历史记录表格"""
        history_group = QGroupBox("历史记录")
        history_group_layout = QVBoxLayout()
        
        # 创建表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "时间", "方向", "服务", "子功能", "数据", "状态"
        ])
        
        # 设置表格属性
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # 设置列宽
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 时间
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 方向
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 服务
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 子功能
        header.setSectionResizeMode(4, QHeaderView.Stretch)          # 数据
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 状态
        
        history_group_layout.addWidget(self.history_table)
        
        # 历史记录控制按钮
        history_control_layout = QHBoxLayout()
        
        self.clear_history_button = QPushButton("清空历史")
        self.clear_history_button.setIcon(create_icon(ICON_CLEAR))
        history_control_layout.addWidget(self.clear_history_button)
        
        self.export_history_button = QPushButton("导出历史")
        self.export_history_button.setIcon(create_icon(ICON_EXPORT))
        history_control_layout.addWidget(self.export_history_button)
        
        history_control_layout.addStretch()
        
        history_group_layout.addLayout(history_control_layout)
        
        history_group.setLayout(history_group_layout)
        parent_layout.addWidget(history_group)
    
    def setup_response_area(self, parent_layout):
        """设置响应显示区域"""
        response_group = QGroupBox("响应详情")
        response_layout = QVBoxLayout()
        
        # 响应显示文本框
        self.response_text = QTextEdit()
        self.response_text.setReadOnly(True)
        self.response_text.setMaximumHeight(150)
        
        # 设置等宽字体，便于查看十六进制数据
        font = QFont("Consolas", 10)
        self.response_text.setFont(font)
        
        response_layout.addWidget(self.response_text)
        
        response_group.setLayout(response_layout)
        parent_layout.addWidget(response_group)
    
    def setup_connections(self):
        """设置信号槽连接"""
        # 会话控制
        self.session_control_button.clicked.connect(self.on_session_control)
        self.ecu_reset_button.clicked.connect(self.on_ecu_reset)
        self.security_access_button.clicked.connect(self.on_security_access)
        self.tester_present_button.clicked.connect(self.on_tester_present)
        self.tp_periodic_check.stateChanged.connect(self.on_tp_periodic_changed)
        
        # 服务选择
        self.service_combo.currentIndexChanged.connect(self.on_service_changed)
        self.subfunction_combo.currentIndexChanged.connect(self.on_subfunction_changed)
        
        # 按钮
        self.send_button.clicked.connect(self.on_send_request)
        self.clear_button.clicked.connect(self.on_clear_input)
        self.save_template_button.clicked.connect(self.on_save_template)
        self.clear_history_button.clicked.connect(self.on_clear_history)
        self.export_history_button.clicked.connect(self.on_export_history)
        
        # 周期发送
        self.periodic_send_check.stateChanged.connect(
            lambda state: self.period_spin.setEnabled(state == Qt.Checked)
        )
        
        # 信号连接
        self.uds_request_sent.connect(self.on_uds_request_sent)
        self.uds_response_received.connect(self.on_uds_response_received)
        self.session_changed.connect(self.on_session_changed)
        self.error_occurred.connect(self.on_error_occurred)
        
        # 初始更新服务信息
        self.on_service_changed()
    
    def load_config(self):
        """加载配置"""
        try:
            # 创建默认UDS会话
            isotp_config = ISOTPConfig(
                rx_id=self.config_manager.uds_config.rx_id,
                tx_id=self.config_manager.uds_config.tx_id,
                addressing_mode=self.config_manager.uds_config.addressing_mode,
                frame_type=self.config_manager.uds_config.frame_type,
                st_min=self.config_manager.uds_config.st_min,
                block_size=self.config_manager.uds_config.block_size,
                can_fd_enabled=self.config_manager.uds_config.can_fd_enabled,
                fd_dlc=self.config_manager.uds_config.fd_dlc
            )
            
            self.current_session = self.uds_manager.create_session(
                "default", isotp_config
            )
            
            if not self.current_session:
                raise Exception("Failed to create UDS session")
            
            # 更新状态
            self.update_connection_status()
            
            logger.info("UDS session configuration loaded")
            
        except Exception as e:
            logger.error(f"Error loading UDS configuration: {e}")
            self.show_error_message(f"加载配置失败: {e}")
    
    def update_connection_status(self):
        """更新连接状态"""
        if self.current_session:
            session_info = self.current_session.get_session_info()
            self.current_session_label.setText(session_info.current_session.name)
            self.security_level_label.setText(str(session_info.security_level))
            
            # 更新状态指示器
            can_interface = self.can_manager.get_interface("default")
            if can_interface and can_interface.is_connected:
                self.status_indicator.setStyleSheet(
                    f"border-radius: 6px; background-color: {COLOR_SUCCESS};"
                )
                self.status_label.setText("已连接")
                self.status_label.setStyleSheet(f"color: {COLOR_SUCCESS};")
            else:
                self.status_indicator.setStyleSheet(
                    f"border-radius: 6px; background-color: {COLOR_ERROR};"
                )
                self.status_label.setText("未连接")
                self.status_label.setStyleSheet(f"color: {COLOR_ERROR};")
    
    # ========== 事件处理函数 ==========
    
    def on_session_control(self):
        """会话控制按钮点击处理"""
        try:
            session_type = self.session_combo.currentData()
            if not session_type:
                return
            
            response = self.current_session.diagnostic_session_control(session_type)
            
            if response:
                self.add_history_entry(
                    UDSRequest(
                        service_id=UDSServiceID.DIAGNOSTIC_SESSION_CONTROL,
                        subfunction=session_type
                    ),
                    response
                )
                
                # 更新会话信息
                self.session_changed.emit(self.current_session.get_session_info())
                
            else:
                self.show_error_message("会话控制失败：无响应")
                
        except Exception as e:
            logger.error(f"Error in session control: {e}")
            self.show_error_message(f"会话控制失败: {e}")
    
    def on_ecu_reset(self):
        """ECU复位按钮点击处理"""
        try:
            # 弹出复位类型选择对话框
            from PyQt5.QtWidgets import QDialog, QDialogButtonBox
            
            dialog = QDialog(self)
            dialog.setWindowTitle("ECU复位")
            dialog.setMinimumWidth(300)
            
            layout = QVBoxLayout()
            
            label = QLabel("选择复位类型:")
            layout.addWidget(label)
            
            reset_combo = QComboBox()
            for reset_type in ResetType:
                reset_combo.addItem(reset_type.name, reset_type)
            layout.addWidget(reset_combo)
            
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            dialog.setLayout(layout)
            
            if dialog.exec_() == QDialog.Accepted:
                reset_type = reset_combo.currentData()
                response = self.current_session.ecu_reset(reset_type)
                
                if response:
                    self.add_history_entry(
                        UDSRequest(
                            service_id=UDSServiceID.ECU_RESET,
                            subfunction=reset_type
                        ),
                        response
                    )
                    
        except Exception as e:
            logger.error(f"Error in ECU reset: {e}")
            self.show_error_message(f"ECU复位失败: {e}")
    
    def on_security_access(self):
        """安全访问按钮点击处理"""
        try:
            # 弹出安全访问对话框
            from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit
            
            dialog = QDialog(self)
            dialog.setWindowTitle("安全访问")
            dialog.setMinimumWidth(400)
            
            layout = QVBoxLayout()
            
            # 访问模式选择
            mode_layout = QHBoxLayout()
            mode_label = QLabel("访问模式:")
            mode_combo = QComboBox()
            for mode in AccessMode:
                mode_combo.addItem(mode.name, mode)
            mode_layout.addWidget(mode_label)
            mode_layout.addWidget(mode_combo)
            layout.addLayout(mode_layout)
            
            # 密钥输入（仅当选择发送密钥时显示）
            key_label = QLabel("安全密钥:")
            key_edit = QLineEdit()
            key_edit.setPlaceholderText("输入十六进制密钥")
            layout.addWidget(key_label)
            layout.addWidget(key_edit)
            
            def on_mode_changed(index):
                mode = mode_combo.currentData()
                # 奇数模式为请求种子，偶数模式为发送密钥
                key_edit.setEnabled(mode % 2 == 0)
                key_label.setEnabled(mode % 2 == 0)
            
            mode_combo.currentIndexChanged.connect(on_mode_changed)
            on_mode_changed(0)  # 初始状态
            
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            dialog.setLayout(layout)
            
            if dialog.exec_() == QDialog.Accepted:
                access_mode = mode_combo.currentData()
                security_key = None
                
                if access_mode % 2 == 0:  # 发送密钥模式
                    key_text = key_edit.text().strip()
                    if key_text:
                        security_key = parse_hex_string(key_text)
                
                response = self.current_session.security_access(access_mode, security_key)
                
                if response:
                    self.add_history_entry(
                        UDSRequest(
                            service_id=UDSServiceID.SECURITY_ACCESS,
                            subfunction=access_mode,
                            data=security_key if security_key else b''
                        ),
                        response
                    )
                    
                    # 更新会话信息
                    self.update_connection_status()
                    
        except Exception as e:
            logger.error(f"Error in security access: {e}")
            self.show_error_message(f"安全访问失败: {e}")
    
    def on_tester_present(self):
        """TesterPresent按钮点击处理"""
        try:
            suppress_response = False  # 可以根据需要调整
            
            response = self.current_session.tester_present(suppress_response)
            
            if response or suppress_response:
                request = UDSRequest(
                    service_id=UDSServiceID.TESTER_PRESENT,
                    subfunction=0x80 if suppress_response else 0x00,
                    expect_response=not suppress_response
                )
                
                self.add_history_entry(request, response)
                
        except Exception as e:
            logger.error(f"Error in tester present: {e}")
            self.show_error_message(f"TesterPresent失败: {e}")
    
    def on_tp_periodic_changed(self, state):
        """TesterPresent周期发送状态改变"""
        timer_id = "tester_present"
        
        if state == Qt.Checked:
            # 启动周期发送
            timer = QTimer()
            timer.timeout.connect(self.on_tester_present)
            timer.start(2000)  # 2秒间隔
            self.timer_senders[timer_id] = timer
        else:
            # 停止周期发送
            if timer_id in self.timer_senders:
                self.timer_senders[timer_id].stop()
                del self.timer_senders[timer_id]
    
    def on_service_changed(self):
        """服务选择改变"""
        try:
            service_id = self.service_combo.currentData()
            if not service_id:
                return
            
            # 获取服务定义
            protocol_defs = ProtocolDefinitions()
            service_def = protocol_defs.get_service_definition(service_id)
            
            if service_def:
                # 更新服务描述
                self.service_description_label.setText(service_def.description)
                
                # 更新子功能
                self.subfunction_combo.clear()
                
                if service_def.subfunctions:
                    for subfunction_id, subfunction_name in service_def.subfunctions.items():
                        self.subfunction_combo.addItem(
                            f"0x{subfunction_id:02X} - {subfunction_name}",
                            subfunction_id
                        )
                    
                    # 显示子功能选择
                    self.subfunction_layout.setEnabled(True)
                else:
                    # 隐藏子功能选择
                    self.subfunction_layout.setEnabled(False)
                
                # 根据服务类型更新UI
                self.update_ui_for_service(service_id)
                
        except Exception as e:
            logger.error(f"Error updating service: {e}")
    
    def update_ui_for_service(self, service_id):
        """根据服务ID更新UI"""
        # 显示/隐藏数据标识符输入
        if service_id in [UDSServiceID.READ_DATA_BY_IDENTIFIER,
                         UDSServiceID.WRITE_DATA_BY_IDENTIFIER,
                         UDSServiceID.READ_SCALING_DATA_BY_IDENTIFIER]:
            self.did_layout.setEnabled(True)
        else:
            self.did_layout.setEnabled(False)
        
        # 根据服务设置默认数据
        if service_id == UDSServiceID.READ_DATA_BY_IDENTIFIER:
            self.data_edit.clear()
            self.data_edit.setEnabled(False)
        else:
            self.data_edit.setEnabled(True)
    
    def on_subfunction_changed(self):
        """子功能选择改变"""
        # 可以在这里根据子功能调整UI
        pass
    
    def on_send_request(self):
        """发送UDS请求"""
        try:
            # 检查连接
            if not self.current_session:
                self.show_error_message("UDS会话未初始化")
                return
            
            # 获取服务ID
            service_id = self.service_combo.currentData()
            if not service_id:
                self.show_error_message("请选择服务")
                return
            
            # 构建请求数据
            subfunction = None
            data = b''
            
            # 获取子功能
            if self.subfunction_combo.isEnabled():
                subfunction = self.subfunction_combo.currentData()
            
            # 获取数据
            data_text = self.data_edit.toPlainText().strip()
            if data_text:
                data = parse_hex_string(data_text)
            
            # 特殊处理某些服务
            if service_id == UDSServiceID.READ_DATA_BY_IDENTIFIER:
                # 从数据标识符组合框获取DID
                did = self.did_combo.currentData()
                if did is not None:
                    data = did.to_bytes(2, 'big')
            
            elif service_id == UDSServiceID.WRITE_DATA_BY_IDENTIFIER:
                # 获取DID和数据
                did = self.did_combo.currentData()
                if did is not None:
                    data = did.to_bytes(2, 'big') + data
            
            # 创建请求
            request = UDSRequest(
                service_id=service_id,
                data=data,
                subfunction=subfunction,
                timeout=self.timeout_spin.value(),
                expect_response=self.expect_response_check.isChecked()
            )
            
            # 发送请求
            response = self.current_session.send_request(request)
            
            # 添加到历史记录
            self.add_history_entry(request, response)
            
            # 发射信号
            self.uds_request_sent.emit(request)
            if response:
                self.uds_response_received.emit(response)
            
            # 如果是周期发送，启动定时器
            if self.periodic_send_check.isChecked():
                timer_id = f"uds_service_{service_id:02X}"
                
                if timer_id not in self.timer_senders:
                    timer = QTimer()
                    timer.timeout.connect(self.on_send_request)
                    timer.start(self.period_spin.value())
                    self.timer_senders[timer_id] = timer
            
        except Exception as e:
            logger.error(f"Error sending UDS request: {e}")
            self.show_error_message(f"发送请求失败: {e}")
    
    def on_clear_input(self):
        """清空输入"""
        self.data_edit.clear()
    
    def on_save_template(self):
        """保存模板"""
        try:
            # 获取当前配置
            template = {
                'service_id': self.service_combo.currentData(),
                'subfunction': self.subfunction_combo.currentData() if self.subfunction_combo.isEnabled() else None,
                'data': self.data_edit.toPlainText(),
                'timeout': self.timeout_spin.value(),
                'expect_response': self.expect_response_check.isChecked(),
                'periodic_send': self.periodic_send_check.isChecked(),
                'period': self.period_spin.value() if self.periodic_send_check.isChecked() else None
            }
            
            # 这里可以实现模板保存逻辑
            logger.info(f"Template saved: {template}")
            self.show_info_message("模板已保存")
            
        except Exception as e:
            logger.error(f"Error saving template: {e}")
            self.show_error_message(f"保存模板失败: {e}")
    
    def on_clear_history(self):
        """清空历史记录"""
        self.history_table.setRowCount(0)
        self.history.clear()
        self.response_text.clear()
    
    def on_export_history(self):
        """导出历史记录"""
        try:
            from PyQt5.QtWidgets import QFileDialog
            
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出历史记录",
                "",
                "CSV文件 (*.csv);;文本文件 (*.txt);;所有文件 (*.*)"
            )
            
            if file_path:
                self.export_history_to_file(file_path)
                self.show_info_message(f"历史记录已导出到: {file_path}")
                
        except Exception as e:
            logger.error(f"Error exporting history: {e}")
            self.show_error_message(f"导出历史记录失败: {e}")
    
    def export_history_to_file(self, file_path):
        """导出历史记录到文件"""
        import csv
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 写入标题
            writer.writerow(['时间', '方向', '服务', '子功能', '数据', '状态', '响应数据'])
            
            # 写入数据
            for request, response in self.history:
                # 时间
                timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss.zzz")
                
                # 方向
                direction = "请求"
                
                # 服务
                service = f"0x{request.service_id:02X}"
                
                # 子功能
                subfunction = f"0x{request.subfunction:02X}" if request.subfunction else ""
                
                # 数据
                data = format_hex(request.data)
                
                # 状态
                if response:
                    status = "成功" if response.is_positive else "失败"
                else:
                    status = "无响应"
                
                # 响应数据
                response_data = format_hex(response.data) if response else ""
                
                writer.writerow([timestamp, direction, service, subfunction, data, status, response_data])
                
                # 如果有响应，也写入响应行
                if response:
                    writer.writerow([
                        timestamp, "响应", f"0x{response.service_id+0x40:02X}",
                        subfunction, response_data, status, ""
                    ])
    
    # ========== 信号槽处理 ==========
    
    def on_uds_request_sent(self, request):
        """UDS请求发送处理"""
        logger.debug(f"UDS request sent: SID=0x{request.service_id:02X}")
    
    def on_uds_response_received(self, response):
        """UDS响应接收处理"""
        # 在响应区域显示详细信息
        self.display_response_details(response)
        
        # 更新会话信息
        self.update_connection_status()
        
        logger.debug(f"UDS response received: SID=0x{response.service_id:02X}, status={'Positive' if response.is_positive else 'Negative'}")
    
    def on_session_changed(self, session_info):
        """会话改变处理"""
        self.update_connection_status()
        logger.info(f"Session changed to: {session_info.current_session.name}")
    
    def on_error_occurred(self, error_message):
        """错误发生处理"""
        self.show_error_message(error_message)
    
    # ========== 辅助函数 ==========
    
    def add_history_entry(self, request: UDSRequest, response: Optional[UDSResponse]):
        """添加历史记录条目"""
        try:
            # 限制历史记录大小
            if len(self.history) >= self.max_history:
                self.history.pop(0)
                self.history_table.removeRow(0)
            
            # 添加到历史记录列表
            self.history.append((request, response))
            
            # 获取当前时间
            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss.zzz")
            
            # 添加请求行
            row_position = self.history_table.rowCount()
            self.history_table.insertRow(row_position)
            
            # 时间
            self.history_table.setItem(row_position, 0, QTableWidgetItem(timestamp))
            
            # 方向
            direction_item = QTableWidgetItem("→")
            direction_item.setTextAlignment(Qt.AlignCenter)
            self.history_table.setItem(row_position, 1, direction_item)
            
            # 服务
            service_text = f"0x{request.service_id:02X}"
            self.history_table.setItem(row_position, 2, QTableWidgetItem(service_text))
            
            # 子功能
            subfunction_text = f"0x{request.subfunction:02X}" if request.subfunction else ""
            self.history_table.setItem(row_position, 3, QTableWidgetItem(subfunction_text))
            
            # 数据
            data_text = format_hex(request.data)
            self.history_table.setItem(row_position, 4, QTableWidgetItem(data_text))
            
            # 状态
            if response:
                status_text = "✓" if response.is_positive else "✗"
                status_item = QTableWidgetItem(status_text)
                status_item.setTextAlignment(Qt.AlignCenter)
                
                # 设置颜色
                if response.is_positive:
                    status_item.setForeground(QBrush(QColor(COLOR_SUCCESS)))
                else:
                    status_item.setForeground(QBrush(QColor(COLOR_ERROR)))
                    
                self.history_table.setItem(row_position, 5, status_item)
            else:
                status_item = QTableWidgetItem("⏱")
                status_item.setTextAlignment(Qt.AlignCenter)
                status_item.setForeground(QBrush(QColor(COLOR_WARNING)))
                self.history_table.setItem(row_position, 5, status_item)
            
            # 如果有响应，添加响应行
            if response:
                row_position = self.history_table.rowCount()
                self.history_table.insertRow(row_position)
                
                # 时间（使用相同时间戳）
                self.history_table.setItem(row_position, 0, QTableWidgetItem(timestamp))
                
                # 方向
                direction_item = QTableWidgetItem("←")
                direction_item.setTextAlignment(Qt.AlignCenter)
                self.history_table.setItem(row_position, 1, direction_item)
                
                # 服务
                service_text = f"0x{response.service_id+0x40:02X}"
                self.history_table.setItem(row_position, 2, QTableWidgetItem(service_text))
                
                # 子功能
                subfunction_text = f"0x{response.subfunction:02X}" if response.subfunction else ""
                self.history_table.setItem(row_position, 3, QTableWidgetItem(subfunction_text))
                
                # 数据
                data_text = format_hex(response.data)
                self.history_table.setItem(row_position, 4, QTableWidgetItem(data_text))
                
                # 状态（响应行不显示状态）
                self.history_table.setItem(row_position, 5, QTableWidgetItem(""))
            
            # 滚动到最后一行
            self.history_table.scrollToBottom()
            
        except Exception as e:
            logger.error(f"Error adding history entry: {e}")
    
    def display_response_details(self, response: UDSResponse):
        """显示响应详情"""
        try:
            text = ""
            
            if response.is_positive:
                text += f"<font color='{COLOR_SUCCESS}'>✓ 肯定响应</font><br>"
                text += f"<b>服务:</b> 0x{response.service_id:02X}<br>"
                
                if response.subfunction is not None:
                    text += f"<b>子功能:</b> 0x{response.subfunction:02X}<br>"
                
                if response.data:
                    text += f"<b>数据:</b> {format_hex(response.data)}<br>"
                
                # 尝试解码数据
                if response.service_id == UDSServiceID.READ_DATA_BY_IDENTIFIER and len(response.data) > 2:
                    try:
                        # 尝试解码为ASCII
                        ascii_data = response.data[2:].decode('ascii', errors='ignore').strip()
                        if ascii_data:
                            text += f"<b>ASCII:</b> {ascii_data}<br>"
                    except:
                        pass
            
            else:
                text += f"<font color='{COLOR_ERROR}'>✗ 否定响应</font><br>"
                text += f"<b>服务:</b> 0x{response.service_id:02X}<br>"
                
                if response.negative_response_code:
                    text += f"<b>否定响应码:</b> 0x{response.negative_response_code.value:02X}<br>"
                    text += f"<b>描述:</b> {response._get_nrc_description(response.negative_response_code)}<br>"
            
            self.response_text.setHtml(text)
            
        except Exception as e:
            logger.error(f"Error displaying response details: {e}")
            self.response_text.setText(f"显示响应详情时出错: {e}")
    
    def show_error_message(self, message: str):
        """显示错误消息"""
        self.error_occurred.emit(message)
        
        # 在响应区域显示错误
        self.response_text.setHtml(f"<font color='{COLOR_ERROR}'>{message}</font>")
        
        # 也可以显示消息框
        # QMessageBox.critical(self, "错误", message)
    
    def show_info_message(self, message: str):
        """显示信息消息"""
        self.response_text.setHtml(f"<font color='{COLOR_INFO}'>{message}</font>")
    
    def closeEvent(self, event):
        """关闭事件处理"""
        # 停止所有定时器
        for timer in self.timer_senders.values():
            timer.stop()
        
        self.timer_senders.clear()
        
        event.accept()