#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CAN设置对话框 - 配置CAN接口参数
支持多种CAN卡接口的配置
"""

import logging
from typing import Optional, Dict, Any

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                            QGroupBox, QLabel, QComboBox, QLineEdit,
                            QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton,
                            QTabWidget, QWidget, QMessageBox, QGridLayout,
                            QListWidget, QListWidgetItem, QAbstractItemView)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIntValidator, QDoubleValidator

from config.config_manager import ConfigManager, CANInterfaceType, CANInterfaceConfig, CANMode, FrameType
from utils.helpers import create_icon, validate_can_id, validate_hex_data
from utils.constants import *

logger = logging.getLogger(__name__)

class CANSettingDialog(QDialog):
    """CAN设置对话框"""
    
    # 信号：配置已更新
    config_updated = pyqtSignal()
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        """
        初始化CAN设置对话框
        
        Args:
            config_manager: 配置管理器
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.current_config = config_manager.can_config
        
        self.setup_ui()
        self.load_config()
        self.setup_connections()
        
        logger.debug("CAN setting dialog initialized")
    
    def setup_ui(self):
        """设置用户界面"""
        self.setWindowTitle("CAN接口设置")
        self.setMinimumSize(800, 600)
        self.setWindowIcon(create_icon(ICON_SETTINGS))
        
        # 创建主布局
        main_layout = QVBoxLayout(self)
        
        # 创建选项卡部件
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 基本设置选项卡
        self.setup_basic_tab()
        
        # 高级设置选项卡
        self.setup_advanced_tab()
        
        # NI XNET特定设置选项卡
        self.setup_ni_xnet_tab()
        
        # Vector特定设置选项卡
        self.setup_vector_tab()
        
        # IXXAT特定设置选项卡
        self.setup_ixxat_tab()
        
        # SLCAN特定设置选项卡
        self.setup_slcan_tab()
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        # 测试连接按钮
        self.test_button = QPushButton("测试连接")
        self.test_button.setIcon(create_icon(ICON_CONNECT))
        button_layout.addWidget(self.test_button)
        
        button_layout.addStretch()
        
        # 确定按钮
        self.ok_button = QPushButton("确定")
        self.ok_button.setIcon(create_icon("ok.png"))
        self.ok_button.setDefault(True)
        button_layout.addWidget(self.ok_button)
        
        # 取消按钮
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setIcon(create_icon("cancel.png"))
        button_layout.addWidget(self.cancel_button)
        
        # 应用按钮
        self.apply_button = QPushButton("应用")
        self.apply_button.setIcon(create_icon("apply.png"))
        button_layout.addWidget(self.apply_button)
        
        main_layout.addLayout(button_layout)
    
    def setup_basic_tab(self):
        """设置基本设置选项卡"""
        basic_tab = QWidget()
        layout = QVBoxLayout(basic_tab)
        
        # 接口选择组
        interface_group = QGroupBox("接口选择")
        interface_layout = QFormLayout()
        
        # 接口类型
        self.interface_type_combo = QComboBox()
        for iface_type in CANInterfaceType:
            self.interface_type_combo.addItem(iface_type.value, iface_type)
        interface_layout.addRow("接口类型:", self.interface_type_combo)
        
        # 通道/端口
        self.channel_combo = QComboBox()
        self.channel_combo.setEditable(True)
        self.channel_combo.addItems(["0", "1", "2", "3", "4", "5", "6", "7"])
        interface_layout.addRow("通道:", self.channel_combo)
        
        # 刷新接口按钮
        self.refresh_button = QPushButton("刷新接口列表")
        self.refresh_button.setIcon(create_icon("refresh.png"))
        interface_layout.addRow("", self.refresh_button)
        
        interface_group.setLayout(interface_layout)
        layout.addWidget(interface_group)
        
        # CAN参数组
        can_group = QGroupBox("CAN参数")
        can_layout = QFormLayout()
        
        # CAN模式
        self.can_mode_combo = QComboBox()
        self.can_mode_combo.addItem("CAN", CANMode.CAN)
        self.can_mode_combo.addItem("CAN FD", CANMode.CAN_FD)
        can_layout.addRow("CAN模式:", self.can_mode_combo)
        
        # 帧类型
        self.frame_type_combo = QComboBox()
        self.frame_type_combo.addItem("标准帧", FrameType.STANDARD)
        self.frame_type_combo.addItem("扩展帧", FrameType.EXTENDED)
        can_layout.addRow("帧类型:", self.frame_type_combo)
        
        # 波特率
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.setEditable(True)
        for baud in CAN_STANDARD_BAUDRATES:
            self.bitrate_combo.addItem(f"{baud:,} bps", baud)
        can_layout.addRow("波特率:", self.bitrate_combo)
        
        # CAN FD数据段波特率
        self.data_bitrate_combo = QComboBox()
        self.data_bitrate_combo.setEditable(True)
        for baud in CANFD_DATA_BAUDRATES:
            self.data_bitrate_combo.addItem(f"{baud:,} bps", baud)
        can_layout.addRow("FD数据段波特率:", self.data_bitrate_combo)
        
        can_group.setLayout(can_layout)
        layout.addWidget(can_group)
        
        # 工作模式组
        mode_group = QGroupBox("工作模式")
        mode_layout = QVBoxLayout()
        
        self.listen_only_check = QCheckBox("只听模式")
        mode_layout.addWidget(self.listen_only_check)
        
        self.receive_own_check = QCheckBox("接收自己发送的帧")
        mode_layout.addWidget(self.receive_own_check)
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        layout.addStretch()
        
        self.tab_widget.addTab(basic_tab, "基本设置")
    
    def setup_advanced_tab(self):
        """设置高级设置选项卡"""
        advanced_tab = QWidget()
        layout = QVBoxLayout(advanced_tab)
        
        # 定时参数组
        timing_group = QGroupBox("定时参数")
        timing_layout = QFormLayout()
        
        # 采样点
        self.sample_point_spin = QDoubleSpinBox()
        self.sample_point_spin.setRange(0.0, 100.0)
        self.sample_point_spin.setDecimals(1)
        self.sample_point_spin.setSuffix(" %")
        timing_layout.addRow("采样点:", self.sample_point_spin)
        
        # SJW
        self.sjw_spin = QSpinBox()
        self.sjw_spin.setRange(1, 127)
        timing_layout.addRow("SJW:", self.sjw_spin)
        
        # 时钟频率
        self.fclock_spin = QSpinBox()
        self.fclock_spin.setRange(1000000, 200000000)
        self.fclock_spin.setSingleStep(1000000)
        self.fclock_spin.setSuffix(" Hz")
        timing_layout.addRow("时钟频率:", self.fclock_spin)
        
        timing_group.setLayout(timing_layout)
        layout.addWidget(timing_group)
        
        # CAN FD定时参数组
        fd_timing_group = QGroupBox("CAN FD定时参数")
        fd_timing_layout = QFormLayout()
        
        # FD SJW
        self.sjw_fd_spin = QSpinBox()
        self.sjw_fd_spin.setRange(1, 127)
        fd_timing_layout.addRow("FD SJW:", self.sjw_fd_spin)
        
        # TSEG1 FD
        self.tseg1_fd_spin = QSpinBox()
        self.tseg1_fd_spin.setRange(1, 255)
        fd_timing_layout.addRow("FD TSEG1:", self.tseg1_fd_spin)
        
        # TSEG2 FD
        self.tseg2_fd_spin = QSpinBox()
        self.tseg2_fd_spin.setRange(1, 127)
        fd_timing_layout.addRow("FD TSEG2:", self.tseg2_fd_spin)
        
        # FD采样点
        self.sample_point_fd_spin = QDoubleSpinBox()
        self.sample_point_fd_spin.setRange(0.0, 100.0)
        self.sample_point_fd_spin.setDecimals(1)
        self.sample_point_fd_spin.setSuffix(" %")
        fd_timing_layout.addRow("FD采样点:", self.sample_point_fd_spin)
        
        fd_timing_group.setLayout(fd_timing_layout)
        layout.addWidget(fd_timing_group)
        
        layout.addStretch()
        
        self.tab_widget.addTab(advanced_tab, "高级设置")
    
    def setup_ni_xnet_tab(self):
        """设置NI XNET特定设置选项卡"""
        ni_tab = QWidget()
        layout = QVBoxLayout(ni_tab)
        
        ni_group = QGroupBox("NI XNET设置")
        ni_layout = QFormLayout()
        
        # 数据库文件
        self.ni_database_edit = QLineEdit()
        self.ni_database_browse = QPushButton("浏览...")
        ni_layout.addRow("数据库文件:", self.ni_database_edit)
        ni_layout.addRow("", self.ni_database_browse)
        
        # 接口名称
        self.ni_interface_combo = QComboBox()
        self.ni_interface_combo.setEditable(True)
        self.ni_interface_combo.addItems(["CAN1", "CAN2", "CAN3", "CAN4"])
        ni_layout.addRow("接口名称:", self.ni_interface_combo)
        
        ni_group.setLayout(ni_layout)
        layout.addWidget(ni_group)
        
        layout.addStretch()
        
        self.tab_widget.addTab(ni_tab, "NI XNET")
    
    def setup_vector_tab(self):
        """设置Vector特定设置选项卡"""
        vector_tab = QWidget()
        layout = QVBoxLayout(vector_tab)
        
        vector_group = QGroupBox("Vector设置")
        vector_layout = QFormLayout()
        
        # 应用程序名称
        self.vector_app_edit = QLineEdit()
        self.vector_app_edit.setText("UDS_Tool")
        vector_layout.addRow("应用程序名:", self.vector_app_edit)
        
        # 硬件通道
        self.vector_hw_channel_spin = QSpinBox()
        self.vector_hw_channel_spin.setRange(1, 64)
        vector_layout.addRow("硬件通道:", self.vector_hw_channel_spin)
        
        vector_group.setLayout(vector_layout)
        layout.addWidget(vector_group)
        
        layout.addStretch()
        
        self.tab_widget.addTab(vector_tab, "Vector")
    
    def setup_ixxat_tab(self):
        """设置IXXAT特定设置选项卡"""
        ixxat_tab = QWidget()
        layout = QVBoxLayout(ixxat_tab)
        
        ixxat_group = QGroupBox("IXXAT设置")
        ixxat_layout = QFormLayout()
        
        # 设备ID
        self.ixxat_device_id_spin = QSpinBox()
        self.ixxat_device_id_spin.setRange(0, 255)
        ixxat_layout.addRow("设备ID:", self.ixxat_device_id_spin)
        
        ixxat_group.setLayout(ixxat_layout)
        layout.addWidget(ixxat_group)
        
        layout.addStretch()
        
        self.tab_widget.addTab(ixxat_tab, "IXXAT")
    
    def setup_slcan_tab(self):
        """设置SLCAN特定设置选项卡"""
        slcan_tab = QWidget()
        layout = QVBoxLayout(slcan_tab)
        
        slcan_group = QGroupBox("SLCAN设置")
        slcan_layout = QFormLayout()
        
        # 串口端口
        self.slcan_port_combo = QComboBox()
        self.slcan_port_combo.setEditable(True)
        # 添加常见串口
        ports = ["COM1", "COM2", "COM3", "COM4", "COM5", "COM6", 
                "/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0", "/dev/ttyACM1"]
        for port in ports:
            self.slcan_port_combo.addItem(port)
        slcan_layout.addRow("串口端口:", self.slcan_port_combo)
        
        # 波特率
        self.slcan_baudrate_combo = QComboBox()
        self.slcan_baudrate_combo.setEditable(True)
        baudrates = ["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"]
        for baud in baudrates:
            self.slcan_baudrate_combo.addItem(f"{baud} bps", int(baud))
        slcan_layout.addRow("串口波特率:", self.slcan_baudrate_combo)
        
        slcan_group.setLayout(slcan_layout)
        layout.addWidget(slcan_group)
        
        layout.addStretch()
        
        self.tab_widget.addTab(slcan_tab, "SLCAN")
    
    def load_config(self):
        """加载配置到界面"""
        try:
            # 接口类型
            index = self.interface_type_combo.findData(self.current_config.interface_type)
            if index >= 0:
                self.interface_type_combo.setCurrentIndex(index)
            
            # 通道
            self.channel_combo.setCurrentText(self.current_config.channel)
            
            # CAN模式
            mode = CANMode.CAN_FD if self.current_config.fd_enabled else CANMode.CAN
            index = self.can_mode_combo.findData(mode)
            if index >= 0:
                self.can_mode_combo.setCurrentIndex(index)
            
            # 帧类型
            index = self.frame_type_combo.findData(self.current_config.frame_type)
            if index >= 0:
                self.frame_type_combo.setCurrentIndex(index)
            
            # 波特率
            index = self.bitrate_combo.findData(self.current_config.bitrate)
            if index >= 0:
                self.bitrate_combo.setCurrentIndex(index)
            else:
                self.bitrate_combo.setCurrentText(str(self.current_config.bitrate))
            
            # FD数据段波特率
            index = self.data_bitrate_combo.findData(self.current_config.data_bitrate)
            if index >= 0:
                self.data_bitrate_combo.setCurrentIndex(index)
            else:
                self.data_bitrate_combo.setCurrentText(str(self.current_config.data_bitrate))
            
            # 工作模式
            self.listen_only_check.setChecked(self.current_config.listen_only)
            self.receive_own_check.setChecked(False)  # 默认不接收自己的帧
            
            # 定时参数
            self.sample_point_spin.setValue(self.current_config.sample_point * 100)  # 转换为百分比
            self.sjw_spin.setValue(self.current_config.sjw)
            self.fclock_spin.setValue(self.current_config.f_clock)
            
            # CAN FD定时参数
            self.sjw_fd_spin.setValue(self.current_config.sjw_fd)
            self.tseg1_fd_spin.setValue(self.current_config.tseg1_fd)
            self.tseg2_fd_spin.setValue(self.current_config.tseg2_fd)
            self.sample_point_fd_spin.setValue(self.current_config.sample_point_fd * 100)
            
            # NI XNET设置
            self.ni_database_edit.setText(self.current_config.ni_database_path)
            self.ni_interface_combo.setCurrentText(self.current_config.ni_interface_name)
            
            # Vector设置
            self.vector_app_edit.setText(self.current_config.vector_app_name)
            self.vector_hw_channel_spin.setValue(self.current_config.vector_hw_channel)
            
            # IXXAT设置
            self.ixxat_device_id_spin.setValue(self.current_config.ixxat_device_id)
            
            # SLCAN设置
            self.slcan_port_combo.setCurrentText(self.current_config.slcan_serial_port)
            index = self.slcan_baudrate_combo.findData(self.current_config.slcan_baudrate)
            if index >= 0:
                self.slcan_baudrate_combo.setCurrentIndex(index)
            else:
                self.slcan_baudrate_combo.setCurrentText(str(self.current_config.slcan_baudrate))
            
            # 根据接口类型更新界面
            self.on_interface_type_changed()
            
            logger.debug("Configuration loaded to UI")
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
    
    def save_config(self):
        """保存界面配置"""
        try:
            # 接口类型
            self.current_config.interface_type = self.interface_type_combo.currentData()
            
            # 通道
            self.current_config.channel = self.channel_combo.currentText()
            
            # CAN模式
            mode = self.can_mode_combo.currentData()
            self.current_config.fd_enabled = (mode == CANMode.CAN_FD)
            
            # 帧类型
            self.current_config.frame_type = self.frame_type_combo.currentData()
            
            # 波特率
            try:
                self.current_config.bitrate = int(self.bitrate_combo.currentText().replace(',', '').replace(' bps', ''))
            except ValueError:
                # 如果转换失败，使用当前选择的数据
                data = self.bitrate_combo.currentData()
                if data is not None:
                    self.current_config.bitrate = data
            
            # FD数据段波特率
            try:
                self.current_config.data_bitrate = int(self.data_bitrate_combo.currentText().replace(',', '').replace(' bps', ''))
            except ValueError:
                data = self.data_bitrate_combo.currentData()
                if data is not None:
                    self.current_config.data_bitrate = data
            
            # 工作模式
            self.current_config.listen_only = self.listen_only_check.isChecked()
            
            # 定时参数
            self.current_config.sample_point = self.sample_point_spin.value() / 100.0  # 转换为小数
            self.current_config.sjw = self.sjw_spin.value()
            self.current_config.f_clock = self.fclock_spin.value()
            
            # CAN FD定时参数
            self.current_config.sjw_fd = self.sjw_fd_spin.value()
            self.current_config.tseg1_fd = self.tseg1_fd_spin.value()
            self.current_config.tseg2_fd = self.tseg2_fd_spin.value()
            self.current_config.sample_point_fd = self.sample_point_fd_spin.value() / 100.0
            
            # NI XNET设置
            self.current_config.ni_database_path = self.ni_database_edit.text()
            self.current_config.ni_interface_name = self.ni_interface_combo.currentText()
            
            # Vector设置
            self.current_config.vector_app_name = self.vector_app_edit.text()
            self.current_config.vector_hw_channel = self.vector_hw_channel_spin.value()
            
            # IXXAT设置
            self.current_config.ixxat_device_id = self.ixxat_device_id_spin.value()
            
            # SLCAN设置
            self.current_config.slcan_serial_port = self.slcan_port_combo.currentText()
            try:
                self.current_config.slcan_baudrate = int(self.slcan_baudrate_combo.currentText().replace(' bps', ''))
            except ValueError:
                data = self.slcan_baudrate_combo.currentData()
                if data is not None:
                    self.current_config.slcan_baudrate = data
            
            # 保存到配置管理器
            self.config_manager.can_config = self.current_config
            self.config_manager.save_config()
            
            logger.debug("Configuration saved from UI")
            return True
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def setup_connections(self):
        """设置信号槽连接"""
        # 接口类型变化
        self.interface_type_combo.currentIndexChanged.connect(self.on_interface_type_changed)
        
        # 刷新接口列表
        self.refresh_button.clicked.connect(self.refresh_interfaces)
        
        # CAN模式变化
        self.can_mode_combo.currentIndexChanged.connect(self.on_can_mode_changed)
        
        # 按钮连接
        self.test_button.clicked.connect(self.test_connection)
        self.ok_button.clicked.connect(self.on_ok_clicked)
        self.cancel_button.clicked.connect(self.reject)
        self.apply_button.clicked.connect(self.on_apply_clicked)
        
        # NI XNET数据库浏览
        self.ni_database_browse.clicked.connect(self.browse_ni_database)
    
    def on_interface_type_changed(self):
        """接口类型变化处理"""
        interface_type = self.interface_type_combo.currentData()
        
        # 根据接口类型启用/禁用相关控件
        is_ni_xnet = (interface_type == CANInterfaceType.NI_XNET)
        is_vector = (interface_type == CANInterfaceType.VECTOR)
        is_ixxat = (interface_type == CANInterfaceType.IXXAT)
        is_slcan = (interface_type == CANInterfaceType.SLCAN)
        
        # 设置选项卡可用性
        for i in range(self.tab_widget.count()):
            tab_text = self.tab_widget.tabText(i)
            if tab_text == "NI XNET":
                self.tab_widget.setTabEnabled(i, is_ni_xnet)
            elif tab_text == "Vector":
                self.tab_widget.setTabEnabled(i, is_vector)
            elif tab_text == "IXXAT":
                self.tab_widget.setTabEnabled(i, is_ixxat)
            elif tab_text == "SLCAN":
                self.tab_widget.setTabEnabled(i, is_slcan)
    
    def on_can_mode_changed(self):
        """CAN模式变化处理"""
        mode = self.can_mode_combo.currentData()
        is_fd = (mode == CANMode.CAN_FD)
        
        # 启用/禁用FD相关控件
        self.data_bitrate_combo.setEnabled(is_fd)
        
        # 如果切换到CAN FD，确保数据段波特率有效
        if is_fd and self.data_bitrate_combo.currentText() == "":
            self.data_bitrate_combo.setCurrentIndex(2)  # 默认2 Mbps
    
    def refresh_interfaces(self):
        """刷新接口列表"""
        try:
            interfaces = self.config_manager.get_available_interfaces()
            
            # 清空通道列表
            self.channel_combo.clear()
            
            # 添加检测到的接口
            for interface, description in interfaces:
                self.channel_combo.addItem(description, interface)
            
            # 如果没有检测到接口，添加默认选项
            if self.channel_combo.count() == 0:
                self.channel_combo.addItem("未检测到接口", "0")
            
            self.show_message("接口列表已刷新", False)
            logger.info("Interface list refreshed")
            
        except Exception as e:
            self.show_message(f"刷新接口列表失败: {e}", True)
            logger.error(f"Error refreshing interface list: {e}")
    
    def browse_ni_database(self):
        """浏览NI XNET数据库文件"""
        from PyQt5.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择NI XNET数据库文件",
            "",
            "NI XNET数据库文件 (*.ncd);;所有文件 (*.*)"
        )
        
        if file_path:
            self.ni_database_edit.setText(file_path)
    
    def test_connection(self):
        """测试连接"""
        try:
            # 保存当前配置
            if not self.save_config():
                self.show_message("配置保存失败，无法测试连接", True)
                return
            
            # 获取配置
            can_config = self.config_manager.can_config
            
            # 创建接口
            from core.can_interface import CANInterfaceFactory
            interface = CANInterfaceFactory.create_interface(
                can_config.interface_type.value,
                channel=can_config.channel,
                **can_config.to_dict()
            )
            
            # 尝试连接
            if interface.connect():
                # 连接成功
                self.show_message("连接测试成功", False)
                
                # 获取接口信息
                info = interface.get_info()
                logger.info(f"Connection test successful: {info}")
                
                # 断开连接
                interface.disconnect()
            else:
                self.show_message("连接测试失败", True)
                logger.error("Connection test failed")
            
        except ImportError as e:
            self.show_message(f"缺少必要的驱动: {e}", True)
            logger.error(f"Missing driver: {e}")
        except Exception as e:
            self.show_message(f"连接测试失败: {e}", True)
            logger.error(f"Connection test error: {e}")
    
    def on_ok_clicked(self):
        """确定按钮点击处理"""
        if self.save_config():
            self.config_updated.emit()
            self.accept()
    
    def on_apply_clicked(self):
        """应用按钮点击处理"""
        if self.save_config():
            self.config_updated.emit()
            self.show_message("配置已应用", False)
    
    def show_message(self, message: str, is_error: bool = False):
        """显示消息"""
        if is_error:
            QMessageBox.critical(self, "错误", message)
        else:
            QMessageBox.information(self, "信息", message)
    
    def closeEvent(self, event):
        """关闭事件处理"""
        # 保存窗口大小和位置
        # 可以在这里添加保存窗口状态的代码
        event.accept()