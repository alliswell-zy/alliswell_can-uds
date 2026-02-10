#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控界面 - 实时监控CAN总线数据
支持分离显示和多种显示格式
"""

import logging
import re
import csv
import threading
import time
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                            QGroupBox, QLabel, QComboBox, QLineEdit,
                            QPushButton, QTextEdit, QSpinBox, QCheckBox,
                            QTableWidget, QTableWidgetItem, QHeaderView,
                            QSplitter, QTabWidget, QTreeWidget, QTreeWidgetItem,
                            QListWidget, QListWidgetItem, QProgressBar,
                            QMessageBox, QScrollArea, QFrame, QFileDialog,
                            QInputDialog, QMenu, QAction, QAbstractItemView,
                            QDockWidget, QMainWindow, QApplication,
                            QStyledItemDelegate, QStyleOptionViewItem, QStyle)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QDateTime, QSize, QPoint, QEvent, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QBrush, QIcon, QPainter, QPen, QTextCursor, QSyntaxHighlighter, QTextCharFormat

from utils.helpers import create_icon, format_hex, parse_hex_string, show_message_box
from utils.constants import *
from core.monitor_manager import MonitorService, MonitorManager, MonitorFilter, MonitorDisplayConfig, MonitorDisplayFormat, MonitorFilterType
from config.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class MonitorHighlighter(QSyntaxHighlighter):
    """监控高亮器 - 根据帧ID高亮显示"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        
    def add_highlight_rule(self, pattern, color):
        """添加高亮规则"""
        format = QTextCharFormat()
        format.setForeground(color)
        self.highlighting_rules.append((pattern, format))
    
    def highlightBlock(self, text):
        """高亮文本块"""
        for pattern, format in self.highlighting_rules:
            expression = re.compile(pattern)
            for match in expression.finditer(text):
                start = match.start()
                length = match.end() - start
                self.setFormat(start, length, format)

class MonitorWidget(QWidget):
    """监控界面部件"""
    
    # 信号定义
    monitor_started = pyqtSignal()
    monitor_stopped = pyqtSignal()
    filter_changed = pyqtSignal()
    display_config_changed = pyqtSignal()
    frame_received = pyqtSignal(object)  # MonitorFrame
    error_occurred = pyqtSignal(str)     # 错误消息
    
    def __init__(self, monitor_service: MonitorService):
        """
        初始化监控界面
        
        Args:
            monitor_service: 监控服务
        """
        super().__init__()
        
        self.monitor_service = monitor_service
        self.monitor_manager = monitor_service.get_monitor_manager()
        
        # 分离窗口
        self.detached_window = None
        
        # 高亮器
        self.highlighter = None
        
        # 更新定时器
        self.update_timer = QTimer()
        
        # 自动滚动
        self.auto_scroll = True
        
        # 颜色映射
        self.color_map = {}
        
        self.setup_ui()
        self.setup_connections()
        self.setup_highlight_rules()
        self.start_update_timer()
        
        logger.info("Monitor widget initialized")
    
    def setup_ui(self):
        """设置用户界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 工具栏
        self.setup_toolbar(main_layout)
        
        # 主分割器
        main_splitter = QSplitter(Qt.Vertical)
        
        # 上半部分：监控显示区域
        display_widget = QWidget()
        display_layout = QVBoxLayout(display_widget)
        
        # 监控显示文本框
        self.setup_monitor_display(display_layout)
        
        # 下半部分：控制区域
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        
        # 显示配置
        self.setup_display_config(control_layout)
        
        # 过滤器配置
        self.setup_filter_config(control_layout)
        
        # 添加部件到分割器
        main_splitter.addWidget(display_widget)
        main_splitter.addWidget(control_widget)
        
        # 设置分割器初始比例
        main_splitter.setSizes([500, 200])
        
        main_layout.addWidget(main_splitter)
        
        # 状态栏
        self.setup_statusbar(main_layout)
    
    def setup_toolbar(self, parent_layout):
        """设置工具栏"""
        toolbar_layout = QHBoxLayout()
        
        # 监控控制按钮
        self.start_button = QPushButton("开始监控")
        self.start_button.setIcon(create_icon(ICON_PLAY))
        self.start_button.setToolTip("开始监控CAN总线")
        toolbar_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("停止监控")
        self.stop_button.setIcon(create_icon(ICON_STOP))
        self.stop_button.setToolTip("停止监控CAN总线")
        self.stop_button.setEnabled(False)
        toolbar_layout.addWidget(self.stop_button)
        
        self.clear_button = QPushButton("清空")
        self.clear_button.setIcon(create_icon(ICON_CLEAR))
        self.clear_button.setToolTip("清空监控数据")
        toolbar_layout.addWidget(self.clear_button)
        
        toolbar_layout.addSpacing(20)
        
        # 显示控制按钮
        self.pause_button = QPushButton("暂停")
        self.pause_button.setIcon(create_icon(ICON_PAUSE))
        self.pause_button.setCheckable(True)
        self.pause_button.setToolTip("暂停显示更新")
        toolbar_layout.addWidget(self.pause_button)
        
        self.auto_scroll_check = QCheckBox("自动滚动")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.setToolTip("自动滚动到最新数据")
        toolbar_layout.addWidget(self.auto_scroll_check)
        
        self.colorize_check = QCheckBox("颜色标识")
        self.colorize_check.setChecked(True)
        self.colorize_check.setToolTip("根据ID使用不同颜色标识")
        toolbar_layout.addWidget(self.colorize_check)
        
        toolbar_layout.addSpacing(20)
        
        # 导出按钮
        self.export_button = QPushButton("导出")
        self.export_button.setIcon(create_icon(ICON_EXPORT))
        self.export_button.setToolTip("导出监控数据")
        toolbar_layout.addWidget(self.export_button)
        
        self.save_button = QPushButton("保存")
        self.save_button.setIcon(create_icon(ICON_SAVE))
        self.save_button.setToolTip("保存监控数据到文件")
        toolbar_layout.addWidget(self.save_button)
        
        self.detach_button = QPushButton("分离窗口")
        self.detach_button.setIcon(create_icon("detach.png"))
        self.detach_button.setToolTip("在新窗口中显示监控")
        toolbar_layout.addWidget(self.detach_button)
        
        toolbar_layout.addStretch()
        
        parent_layout.addLayout(toolbar_layout)
    
    def setup_monitor_display(self, parent_layout):
        """设置监控显示区域"""
        display_group = QGroupBox("监控显示")
        display_layout = QVBoxLayout()
        
        # 创建监控显示文本框
        self.monitor_text = QTextEdit()
        self.monitor_text.setReadOnly(True)
        self.monitor_text.setFont(QFont("Consolas", 10))
        self.monitor_text.setLineWrapMode(QTextEdit.NoWrap)
        
        # 设置高亮器
        self.highlighter = MonitorHighlighter(self.monitor_text.document())
        
        display_layout.addWidget(self.monitor_text)
        
        # 显示控制
        control_layout = QHBoxLayout()
        
        # 显示格式选择
        format_label = QLabel("显示格式:")
        self.format_combo = QComboBox()
        for format_type in MonitorDisplayFormat:
            self.format_combo.addItem(format_type.value, format_type)
        control_layout.addWidget(format_label)
        control_layout.addWidget(self.format_combo)
        
        # 时间格式选择
        time_label = QLabel("时间格式:")
        self.time_combo = QComboBox()
        self.time_combo.addItem("绝对时间", "absolute")
        self.time_combo.addItem("相对时间", "relative")
        self.time_combo.addItem("增量时间", "delta")
        control_layout.addWidget(time_label)
        control_layout.addWidget(self.time_combo)
        
        # 最大显示行数
        max_lines_label = QLabel("最大行数:")
        self.max_lines_spin = QSpinBox()
        self.max_lines_spin.setRange(100, 100000)
        self.max_lines_spin.setValue(1000)
        self.max_lines_spin.setSuffix(" 行")
        control_layout.addWidget(max_lines_label)
        control_layout.addWidget(self.max_lines_spin)
        
        control_layout.addStretch()
        
        display_layout.addLayout(control_layout)
        
        display_group.setLayout(display_layout)
        parent_layout.addWidget(display_group)
    
    def setup_display_config(self, parent_layout):
        """设置显示配置"""
        config_group = QGroupBox("显示配置")
        config_layout = QFormLayout()
        
        # 显示选项
        self.show_timestamp_check = QCheckBox()
        self.show_timestamp_check.setChecked(True)
        config_layout.addRow("显示时间戳:", self.show_timestamp_check)
        
        self.show_id_check = QCheckBox()
        self.show_id_check.setChecked(True)
        config_layout.addRow("显示ID:", self.show_id_check)
        
        self.show_dlc_check = QCheckBox()
        self.show_dlc_check.setChecked(True)
        config_layout.addRow("显示DLC:", self.show_dlc_check)
        
        self.show_data_check = QCheckBox()
        self.show_data_check.setChecked(True)
        config_layout.addRow("显示数据:", self.show_data_check)
        
        self.show_ascii_check = QCheckBox()
        self.show_ascii_check.setChecked(False)
        config_layout.addRow("显示ASCII:", self.show_ascii_check)
        
        self.show_direction_check = QCheckBox()
        self.show_direction_check.setChecked(True)
        config_layout.addRow("显示方向:", self.show_direction_check)
        
        self.show_channel_check = QCheckBox()
        self.show_channel_check.setChecked(True)
        config_layout.addRow("显示通道:", self.show_channel_check)
        
        self.show_fd_flags_check = QCheckBox()
        self.show_fd_flags_check.setChecked(True)
        config_layout.addRow("显示FD标志:", self.show_fd_flags_check)
        
        config_group.setLayout(config_layout)
        parent_layout.addWidget(config_group)
    
    def setup_filter_config(self, parent_layout):
        """设置过滤器配置"""
        filter_group = QGroupBox("过滤器")
        filter_layout = QVBoxLayout()
        
        # 过滤器列表
        filter_list_layout = QHBoxLayout()
        
        self.filter_list = QListWidget()
        self.filter_list.setMaximumHeight(80)
        filter_list_layout.addWidget(self.filter_list)
        
        # 过滤器按钮
        filter_button_layout = QVBoxLayout()
        
        self.add_filter_button = QPushButton("添加")
        self.add_filter_button.setIcon(create_icon(ICON_ADD))
        filter_button_layout.addWidget(self.add_filter_button)
        
        self.edit_filter_button = QPushButton("编辑")
        self.edit_filter_button.setIcon(create_icon(ICON_EDIT))
        self.edit_filter_button.setEnabled(False)
        filter_button_layout.addWidget(self.edit_filter_button)
        
        self.delete_filter_button = QPushButton("删除")
        self.delete_filter_button.setIcon(create_icon(ICON_REMOVE))
        self.delete_filter_button.setEnabled(False)
        filter_button_layout.addWidget(self.delete_filter_button)
        
        filter_button_layout.addStretch()
        
        filter_list_layout.addLayout(filter_button_layout)
        filter_layout.addLayout(filter_list_layout)
        
        # 快速过滤器
        quick_filter_layout = QHBoxLayout()
        
        quick_filter_label = QLabel("快速过滤:")
        self.quick_filter_edit = QLineEdit()
        self.quick_filter_edit.setPlaceholderText("输入ID或数据模式进行过滤")
        self.quick_filter_button = QPushButton("应用")
        self.quick_filter_button.setIcon(create_icon(ICON_FILTER))
        
        quick_filter_layout.addWidget(quick_filter_label)
        quick_filter_layout.addWidget(self.quick_filter_edit)
        quick_filter_layout.addWidget(self.quick_filter_button)
        
        filter_layout.addLayout(quick_filter_layout)
        
        filter_group.setLayout(filter_layout)
        parent_layout.addWidget(filter_group)
    
    def setup_statusbar(self, parent_layout):
        """设置状态栏"""
        status_layout = QHBoxLayout()
        
        # 状态标签
        self.status_label = QLabel("监控停止")
        self.status_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        status_layout.addWidget(self.status_label)
        
        status_layout.addSpacing(20)
        
        # 帧统计
        self.frame_count_label = QLabel("帧数: 0")
        status_layout.addWidget(self.frame_count_label)
        
        self.frame_rate_label = QLabel("帧率: 0.0 fps")
        status_layout.addWidget(self.frame_rate_label)
        
        self.filtered_label = QLabel("过滤: 0%")
        status_layout.addWidget(self.filtered_label)
        
        status_layout.addStretch()
        
        # 缓冲区信息
        self.buffer_label = QLabel("缓冲区: 0/10000")
        status_layout.addWidget(self.buffer_label)
        
        # 连接状态
        self.connection_label = QLabel()
        self.update_connection_status()
        status_layout.addWidget(self.connection_label)
        
        parent_layout.addLayout(status_layout)
    
    def setup_connections(self):
        """设置信号槽连接"""
        # 工具栏按钮
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.clear_button.clicked.connect(self.clear_monitor)
        self.pause_button.toggled.connect(self.on_pause_toggled)
        self.auto_scroll_check.toggled.connect(self.on_auto_scroll_toggled)
        self.colorize_check.toggled.connect(self.on_colorize_toggled)
        self.export_button.clicked.connect(self.export_monitor_data)
        self.save_button.clicked.connect(self.save_monitor_data)
        self.detach_button.clicked.connect(self.detach_monitor)
        
        # 显示控制
        self.format_combo.currentIndexChanged.connect(self.on_display_format_changed)
        self.time_combo.currentIndexChanged.connect(self.on_time_format_changed)
        self.max_lines_spin.valueChanged.connect(self.on_max_lines_changed)
        
        # 显示配置
        self.show_timestamp_check.toggled.connect(self.on_display_config_changed)
        self.show_id_check.toggled.connect(self.on_display_config_changed)
        self.show_dlc_check.toggled.connect(self.on_display_config_changed)
        self.show_data_check.toggled.connect(self.on_display_config_changed)
        self.show_ascii_check.toggled.connect(self.on_display_config_changed)
        self.show_direction_check.toggled.connect(self.on_display_config_changed)
        self.show_channel_check.toggled.connect(self.on_display_config_changed)
        self.show_fd_flags_check.toggled.connect(self.on_display_config_changed)
        
        # 过滤器
        self.filter_list.itemSelectionChanged.connect(self.on_filter_selection_changed)
        self.add_filter_button.clicked.connect(self.add_filter)
        self.edit_filter_button.clicked.connect(self.edit_filter)
        self.delete_filter_button.clicked.connect(self.delete_filter)
        self.quick_filter_button.clicked.connect(self.apply_quick_filter)
        self.quick_filter_edit.returnPressed.connect(self.apply_quick_filter)
        
        # 监控管理器信号
        self.monitor_manager.on_frame_received = self.on_frame_received
        self.monitor_manager.on_filter_changed = self.on_filter_changed
        self.monitor_manager.on_config_changed = self.on_display_config_changed
        
        # 监控服务信号
        # 注意：我们已经将回调设置到monitor_manager
        
        # 更新定时器
        self.update_timer.timeout.connect(self.update_display)
    
    def setup_highlight_rules(self):
        """设置高亮规则"""
        if not self.highlighter:
            return
        
        # 根据ID范围设置颜色
        color_rules = [
            (r'\b(7E[0-9A-F])\b', QColor("#FF6B6B")),  # UDS诊断 - 红色
            (r'\b(7[0-9A-F][0-9A-F])\b', QColor("#4ECDC4")),  # 标准帧 - 青色
            (r'\b(0[0-9A-F][0-9A-F])\b', QColor("#FFD166")),  # 低优先级 - 黄色
            (r'\b(1[0-9A-F][0-9A-F])\b', QColor("#06D6A0")),  # 中等优先级 - 绿色
            (r'\b(RX)\b', QColor("#118AB2")),  # 接收 - 蓝色
            (r'\b(TX)\b', QColor("#EF476F")),  # 发送 - 粉色
            (r'\b(✓|成功)\b', QColor(COLOR_SUCCESS)),  # 成功
            (r'\b(✗|失败|错误)\b', QColor(COLOR_ERROR)),  # 错误
            (r'\b(警告)\b', QColor(COLOR_WARNING)),  # 警告
        ]
        
        for pattern, color in color_rules:
            self.highlighter.add_highlight_rule(pattern, color)
    
    def start_update_timer(self):
        """启动更新定时器"""
        self.update_timer.start(100)  # 100ms更新一次
    
    def stop_update_timer(self):
        """停止更新定时器"""
        self.update_timer.stop()
    
    # ========== 监控控制 ==========
    
    def start_monitoring(self):
        """开始监控"""
        try:
            # 启动监控管理器
            if self.monitor_manager.start():
                # 更新按钮状态
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(True)
                
                # 更新状态
                self.status_label.setText("监控运行中")
                self.status_label.setStyleSheet(f"color: {COLOR_SUCCESS}; font-weight: bold;")
                
                # 发射信号
                self.monitor_started.emit()
                
                self.show_status_message("监控已启动")
                logger.info("Monitoring started")
            else:
                self.show_error_message("监控启动失败")
                logger.error("Monitoring start failed")
                
        except Exception as e:
            self.show_error_message(f"监控启动失败: {e}")
            logger.error(f"Error starting monitoring: {e}")
    
    def stop_monitoring(self):
        """停止监控"""
        try:
            # 停止监控管理器
            if self.monitor_manager.stop():
                # 更新按钮状态
                self.start_button.setEnabled(True)
                self.stop_button.setEnabled(False)
                
                # 更新状态
                self.status_label.setText("监控停止")
                self.status_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
                
                # 发射信号
                self.monitor_stopped.emit()
                
                self.show_status_message("监控已停止")
                logger.info("Monitoring stopped")
            else:
                self.show_error_message("监控停止失败")
                logger.error("Monitoring stop failed")
                
        except Exception as e:
            self.show_error_message(f"监控停止失败: {e}")
            logger.error(f"Error stopping monitoring: {e}")
    
    def clear_monitor(self):
        """清空监控"""
        try:
            self.monitor_manager.clear_buffer()
            self.monitor_text.clear()
            
            self.show_status_message("监控数据已清空")
            logger.info("Monitor cleared")
            
        except Exception as e:
            self.show_error_message(f"清空监控失败: {e}")
            logger.error(f"Error clearing monitor: {e}")
    
    def on_pause_toggled(self, paused):
        """暂停/继续显示"""
        if paused:
            self.stop_update_timer()
            self.pause_button.setText("继续")
            self.pause_button.setIcon(create_icon("play.png"))
            self.show_status_message("显示已暂停")
        else:
            self.start_update_timer()
            self.pause_button.setText("暂停")
            self.pause_button.setIcon(create_icon(ICON_PAUSE))
            self.show_status_message("显示已继续")
    
    def on_auto_scroll_toggled(self, enabled):
        """自动滚动切换"""
        self.auto_scroll = enabled
        if enabled and not self.pause_button.isChecked():
            self.monitor_text.moveCursor(QTextCursor.End)
    
    def on_colorize_toggled(self, enabled):
        """颜色标识切换"""
        self.colorize_check.setChecked(enabled)
        # 重新应用高亮规则
        self.setup_highlight_rules()
    
    def export_monitor_data(self):
        """导出监控数据"""
        try:
            # 选择文件
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出监控数据",
                f"monitor_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV文件 (*.csv);;文本文件 (*.txt);;所有文件 (*.*)"
            )
            
            if not file_path:
                return
            
            # 导出数据
            success = self.monitor_manager.export_to_file(file_path)
            if success:
                self.show_status_message(f"监控数据已导出到: {file_path}")
                logger.info(f"Monitor data exported to: {file_path}")
            else:
                self.show_error_message("导出失败")
                logger.error("Monitor export failed")
                
        except Exception as e:
            self.show_error_message(f"导出失败: {e}")
            logger.error(f"Error exporting monitor data: {e}")
    
    def save_monitor_data(self):
        """保存监控数据到文件"""
        try:
            # 选择文件
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存监控数据",
                f"monitor_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
                "日志文件 (*.log);;文本文件 (*.txt);;所有文件 (*.*)"
            )
            
            if not file_path:
                return
            
            # 开始保存
            if self.monitor_manager.start_saving(file_path):
                self.save_button.setText("停止保存")
                self.save_button.setIcon(create_icon(ICON_STOP))
                self.save_button.disconnect()
                self.save_button.clicked.connect(self.stop_saving_monitor_data)
                
                self.show_status_message(f"开始保存到: {file_path}")
                logger.info(f"Started saving monitor data to: {file_path}")
            else:
                self.show_error_message("开始保存失败")
                logger.error("Start saving monitor data failed")
                
        except Exception as e:
            self.show_error_message(f"保存失败: {e}")
            logger.error(f"Error saving monitor data: {e}")
    
    def stop_saving_monitor_data(self):
        """停止保存监控数据"""
        try:
            self.monitor_manager.stop_saving()
            
            self.save_button.setText("保存")
            self.save_button.setIcon(create_icon(ICON_SAVE))
            self.save_button.disconnect()
            self.save_button.clicked.connect(self.save_monitor_data)
            
            self.show_status_message("停止保存监控数据")
            logger.info("Stopped saving monitor data")
            
        except Exception as e:
            self.show_error_message(f"停止保存失败: {e}")
            logger.error(f"Error stopping monitor data saving: {e}")
    
    def detach_monitor(self):
        """分离监控窗口"""
        try:
            if self.detached_window and self.detached_window.isVisible():
                # 如果窗口已存在，将其置前
                self.detached_window.raise_()
                self.detached_window.activateWindow()
                return
            
            # 创建分离窗口
            self.detached_window = DetachedMonitorWindow(self.monitor_service, self)
            self.detached_window.closed.connect(self.on_detached_window_closed)
            
            # 显示窗口
            self.detached_window.show()
            
            self.show_status_message("监控窗口已分离")
            logger.info("Monitor window detached")
            
        except Exception as e:
            self.show_error_message(f"分离窗口失败: {e}")
            logger.error(f"Error detaching monitor window: {e}")
    
    def on_detached_window_closed(self):
        """分离窗口关闭"""
        self.detached_window = None
        self.show_status_message("分离窗口已关闭")
    
    # ========== 显示控制 ==========
    
    def on_display_format_changed(self):
        """显示格式改变"""
        try:
            format_type = self.format_combo.currentData()
            config = self.monitor_manager.config
            config.display_format = format_type
            
            self.monitor_manager.update_config(config)
            
            self.show_status_message(f"显示格式已改为: {format_type.value}")
            
        except Exception as e:
            logger.error(f"Error changing display format: {e}")
    
    def on_time_format_changed(self):
        """时间格式改变"""
        try:
            time_format = self.time_combo.currentData()
            config = self.monitor_manager.config
            config.timestamp_format = time_format
            
            self.monitor_manager.update_config(config)
            
            self.show_status_message(f"时间格式已改为: {time_format}")
            
        except Exception as e:
            logger.error(f"Error changing time format: {e}")
    
    def on_max_lines_changed(self, value):
        """最大显示行数改变"""
        try:
            config = self.monitor_manager.config
            config.max_display_lines = value
            self.monitor_manager.update_config(config)
            
            # 如果当前行数超过最大值，截断
            self.truncate_display_lines()
            
        except Exception as e:
            logger.error(f"Error changing max lines: {e}")
    
    def on_display_config_changed(self):
        """显示配置改变"""
        try:
            config = MonitorDisplayConfig(
                display_format=self.format_combo.currentData(),
                show_timestamp=self.show_timestamp_check.isChecked(),
                show_id=self.show_id_check.isChecked(),
                show_dlc=self.show_dlc_check.isChecked(),
                show_data=self.show_data_check.isChecked(),
                show_ascii=self.show_ascii_check.isChecked(),
                show_direction=self.show_direction_check.isChecked(),
                show_channel=self.show_channel_check.isChecked(),
                show_fd_flags=self.show_fd_flags_check.isChecked(),
                colorize_by_id=self.colorize_check.isChecked(),
                auto_scroll=self.auto_scroll_check.isChecked(),
                max_display_lines=self.max_lines_spin.value(),
                timestamp_format=self.time_combo.currentData()
            )
            
            self.monitor_manager.update_config(config)
            self.display_config_changed.emit()
            
        except Exception as e:
            logger.error(f"Error updating display config: {e}")
    
    def update_display(self):
        """更新显示"""
        try:
            if self.pause_button.isChecked():
                return
            
            # 获取新的帧
            frames = self.monitor_manager.get_formatted_frames(50)  # 每次最多获取50帧
            
            if not frames:
                return
            
            # 添加到显示
            cursor = self.monitor_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            
            for frame in frames:
                cursor.insertText(frame + "\n")
            
            # 自动滚动
            if self.auto_scroll:
                self.monitor_text.moveCursor(QTextCursor.End)
            
            # 截断超出最大行数的部分
            self.truncate_display_lines()
            
            # 更新状态栏
            self.update_statusbar()
            
        except Exception as e:
            logger.error(f"Error updating display: {e}")
    
    def truncate_display_lines(self):
        """截断超出最大行数的部分"""
        try:
            max_lines = self.monitor_manager.config.max_display_lines
            document = self.monitor_text.document()
            
            if document.lineCount() > max_lines:
                cursor = QTextCursor(document)
                cursor.movePosition(QTextCursor.Start)
                cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor, document.lineCount() - max_lines)
                cursor.removeSelectedText()
                
        except Exception as e:
            logger.error(f"Error truncating display lines: {e}")
    
    # ========== 过滤器管理 ==========
    
    def on_filter_selection_changed(self):
        """过滤器选择改变"""
        selected_items = self.filter_list.selectedItems()
        self.edit_filter_button.setEnabled(len(selected_items) == 1)
        self.delete_filter_button.setEnabled(len(selected_items) > 0)
    
    def add_filter(self):
        """添加过滤器"""
        try:
            dialog = FilterDialog(self)
            if dialog.exec_() == FilterDialog.Accepted:
                filter_obj = dialog.get_filter()
                self.monitor_manager.add_filter(filter_obj)
                self.update_filter_list()
                
                self.show_status_message(f"已添加过滤器: {filter_obj.name}")
                
        except Exception as e:
            self.show_error_message(f"添加过滤器失败: {e}")
            logger.error(f"Error adding filter: {e}")
    
    def edit_filter(self):
        """编辑过滤器"""
        try:
            selected_items = self.filter_list.selectedItems()
            if not selected_items:
                return
            
            item = selected_items[0]
            filter_index = self.filter_list.row(item)
            
            filters = self.monitor_manager.get_filters()
            if 0 <= filter_index < len(filters):
                filter_obj = filters[filter_index]
                
                dialog = FilterDialog(self, filter_obj)
                if dialog.exec_() == FilterDialog.Accepted:
                    new_filter = dialog.get_filter()
                    self.monitor_manager.update_filter(filter_index, new_filter)
                    self.update_filter_list()
                    
                    self.show_status_message(f"已更新过滤器: {new_filter.name}")
                    
        except Exception as e:
            self.show_error_message(f"编辑过滤器失败: {e}")
            logger.error(f"Error editing filter: {e}")
    
    def delete_filter(self):
        """删除过滤器"""
        try:
            selected_items = self.filter_list.selectedItems()
            if not selected_items:
                return
            
            # 获取选中的索引（从大到小排序，避免删除时索引变化）
            indices = sorted([self.filter_list.row(item) for item in selected_items], reverse=True)
            
            for index in indices:
                self.monitor_manager.remove_filter(index)
            
            self.update_filter_list()
            
            self.show_status_message(f"已删除 {len(indices)} 个过滤器")
            
        except Exception as e:
            self.show_error_message(f"删除过滤器失败: {e}")
            logger.error(f"Error deleting filter: {e}")
    
    def apply_quick_filter(self):
        """应用快速过滤器"""
        try:
            pattern = self.quick_filter_edit.text().strip()
            if not pattern:
                # 清空快速过滤器
                for filter_obj in self.monitor_manager.get_filters():
                    if filter_obj.name.startswith("快速过滤"):
                        # 找到并删除快速过滤器
                        filters = self.monitor_manager.get_filters()
                        for i, f in enumerate(filters):
                            if f.name.startswith("快速过滤"):
                                self.monitor_manager.remove_filter(i)
                                break
                self.update_filter_list()
                self.show_status_message("快速过滤器已清除")
                return
            
            # 检查是否为ID或数据模式
            if re.match(r'^[0-9A-Fa-fxX\s]+$', pattern):
                # 可能是十六进制ID
                clean_pattern = pattern.replace(' ', '').replace('0x', '').replace('0X', '')
                
                if len(clean_pattern) <= 8:  # 可能是CAN ID
                    try:
                        can_id = int(clean_pattern, 16)
                        filter_obj = MonitorFilter(
                            filter_type=MonitorFilterType.ID_RANGE,
                            name=f"快速过滤: ID={pattern}",
                            enabled=True,
                            id_range_start=can_id,
                            id_range_end=can_id
                        )
                    except ValueError:
                        filter_obj = MonitorFilter(
                            filter_type=MonitorFilterType.DATA_PATTERN,
                            name=f"快速过滤: 数据={pattern}",
                            enabled=True,
                            data_pattern=pattern
                        )
                else:
                    # 数据模式
                    filter_obj = MonitorFilter(
                        filter_type=MonitorFilterType.DATA_PATTERN,
                        name=f"快速过滤: 数据={pattern}",
                        enabled=True,
                        data_pattern=pattern
                    )
            else:
                # 自定义模式
                filter_obj = MonitorFilter(
                    filter_type=MonitorFilterType.DATA_PATTERN,
                    name=f"快速过滤: 模式={pattern}",
                    enabled=True,
                    data_pattern=pattern
                )
            
            # 添加过滤器
            self.monitor_manager.add_filter(filter_obj)
            self.update_filter_list()
            
            self.show_status_message(f"已应用快速过滤器: {pattern}")
            
        except Exception as e:
            self.show_error_message(f"应用快速过滤器失败: {e}")
            logger.error(f"Error applying quick filter: {e}")
    
    def update_filter_list(self):
        """更新过滤器列表"""
        self.filter_list.clear()
        
        filters = self.monitor_manager.get_filters()
        for filter_obj in filters:
            item = QListWidgetItem(filter_obj.name)
            if not filter_obj.enabled:
                item.setForeground(QBrush(QColor(TEXT_DISABLED)))
            self.filter_list.addItem(item)
    
    def on_filter_changed(self):
        """过滤器改变"""
        self.update_filter_list()
        self.filter_changed.emit()
    
    # ========== 状态栏更新 ==========
    
    def update_statusbar(self):
        """更新状态栏"""
        try:
            stats = self.monitor_manager.get_statistics()
            
            # 更新帧统计
            self.frame_count_label.setText(f"帧数: {stats.get('total_frames', 0)}")
            self.frame_rate_label.setText(f"帧率: {stats.get('frame_rate', 0):.1f} fps")
            
            # 更新过滤统计
            filtered_rate = stats.get('filtered_rate', 0)
            self.filtered_label.setText(f"过滤: {filtered_rate:.1f}%")
            
            # 更新缓冲区信息
            buffer_size = stats.get('buffer_size', 0)
            buffer_max = 10000  # 假设最大缓冲区大小
            self.buffer_label.setText(f"缓冲区: {buffer_size}/{buffer_max}")
            
            # 更新连接状态
            self.update_connection_status()
            
        except Exception as e:
            logger.error(f"Error updating statusbar: {e}")
    
    def update_connection_status(self):
        """更新连接状态"""
        try:
            # 检查监控服务是否正在监控任何接口
            monitored_interfaces = self.monitor_service.get_monitored_interfaces()
            if monitored_interfaces:
                self.connection_label.setText(f"监控中: {', '.join(monitored_interfaces)}")
                self.connection_label.setStyleSheet(f"color: {COLOR_SUCCESS};")
            else:
                self.connection_label.setText("未监控")
                self.connection_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
                
        except Exception as e:
            logger.error(f"Error updating connection status: {e}")
    
    # ========== 回调函数 ==========
    
    def on_frame_received(self, frame):
        """帧接收回调"""
        # 发射信号
        self.frame_received.emit(frame)
        
        # 如果显示没有暂停，可以立即更新
        if not self.pause_button.isChecked():
            # 注意：这里不直接更新显示，由定时器处理
            pass
    
    # ========== 辅助函数 ==========
    
    def show_status_message(self, message: str):
        """显示状态消息"""
        self.status_label.setText(message)
        logger.info(f"Monitor status: {message}")
    
    def show_error_message(self, message: str):
        """显示错误消息"""
        self.status_label.setText(f"<font color='{COLOR_ERROR}'>{message}</font>")
        logger.error(f"Monitor error: {message}")
        
        # 发射错误信号
        self.error_occurred.emit(message)
    
    def closeEvent(self, event):
        """关闭事件处理"""
        # 停止监控
        self.stop_monitoring()
        
        # 停止保存
        if self.monitor_manager.save_enabled:
            self.stop_saving_monitor_data()
        
        # 关闭分离窗口
        if self.detached_window:
            self.detached_window.close()
        
        event.accept()


class FilterDialog(QDialog):
    """过滤器对话框"""
    
    def __init__(self, parent=None, filter_obj: MonitorFilter = None):
        """
        初始化过滤器对话框
        
        Args:
            parent: 父窗口
            filter_obj: 要编辑的过滤器对象，None表示新建
        """
        super().__init__(parent)
        
        self.filter_obj = filter_obj
        self.setup_ui()
        self.setup_connections()
        
        if filter_obj:
            self.load_filter_data()
        
        self.setWindowTitle("过滤器" + ("编辑" if filter_obj else "添加"))
    
    def setup_ui(self):
        """设置用户界面"""
        layout = QVBoxLayout(self)
        
        # 基本设置
        form_layout = QFormLayout()
        
        # 过滤器名称
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入过滤器名称")
        form_layout.addRow("名称:", self.name_edit)
        
        # 启用状态
        self.enabled_check = QCheckBox()
        self.enabled_check.setChecked(True)
        form_layout.addRow("启用:", self.enabled_check)
        
        # 过滤器类型
        self.type_combo = QComboBox()
        for filter_type in MonitorFilterType:
            self.type_combo.addItem(filter_type.value, filter_type)
        form_layout.addRow("类型:", self.type_combo)
        
        layout.addLayout(form_layout)
        
        # 参数堆栈
        self.param_stack = QStackedWidget()
        
        # ID范围参数
        self.setup_id_range_params()
        
        # ID列表参数
        self.setup_id_list_params()
        
        # 数据模式参数
        self.setup_data_pattern_params()
        
        # 自定义参数
        self.setup_custom_params()
        
        layout.addWidget(self.param_stack)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def setup_id_range_params(self):
        """设置ID范围参数"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        self.id_range_start_edit = QLineEdit()
        self.id_range_start_edit.setPlaceholderText("起始ID，如 7E0")
        layout.addRow("起始ID:", self.id_range_start_edit)
        
        self.id_range_end_edit = QLineEdit()
        self.id_range_end_edit.setPlaceholderText("结束ID，如 7EF")
        layout.addRow("结束ID:", self.id_range_end_edit)
        
        self.param_stack.addWidget(widget)
    
    def setup_id_list_params(self):
        """设置ID列表参数"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # ID列表编辑
        self.id_list_edit = QTextEdit()
        self.id_list_edit.setMaximumHeight(100)
        self.id_list_edit.setPlaceholderText("每行一个ID，如:\n7E0\n7E8\n7DF")
        layout.addWidget(QLabel("ID列表:"))
        layout.addWidget(self.id_list_edit)
        
        self.param_stack.addWidget(widget)
    
    def setup_data_pattern_params(self):
        """设置数据模式参数"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        self.data_pattern_edit = QLineEdit()
        self.data_pattern_edit.setPlaceholderText("数据模式，支持通配符*，如: 02 10 01 或 02 10 *")
        layout.addRow("数据模式:", self.data_pattern_edit)
        
        self.param_stack.addWidget(widget)
    
    def setup_custom_params(self):
        """设置自定义参数"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        info_label = QLabel("自定义过滤器需要编程实现。")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        self.param_stack.addWidget(widget)
    
    def setup_connections(self):
        """设置信号槽连接"""
        self.type_combo.currentIndexChanged.connect(self.on_filter_type_changed)
    
    def on_filter_type_changed(self, index):
        """过滤器类型改变"""
        filter_type = self.type_combo.currentData()
        
        if filter_type == MonitorFilterType.ID_RANGE:
            self.param_stack.setCurrentIndex(0)
        elif filter_type == MonitorFilterType.ID_LIST:
            self.param_stack.setCurrentIndex(1)
        elif filter_type == MonitorFilterType.DATA_PATTERN:
            self.param_stack.setCurrentIndex(2)
        elif filter_type == MonitorFilterType.CUSTOM:
            self.param_stack.setCurrentIndex(3)
    
    def load_filter_data(self):
        """加载过滤器数据"""
        if not self.filter_obj:
            return
        
        self.name_edit.setText(self.filter_obj.name)
        self.enabled_check.setChecked(self.filter_obj.enabled)
        
        index = self.type_combo.findData(self.filter_obj.filter_type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
        
        if self.filter_obj.filter_type == MonitorFilterType.ID_RANGE:
            self.id_range_start_edit.setText(hex(self.filter_obj.id_range_start))
            self.id_range_end_edit.setText(hex(self.filter_obj.id_range_end))
        elif self.filter_obj.filter_type == MonitorFilterType.ID_LIST:
            id_list_text = "\n".join(hex(id) for id in self.filter_obj.id_list)
            self.id_list_edit.setText(id_list_text)
        elif self.filter_obj.filter_type == MonitorFilterType.DATA_PATTERN:
            self.data_pattern_edit.setText(self.filter_obj.data_pattern)
    
    def get_filter(self) -> MonitorFilter:
        """获取过滤器对象"""
        filter_type = self.type_combo.currentData()
        
        filter_obj = MonitorFilter(
            filter_type=filter_type,
            name=self.name_edit.text() or "未命名过滤器",
            enabled=self.enabled_check.isChecked()
        )
        
        if filter_type == MonitorFilterType.ID_RANGE:
            # 解析起始ID和结束ID
            start_text = self.id_range_start_edit.text().strip()
            end_text = self.id_range_end_edit.text().strip()
            
            try:
                if start_text.startswith('0x'):
                    filter_obj.id_range_start = int(start_text, 16)
                else:
                    filter_obj.id_range_start = int(start_text)
                
                if end_text.startswith('0x'):
                    filter_obj.id_range_end = int(end_text, 16)
                else:
                    filter_obj.id_range_end = int(end_text)
            except ValueError:
                raise ValueError("无效的ID格式")
            
        elif filter_type == MonitorFilterType.ID_LIST:
            # 解析ID列表
            id_list_text = self.id_list_edit.toPlainText().strip()
            if id_list_text:
                id_list = []
                for line in id_list_text.split('\n'):
                    line = line.strip()
                    if line:
                        try:
                            if line.startswith('0x'):
                                id_list.append(int(line, 16))
                            else:
                                id_list.append(int(line))
                        except ValueError:
                            raise ValueError(f"无效的ID格式: {line}")
                filter_obj.id_list = id_list
            
        elif filter_type == MonitorFilterType.DATA_PATTERN:
            # 设置数据模式
            filter_obj.data_pattern = self.data_pattern_edit.text().strip()
        
        elif filter_type == MonitorFilterType.CUSTOM:
            # 自定义过滤器需要编程实现
            pass
        
        return filter_obj


class DetachedMonitorWindow(QMainWindow):
    """分离的监控窗口"""
    
    closed = pyqtSignal()
    
    def __init__(self, monitor_service: MonitorService, parent=None):
        """
        初始化分离的监控窗口
        
        Args:
            monitor_service: 监控服务
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.monitor_service = monitor_service
        
        self.setup_ui()
        self.setup_connections()
        
        self.setWindowTitle("监控窗口 - 分离显示")
        self.setGeometry(100, 100, 800, 600)
        
        logger.info("Detached monitor window initialized")
    
    def setup_ui(self):
        """设置用户界面"""
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 创建监控显示
        self.monitor_text = QTextEdit()
        self.monitor_text.setReadOnly(True)
        self.monitor_text.setFont(QFont("Consolas", 10))
        self.monitor_text.setLineWrapMode(QTextEdit.NoWrap)
        
        layout.addWidget(self.monitor_text)
        
        # 创建工具栏
        self.setup_toolbar()
        
        # 设置高亮器
        self.highlighter = MonitorHighlighter(self.monitor_text.document())
        self.setup_highlight_rules()
    
    def setup_toolbar(self):
        """设置工具栏"""
        toolbar = self.addToolBar("监控工具栏")
        
        # 清空按钮
        clear_action = QAction(create_icon(ICON_CLEAR), "清空", self)
        clear_action.triggered.connect(self.clear_display)
        toolbar.addAction(clear_action)
        
        toolbar.addSeparator()
        
        # 暂停按钮
        self.pause_action = QAction(create_icon(ICON_PAUSE), "暂停", self)
        self.pause_action.setCheckable(True)
        self.pause_action.toggled.connect(self.on_pause_toggled)
        toolbar.addAction(self.pause_action)
        
        # 自动滚动
        self.auto_scroll_action = QAction(create_icon("scroll.png"), "自动滚动", self)
        self.auto_scroll_action.setCheckable(True)
        self.auto_scroll_action.setChecked(True)
        self.auto_scroll_action.toggled.connect(self.on_auto_scroll_toggled)
        toolbar.addAction(self.auto_scroll_action)
        
        toolbar.addSeparator()
        
        # 关闭按钮
        close_action = QAction(create_icon("close.png"), "关闭", self)
        close_action.triggered.connect(self.close)
        toolbar.addAction(close_action)
        
        # 更新定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(100)  # 100ms更新一次
    
    def setup_connections(self):
        """设置信号槽连接"""
        # 监控管理器回调
        monitor_manager = self.monitor_service.get_monitor_manager()
        monitor_manager.on_frame_received = self.on_frame_received
    
    def setup_highlight_rules(self):
        """设置高亮规则"""
        if not self.highlighter:
            return
        
        # 使用与主窗口相同的高亮规则
        color_rules = [
            (r'\b(7E[0-9A-F])\b', QColor("#FF6B6B")),  # UDS诊断 - 红色
            (r'\b(7[0-9A-F][0-9A-F])\b', QColor("#4ECDC4")),  # 标准帧 - 青色
            (r'\b(0[0-9A-F][0-9A-F])\b', QColor("#FFD166")),  # 低优先级 - 黄色
            (r'\b(1[0-9A-F][0-9A-F])\b', QColor("#06D6A0")),  # 中等优先级 - 绿色
            (r'\b(RX)\b', QColor("#118AB2")),  # 接收 - 蓝色
            (r'\b(TX)\b', QColor("#EF476F")),  # 发送 - 粉色
            (r'\b(✓|成功)\b', QColor(COLOR_SUCCESS)),  # 成功
            (r'\b(✗|失败|错误)\b', QColor(COLOR_ERROR)),  # 错误
            (r'\b(警告)\b', QColor(COLOR_WARNING)),  # 警告
        ]
        
        for pattern, color in color_rules:
            self.highlighter.add_highlight_rule(pattern, color)
    
    def clear_display(self):
        """清空显示"""
        self.monitor_text.clear()
    
    def on_pause_toggled(self, paused):
        """暂停/继续显示"""
        if paused:
            self.update_timer.stop()
            self.pause_action.setText("继续")
            self.pause_action.setIcon(create_icon("play.png"))
        else:
            self.update_timer.start(100)
            self.pause_action.setText("暂停")
            self.pause_action.setIcon(create_icon(ICON_PAUSE))
    
    def on_auto_scroll_toggled(self, enabled):
        """自动滚动切换"""
        self.auto_scroll = enabled
        if enabled and not self.pause_action.isChecked():
            self.monitor_text.moveCursor(QTextCursor.End)
    
    def update_display(self):
        """更新显示"""
        try:
            if self.pause_action.isChecked():
                return
            
            # 获取新的帧
            monitor_manager = self.monitor_service.get_monitor_manager()
            frames = monitor_manager.get_formatted_frames(50)  # 每次最多获取50帧
            
            if not frames:
                return
            
            # 添加到显示
            cursor = self.monitor_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            
            for frame in frames:
                cursor.insertText(frame + "\n")
            
            # 自动滚动
            if hasattr(self, 'auto_scroll') and self.auto_scroll:
                self.monitor_text.moveCursor(QTextCursor.End)
            
        except Exception as e:
            logger.error(f"Error updating detached monitor display: {e}")
    
    def on_frame_received(self, frame):
        """帧接收回调"""
        # 如果显示没有暂停，可以立即更新
        if not self.pause_action.isChecked():
            # 注意：这里不直接更新显示，由定时器处理
            pass
    
    def closeEvent(self, event):
        """关闭事件处理"""
        # 停止定时器
        self.update_timer.stop()
        
        # 发射关闭信号
        self.closed.emit()
        
        event.accept()