#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令工程界面 - 管理命令工程和发送任务
支持CAN帧、UDS帧的发送，支持周期性发送和单次发送
"""

import logging
import json
import copy
from typing import Optional, Dict, List, Any, Tuple

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                            QGroupBox, QLabel, QComboBox, QLineEdit,
                            QPushButton, QTextEdit, QSpinBox, QCheckBox,
                            QTableWidget, QTableWidgetItem, QHeaderView,
                            QSplitter, QTabWidget, QTreeWidget, QTreeWidgetItem,
                            QListWidget, QListWidgetItem, QProgressBar,
                            QMessageBox, QScrollArea, QFrame, QFileDialog,
                            QInputDialog, QMenu, QAction, QAbstractItemView,
                            QStyledItemDelegate, QStyleOptionViewItem, QStyle)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QDateTime, QSize, QPoint, QEvent
from PyQt5.QtGui import QFont, QColor, QBrush, QIcon, QPainter, QPen

from utils.helpers import create_icon, format_hex, parse_hex_string
from utils.constants import *
from config.config_manager import ConfigManager
from core.command_project_manager import (
    CommandProjectManager, CommandProject, CommandGroup, Command,
    CommandType, SendMode, CommandStatus, CANFrameCommand, UDSCommand,
    WaitCommand, CommentCommand, ScriptCommand
)

logger = logging.getLogger(__name__)

class CommandItemDelegate(QStyledItemDelegate):
    """命令项代理，用于自定义显示"""
    
    def paint(self, painter, option, index):
        """绘制项"""
        if index.column() == 5:  # 状态列
            status = index.data(Qt.DisplayRole)
            rect = option.rect.adjusted(2, 2, -2, -2)
            
            painter.save()
            
            if status == "成功":
                painter.setBrush(QColor(COLOR_SUCCESS))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(rect.center(), 6, 6)
            elif status == "失败":
                painter.setBrush(QColor(COLOR_ERROR))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(rect.center(), 6, 6)
            elif status == "运行中":
                painter.setBrush(QColor(COLOR_WARNING))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(rect.center(), 6, 6)
            elif status == "已停止":
                painter.setBrush(QColor(COLOR_DISABLED))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(rect.center(), 6, 6)
            
            painter.restore()
        else:
            super().paint(painter, option, index)

class CommandProjectWidget(QWidget):
    """命令工程界面部件"""
    
    # 信号定义
    project_loaded = pyqtSignal(object)  # CommandProject
    project_saved = pyqtSignal(str)      # 文件路径
    command_executed = pyqtSignal(object, object)  # Command, response
    execution_started = pyqtSignal()
    execution_stopped = pyqtSignal()
    error_occurred = pyqtSignal(str)     # 错误消息
    
    def __init__(self, command_manager: CommandProjectManager, config_manager: ConfigManager):
        """
        初始化命令工程界面
        
        Args:
            command_manager: 命令工程管理器
            config_manager: 配置管理器
        """
        super().__init__()
        
        self.command_manager = command_manager
        self.config_manager = config_manager
        
        # 当前工程
        self.current_project: Optional[CommandProject] = None
        
        # 当前选中的命令
        self.selected_command: Optional[Command] = None
        
        # 编辑状态
        self.editing = False
        
        self.setup_ui()
        self.setup_connections()
        self.setup_context_menus()
        
        logger.info("Command project widget initialized")
    
    def setup_ui(self):
        """设置用户界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 工具栏
        self.setup_toolbar(main_layout)
        
        # 主分割器
        main_splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：工程树和命令列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 工程树
        self.setup_project_tree(left_layout)
        
        # 命令列表
        self.setup_command_list(left_layout)
        
        # 右侧：命令编辑区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 命令编辑区域
        self.setup_command_editor(right_layout)
        
        # 添加部件到分割器
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        
        # 设置分割器初始比例
        main_splitter.setSizes([300, 500])
        
        main_layout.addWidget(main_splitter)
        
        # 状态栏
        self.setup_statusbar(main_layout)
    
    def setup_toolbar(self, parent_layout):
        """设置工具栏"""
        toolbar_layout = QHBoxLayout()
        
        # 工程操作按钮
        self.new_project_button = QPushButton("新建工程")
        self.new_project_button.setIcon(create_icon(ICON_ADD))
        toolbar_layout.addWidget(self.new_project_button)
        
        self.open_project_button = QPushButton("打开工程")
        self.open_project_button.setIcon(create_icon(ICON_LOAD))
        toolbar_layout.addWidget(self.open_project_button)
        
        self.save_project_button = QPushButton("保存工程")
        self.save_project_button.setIcon(create_icon(ICON_SAVE))
        self.save_project_button.setEnabled(False)
        toolbar_layout.addWidget(self.save_project_button)
        
        self.save_as_project_button = QPushButton("另存为")
        self.save_as_project_button.setIcon(create_icon("save_as.png"))
        self.save_as_project_button.setEnabled(False)
        toolbar_layout.addWidget(self.save_as_project_button)
        
        toolbar_layout.addSpacing(20)
        
        # 工程执行按钮
        self.execute_project_button = QPushButton("执行工程")
        self.execute_project_button.setIcon(create_icon(ICON_PLAY))
        self.execute_project_button.setEnabled(False)
        toolbar_layout.addWidget(self.execute_project_button)
        
        self.stop_execution_button = QPushButton("停止执行")
        self.stop_execution_button.setIcon(create_icon(ICON_STOP))
        self.stop_execution_button.setEnabled(False)
        toolbar_layout.addWidget(self.stop_execution_button)
        
        self.execute_single_button = QPushButton("执行选中")
        self.execute_single_button.setIcon(create_icon("play_one.png"))
        self.execute_single_button.setEnabled(False)
        toolbar_layout.addWidget(self.execute_single_button)
        
        toolbar_layout.addSpacing(20)
        
        # 工程管理按钮
        self.add_group_button = QPushButton("添加组")
        self.add_group_button.setIcon(create_icon(ICON_ADD))
        self.add_group_button.setEnabled(False)
        toolbar_layout.addWidget(self.add_group_button)
        
        self.add_command_button = QPushButton("添加命令")
        self.add_command_button.setIcon(create_icon(ICON_ADD))
        self.add_command_button.setEnabled(False)
        toolbar_layout.addWidget(self.add_command_button)
        
        self.delete_item_button = QPushButton("删除")
        self.delete_item_button.setIcon(create_icon(ICON_REMOVE))
        self.delete_item_button.setEnabled(False)
        toolbar_layout.addWidget(self.delete_item_button)
        
        toolbar_layout.addStretch()
        
        parent_layout.addLayout(toolbar_layout)
    
    def setup_project_tree(self, parent_layout):
        """设置工程树"""
        tree_group = QGroupBox("工程结构")
        tree_layout = QVBoxLayout()
        
        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderLabels(["名称", "类型", "状态", "ID"])
        self.project_tree.setColumnWidth(0, 150)
        self.project_tree.setColumnWidth(1, 80)
        self.project_tree.setColumnWidth(2, 80)
        self.project_tree.setColumnWidth(3, 100)
        
        tree_layout.addWidget(self.project_tree)
        
        tree_group.setLayout(tree_layout)
        parent_layout.addWidget(tree_group)
    
    def setup_command_list(self, parent_layout):
        """设置命令列表"""
        list_group = QGroupBox("命令列表")
        list_layout = QVBoxLayout()
        
        self.command_list = QListWidget()
        self.command_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        list_layout.addWidget(self.command_list)
        
        list_group.setLayout(list_layout)
        parent_layout.addWidget(list_group)
    
    def setup_command_editor(self, parent_layout):
        """设置命令编辑器"""
        editor_group = QGroupBox("命令编辑")
        editor_layout = QVBoxLayout()
        
        # 使用滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        editor_widget = QWidget()
        editor_widget_layout = QVBoxLayout(editor_widget)
        
        # 基本参数
        self.setup_basic_parameters(editor_widget_layout)
        
        # 命令参数（根据命令类型动态显示）
        self.command_params_stack = QTabWidget()
        self.setup_can_frame_params()
        self.setup_uds_command_params()
        self.setup_wait_command_params()
        self.setup_comment_command_params()
        self.setup_script_command_params()
        
        editor_widget_layout.addWidget(self.command_params_stack)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.save_command_button = QPushButton("保存命令")
        self.save_command_button.setIcon(create_icon(ICON_SAVE))
        self.save_command_button.setEnabled(False)
        button_layout.addWidget(self.save_command_button)
        
        self.cancel_edit_button = QPushButton("取消编辑")
        self.cancel_edit_button.setIcon(create_icon("cancel.png"))
        self.cancel_edit_button.setEnabled(False)
        button_layout.addWidget(self.cancel_edit_button)
        
        button_layout.addStretch()
        
        editor_widget_layout.addLayout(button_layout)
        
        scroll_area.setWidget(editor_widget)
        editor_layout.addWidget(scroll_area)
        
        editor_group.setLayout(editor_layout)
        parent_layout.addWidget(editor_group)
    
    def setup_basic_parameters(self, parent_layout):
        """设置基本参数"""
        form_layout = QFormLayout()
        
        # 命令名称
        self.command_name_edit = QLineEdit()
        self.command_name_edit.setPlaceholderText("输入命令名称")
        form_layout.addRow("名称:", self.command_name_edit)
        
        # 命令类型
        self.command_type_combo = QComboBox()
        for command_type in CommandType:
            self.command_type_combo.addItem(command_type.value, command_type)
        form_layout.addRow("类型:", self.command_type_combo)
        
        # 发送模式
        self.send_mode_combo = QComboBox()
        for send_mode in SendMode:
            self.send_mode_combo.addItem(send_mode.value, send_mode)
        form_layout.addRow("发送模式:", self.send_mode_combo)
        
        # 发送周期（仅周期性发送时启用）
        self.period_spin = QSpinBox()
        self.period_spin.setRange(10, 60000)
        self.period_spin.setValue(1000)
        self.period_spin.setSuffix(" ms")
        form_layout.addRow("发送周期:", self.period_spin)
        
        # 启用状态
        self.enabled_check = QCheckBox()
        self.enabled_check.setChecked(True)
        form_layout.addRow("启用:", self.enabled_check)
        
        parent_layout.addLayout(form_layout)
    
    def setup_can_frame_params(self):
        """设置CAN帧参数"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # CAN ID
        self.can_id_edit = QLineEdit()
        self.can_id_edit.setPlaceholderText("十六进制，如 7E0")
        layout.addRow("CAN ID:", self.can_id_edit)
        
        # 扩展帧
        self.can_extended_check = QCheckBox()
        layout.addRow("扩展帧:", self.can_extended_check)
        
        # CAN FD
        self.can_fd_check = QCheckBox()
        layout.addRow("CAN FD:", self.can_fd_check)
        
        # 数据
        self.can_data_edit = QTextEdit()
        self.can_data_edit.setMaximumHeight(80)
        self.can_data_edit.setPlaceholderText("十六进制数据，用空格分隔")
        layout.addRow("数据:", self.can_data_edit)
        
        # DLC
        self.can_dlc_spin = QSpinBox()
        self.can_dlc_spin.setRange(0, 64)
        self.can_dlc_spin.setValue(8)
        layout.addRow("DLC:", self.can_dlc_spin)
        
        # 注释
        self.can_comment_edit = QLineEdit()
        self.can_comment_edit.setPlaceholderText("输入注释")
        layout.addRow("注释:", self.can_comment_edit)
        
        self.command_params_stack.addTab(widget, "CAN帧")
    
    def setup_uds_command_params(self):
        """设置UDS命令参数"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # 服务ID
        self.uds_service_edit = QLineEdit()
        self.uds_service_edit.setPlaceholderText("十六进制，如 10")
        layout.addRow("服务ID:", self.uds_service_edit)
        
        # 子功能
        self.uds_subfunction_edit = QLineEdit()
        self.uds_subfunction_edit.setPlaceholderText("十六进制，如 01")
        layout.addRow("子功能:", self.uds_subfunction_edit)
        
        # 数据
        self.uds_data_edit = QTextEdit()
        self.uds_data_edit.setMaximumHeight(80)
        self.uds_data_edit.setPlaceholderText("十六进制数据，用空格分隔")
        layout.addRow("数据:", self.uds_data_edit)
        
        # 超时时间
        self.uds_timeout_spin = QSpinBox()
        self.uds_timeout_spin.setRange(100, 60000)
        self.uds_timeout_spin.setValue(2000)
        self.uds_timeout_spin.setSuffix(" ms")
        layout.addRow("超时时间:", self.uds_timeout_spin)
        
        # 期望响应
        self.uds_expect_response_check = QCheckBox()
        self.uds_expect_response_check.setChecked(True)
        layout.addRow("期望响应:", self.uds_expect_response_check)
        
        # 注释
        self.uds_comment_edit = QLineEdit()
        self.uds_comment_edit.setPlaceholderText("输入注释")
        layout.addRow("注释:", self.uds_comment_edit)
        
        self.command_params_stack.addTab(widget, "UDS命令")
    
    def setup_wait_command_params(self):
        """设置等待命令参数"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # 等待时间
        self.wait_duration_spin = QSpinBox()
        self.wait_duration_spin.setRange(1, 60000)
        self.wait_duration_spin.setValue(1000)
        self.wait_duration_spin.setSuffix(" ms")
        layout.addRow("等待时间:", self.wait_duration_spin)
        
        # 注释
        self.wait_comment_edit = QLineEdit()
        self.wait_comment_edit.setPlaceholderText("输入注释")
        layout.addRow("注释:", self.wait_comment_edit)
        
        self.command_params_stack.addTab(widget, "等待")
    
    def setup_comment_command_params(self):
        """设置注释命令参数"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # 注释
        self.comment_text_edit = QTextEdit()
        self.comment_text_edit.setMaximumHeight(100)
        self.comment_text_edit.setPlaceholderText("输入注释")
        layout.addRow("注释:", self.comment_text_edit)
        
        self.command_params_stack.addTab(widget, "注释")
    
    def setup_script_command_params(self):
        """设置脚本命令参数"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # 脚本代码
        self.script_code_edit = QTextEdit()
        self.script_code_edit.setMaximumHeight(200)
        self.script_code_edit.setPlaceholderText("输入Python脚本代码")
        layout.addRow("脚本代码:", self.script_code_edit)
        
        # 注释
        self.script_comment_edit = QLineEdit()
        self.script_comment_edit.setPlaceholderText("输入注释")
        layout.addRow("注释:", self.script_comment_edit)
        
        self.command_params_stack.addTab(widget, "脚本")
    
    def setup_statusbar(self, parent_layout):
        """设置状态栏"""
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        # 执行进度
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedWidth(200)
        status_layout.addWidget(self.progress_bar)
        
        # 执行状态
        self.execution_status_label = QLabel()
        self.execution_status_label.setVisible(False)
        status_layout.addWidget(self.execution_status_label)
        
        parent_layout.addLayout(status_layout)
    
    def setup_connections(self):
        """设置信号槽连接"""
        # 工具栏按钮
        self.new_project_button.clicked.connect(self.new_project)
        self.open_project_button.clicked.connect(self.open_project)
        self.save_project_button.clicked.connect(self.save_project)
        self.save_as_project_button.clicked.connect(self.save_project_as)
        self.execute_project_button.clicked.connect(self.execute_project)
        self.stop_execution_button.clicked.connect(self.stop_execution)
        self.execute_single_button.clicked.connect(self.execute_selected)
        self.add_group_button.clicked.connect(self.add_group)
        self.add_command_button.clicked.connect(self.add_command)
        self.delete_item_button.clicked.connect(self.delete_item)
        
        # 工程树
        self.project_tree.itemSelectionChanged.connect(self.on_project_tree_selection_changed)
        
        # 命令列表
        self.command_list.itemSelectionChanged.connect(self.on_command_list_selection_changed)
        
        # 命令类型变化
        self.command_type_combo.currentIndexChanged.connect(self.on_command_type_changed)
        
        # 发送模式变化
        self.send_mode_combo.currentIndexChanged.connect(self.on_send_mode_changed)
        
        # 命令编辑器按钮
        self.save_command_button.clicked.connect(self.save_current_command)
        self.cancel_edit_button.clicked.connect(self.cancel_edit)
        
        # 命令工程管理器信号
        self.command_manager.executor.on_command_started.connect(self.on_command_started)
        self.command_manager.executor.on_command_completed.connect(self.on_command_completed)
        self.command_manager.executor.on_command_failed.connect(self.on_command_failed)
        self.command_manager.executor.on_group_started.connect(self.on_group_started)
        self.command_manager.executor.on_group_completed.connect(self.on_group_completed)
        self.command_manager.executor.on_project_started.connect(self.on_project_started)
        self.command_manager.executor.on_project_completed.connect(self.on_project_completed)
    
    def setup_context_menus(self):
        """设置上下文菜单"""
        # 工程树上下文菜单
        self.project_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.project_tree.customContextMenuRequested.connect(self.show_project_tree_context_menu)
        
        # 命令列表上下文菜单
        self.command_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.command_list.customContextMenuRequested.connect(self.show_command_list_context_menu)
    
    def show_project_tree_context_menu(self, position: QPoint):
        """显示工程树上下文菜单"""
        item = self.project_tree.itemAt(position)
        if not item:
            return
        
        menu = QMenu()
        
        if item.data(0, Qt.UserRole) == "project":
            # 工程级菜单
            menu.addAction("添加组", self.add_group)
            menu.addAction("导入组", self.import_group)
            menu.addSeparator()
            menu.addAction("工程属性", self.show_project_properties)
        elif item.data(0, Qt.UserRole) == "group":
            # 组级菜单
            menu.addAction("添加命令", self.add_command)
            menu.addAction("复制组", self.copy_group)
            menu.addAction("重命名组", self.rename_group)
            menu.addSeparator()
            menu.addAction("组属性", self.show_group_properties)
        elif item.data(0, Qt.UserRole) == "command":
            # 命令级菜单
            menu.addAction("编辑命令", self.edit_selected_command)
            menu.addAction("复制命令", self.copy_command)
            menu.addAction("启用/禁用", self.toggle_command_enabled)
            menu.addSeparator()
            menu.addAction("上移", self.move_command_up)
            menu.addAction("下移", self.move_command_down)
        
        menu.exec_(self.project_tree.viewport().mapToGlobal(position))
    
    def show_command_list_context_menu(self, position: QPoint):
        """显示命令列表上下文菜单"""
        items = self.command_list.selectedItems()
        if not items:
            return
        
        menu = QMenu()
        
        menu.addAction("执行选中命令", self.execute_selected)
        menu.addSeparator()
        menu.addAction("编辑命令", self.edit_selected_command)
        menu.addAction("复制命令", self.copy_command)
        menu.addAction("启用/禁用", self.toggle_command_enabled)
        menu.addSeparator()
        menu.addAction("删除命令", self.delete_item)
        
        menu.exec_(self.command_list.viewport().mapToGlobal(position))
    
    # ========== 工程管理 ==========
    
    def new_project(self):
        """新建工程"""
        try:
            # 提示保存当前工程
            if self.current_project:
                reply = QMessageBox.question(
                    self,
                    "新建工程",
                    "是否保存当前工程？",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                )
                
                if reply == QMessageBox.Cancel:
                    return
                elif reply == QMessageBox.Yes:
                    if not self.save_project():
                        return
            
            # 获取工程名称
            name, ok = QInputDialog.getText(
                self,
                "新建工程",
                "请输入工程名称:",
                QLineEdit.Normal,
                "新工程"
            )
            
            if not ok or not name:
                return
            
            # 创建新工程
            import uuid
            project_id = str(uuid.uuid4())[:8]
            
            self.current_project = self.command_manager.create_project(
                project_id, name, "新建的工程"
            )
            
            if not self.current_project:
                raise Exception("创建工程失败")
            
            # 更新UI
            self.update_project_tree()
            self.update_ui_state()
            
            self.save_project_button.setEnabled(True)
            self.save_as_project_button.setEnabled(True)
            self.execute_project_button.setEnabled(True)
            
            self.show_status_message(f"已创建新工程: {name}")
            self.project_loaded.emit(self.current_project)
            
        except Exception as e:
            logger.error(f"Error creating new project: {e}")
            self.show_error_message(f"创建工程失败: {e}")
    
    def open_project(self):
        """打开工程"""
        try:
            # 提示保存当前工程
            if self.current_project:
                reply = QMessageBox.question(
                    self,
                    "打开工程",
                    "是否保存当前工程？",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                )
                
                if reply == QMessageBox.Cancel:
                    return
                elif reply == QMessageBox.Yes:
                    if not self.save_project():
                        return
            
            # 选择文件
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "打开工程文件",
                "",
                "UDS工程文件 (*.udsp);;JSON文件 (*.json);;所有文件 (*.*)"
            )
            
            if not file_path:
                return
            
            # 加载工程
            project = self.command_manager.load_project(file_path)
            if not project:
                raise Exception("加载工程失败")
            
            self.current_project = project
            
            # 更新UI
            self.update_project_tree()
            self.update_ui_state()
            
            self.save_project_button.setEnabled(True)
            self.save_as_project_button.setEnabled(True)
            self.execute_project_button.setEnabled(True)
            
            self.show_status_message(f"已打开工程: {project.name}")
            self.project_loaded.emit(self.current_project)
            
        except Exception as e:
            logger.error(f"Error opening project: {e}")
            self.show_error_message(f"打开工程失败: {e}")
    
    def save_project(self):
        """保存工程"""
        try:
            if not self.current_project:
                self.show_error_message("没有打开的工程")
                return False
            
            # 如果有文件路径，直接保存
            if hasattr(self.current_project, 'file_path') and self.current_project.file_path:
                file_path = self.current_project.file_path
            else:
                # 选择文件
                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "保存工程文件",
                    f"{self.current_project.name}.udsp",
                    "UDS工程文件 (*.udsp);;JSON文件 (*.json);;所有文件 (*.*)"
                )
                
                if not file_path:
                    return False
            
            # 保存工程
            success = self.command_manager.save_project(self.current_project.id, file_path)
            if not success:
                raise Exception("保存工程失败")
            
            # 更新文件路径
            self.current_project.file_path = file_path
            
            self.show_status_message(f"工程已保存: {file_path}")
            self.project_saved.emit(file_path)
            return True
            
        except Exception as e:
            logger.error(f"Error saving project: {e}")
            self.show_error_message(f"保存工程失败: {e}")
            return False
    
    def save_project_as(self):
        """工程另存为"""
        try:
            if not self.current_project:
                self.show_error_message("没有打开的工程")
                return
            
            # 选择文件
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "工程另存为",
                f"{self.current_project.name}.udsp",
                "UDS工程文件 (*.udsp);;JSON文件 (*.json);;所有文件 (*.*)"
            )
            
            if not file_path:
                return
            
            # 保存工程
            success = self.command_manager.save_project(self.current_project.id, file_path)
            if not success:
                raise Exception("保存工程失败")
            
            # 更新文件路径
            self.current_project.file_path = file_path
            
            self.show_status_message(f"工程已另存为: {file_path}")
            self.project_saved.emit(file_path)
            
        except Exception as e:
            logger.error(f"Error saving project as: {e}")
            self.show_error_message(f"工程另存为失败: {e}")
    
    def import_group(self):
        """导入组"""
        try:
            if not self.current_project:
                self.show_error_message("没有打开的工程")
                return
            
            # 选择文件
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "导入组",
                "",
                "JSON文件 (*.json);;所有文件 (*.*)"
            )
            
            if not file_path:
                return
            
            # 加载组数据
            with open(file_path, 'r', encoding='utf-8') as f:
                group_data = json.load(f)
            
            # 创建组
            import uuid
            group_id = str(uuid.uuid4())[:8]
            
            group = CommandGroup.from_dict({
                'id': group_id,
                'name': group_data.get('name', '导入的组'),
                'description': group_data.get('description', ''),
                'enabled': group_data.get('enabled', True),
                'commands': []
            })
            
            # 添加命令
            for cmd_data in group_data.get('commands', []):
                command = Command.from_dict(cmd_data)
                group.add_command(command)
            
            # 添加到工程
            self.current_project.add_group(group)
            
            # 更新UI
            self.update_project_tree()
            self.show_status_message(f"已导入组: {group.name}")
            
        except Exception as e:
            logger.error(f"Error importing group: {e}")
            self.show_error_message(f"导入组失败: {e}")
    
    def show_project_properties(self):
        """显示工程属性"""
        if not self.current_project:
            return
        
        from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit
        
        dialog = QDialog(self)
        dialog.setWindowTitle("工程属性")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        # 工程名称
        name_edit = QLineEdit(self.current_project.name)
        form_layout.addRow("名称:", name_edit)
        
        # 工程描述
        desc_edit = QTextEdit(self.current_project.description)
        desc_edit.setMaximumHeight(100)
        form_layout.addRow("描述:", desc_edit)
        
        # 版本
        version_edit = QLineEdit(self.current_project.version)
        form_layout.addRow("版本:", version_edit)
        
        layout.addLayout(form_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() == QDialog.Accepted:
            # 更新工程信息
            self.current_project.name = name_edit.text()
            self.current_project.description = desc_edit.toPlainText()
            self.current_project.version = version_edit.text()
            self.current_project.updated_at = time.time()
            
            # 更新UI
            self.update_project_tree()
            self.show_status_message("工程属性已更新")
    
    def show_group_properties(self):
        """显示组属性"""
        # 获取选中的组
        selected_items = self.project_tree.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        if item.data(0, Qt.UserRole) != "group":
            return
        
        group_id = item.data(0, Qt.UserRole + 1)
        group = self.current_project.get_group(group_id)
        if not group:
            return
        
        from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit, QSpinBox, QCheckBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("组属性")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        # 组名称
        name_edit = QLineEdit(group.name)
        form_layout.addRow("名称:", name_edit)
        
        # 组描述
        desc_edit = QTextEdit(group.description)
        desc_edit.setMaximumHeight(100)
        form_layout.addRow("描述:", desc_edit)
        
        # 启用状态
        enabled_check = QCheckBox()
        enabled_check.setChecked(group.enabled)
        form_layout.addRow("启用:", enabled_check)
        
        # 重复次数
        repeat_spin = QSpinBox()
        repeat_spin.setRange(0, 9999)
        repeat_spin.setSpecialValueText("无限")
        repeat_spin.setValue(group.repeat_count)
        form_layout.addRow("重复次数:", repeat_spin)
        
        # 重复间隔
        interval_spin = QSpinBox()
        interval_spin.setRange(0, 60000)
        interval_spin.setValue(group.repeat_interval)
        interval_spin.setSuffix(" ms")
        form_layout.addRow("重复间隔:", interval_spin)
        
        # 顺序执行
        sequence_check = QCheckBox()
        sequence_check.setChecked(group.run_in_sequence)
        form_layout.addRow("顺序执行:", sequence_check)
        
        layout.addLayout(form_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() == QDialog.Accepted:
            # 更新组信息
            group.name = name_edit.text()
            group.description = desc_edit.toPlainText()
            group.enabled = enabled_check.isChecked()
            group.repeat_count = repeat_spin.value()
            group.repeat_interval = interval_spin.value()
            group.run_in_sequence = sequence_check.isChecked()
            
            # 更新UI
            self.update_project_tree()
            self.show_status_message("组属性已更新")
    
    # ========== 组管理 ==========
    
    def add_group(self):
        """添加组"""
        try:
            if not self.current_project:
                self.show_error_message("没有打开的工程")
                return
            
            # 获取组名称
            name, ok = QInputDialog.getText(
                self,
                "添加组",
                "请输入组名称:",
                QLineEdit.Normal,
                "新组"
            )
            
            if not ok or not name:
                return
            
            # 创建组
            import uuid
            group_id = str(uuid.uuid4())[:8]
            
            group = CommandGroup(
                id=group_id,
                name=name,
                description="新建的组"
            )
            
            # 添加到工程
            self.current_project.add_group(group)
            
            # 更新UI
            self.update_project_tree()
            self.show_status_message(f"已添加组: {name}")
            
        except Exception as e:
            logger.error(f"Error adding group: {e}")
            self.show_error_message(f"添加组失败: {e}")
    
    def copy_group(self):
        """复制组"""
        try:
            # 获取选中的组
            selected_items = self.project_tree.selectedItems()
            if not selected_items:
                return
            
            item = selected_items[0]
            if item.data(0, Qt.UserRole) != "group":
                return
            
            group_id = item.data(0, Qt.UserRole + 1)
            group = self.current_project.get_group(group_id)
            if not group:
                return
            
            # 创建组副本
            import uuid
            new_group_id = str(uuid.uuid4())[:8]
            
            # 深拷贝组
            new_group = copy.deepcopy(group)
            new_group.id = new_group_id
            new_group.name = f"{group.name} - 副本"
            
            # 重新生成命令ID
            for command in new_group.commands:
                command.id = str(uuid.uuid4())[:8]
            
            # 添加到工程
            self.current_project.add_group(new_group)
            
            # 更新UI
            self.update_project_tree()
            self.show_status_message(f"已复制组: {group.name}")
            
        except Exception as e:
            logger.error(f"Error copying group: {e}")
            self.show_error_message(f"复制组失败: {e}")
    
    def rename_group(self):
        """重命名组"""
        try:
            # 获取选中的组
            selected_items = self.project_tree.selectedItems()
            if not selected_items:
                return
            
            item = selected_items[0]
            if item.data(0, Qt.UserRole) != "group":
                return
            
            group_id = item.data(0, Qt.UserRole + 1)
            group = self.current_project.get_group(group_id)
            if not group:
                return
            
            # 获取新名称
            name, ok = QInputDialog.getText(
                self,
                "重命名组",
                "请输入新名称:",
                QLineEdit.Normal,
                group.name
            )
            
            if not ok or not name:
                return
            
            # 更新组名称
            group.name = name
            
            # 更新UI
            self.update_project_tree()
            self.show_status_message(f"组已重命名为: {name}")
            
        except Exception as e:
            logger.error(f"Error renaming group: {e}")
            self.show_error_message(f"重命名组失败: {e}")
    
    # ========== 命令管理 ==========
    
    def add_command(self):
        """添加命令"""
        try:
            # 确定要添加到哪个组
            group_id = None
            selected_items = self.project_tree.selectedItems()
            
            if selected_items:
                item = selected_items[0]
                if item.data(0, Qt.UserRole) == "group":
                    group_id = item.data(0, Qt.UserRole + 1)
                elif item.data(0, Qt.UserRole) == "project":
                    # 如果没有选中的组，使用第一个组
                    if self.current_project and self.current_project.groups:
                        group_id = self.current_project.groups[0].id
                    else:
                        # 如果没有组，先创建一个
                        self.add_group()
                        return
            else:
                if self.current_project and self.current_project.groups:
                    group_id = self.current_project.groups[0].id
                else:
                    self.add_group()
                    return
            
            if not group_id:
                self.show_error_message("无法确定要添加到的组")
                return
            
            # 创建新命令
            import uuid
            command_id = str(uuid.uuid4())[:8]
            
            command = Command(
                id=command_id,
                name="新命令",
                command_type=CommandType.CAN_FRAME,
                send_mode=SendMode.SINGLE
            )
            
            # 添加到组
            group = self.current_project.get_group(group_id)
            if group:
                group.add_command(command)
                
                # 更新UI
                self.update_project_tree()
                self.update_command_list(group_id)
                
                # 选中新命令
                for i in range(self.command_list.count()):
                    item = self.command_list.item(i)
                    if item.data(Qt.UserRole) == command_id:
                        self.command_list.setCurrentItem(item)
                        break
                
                # 进入编辑模式
                self.edit_selected_command()
                
                self.show_status_message("已添加新命令")
            
        except Exception as e:
            logger.error(f"Error adding command: {e}")
            self.show_error_message(f"添加命令失败: {e}")
    
    def edit_selected_command(self):
        """编辑选中的命令"""
        try:
            # 获取选中的命令
            selected_items = self.command_list.selectedItems()
            if not selected_items:
                return
            
            item = selected_items[0]
            command_id = item.data(Qt.UserRole)
            
            # 查找命令
            command = None
            group_id = None
            
            for group in self.current_project.groups:
                for cmd in group.commands:
                    if cmd.id == command_id:
                        command = cmd
                        group_id = group.id
                        break
                if command:
                    break
            
            if not command:
                return
            
            # 保存当前选中的组ID
            self.editing_group_id = group_id
            self.editing_command_id = command_id
            
            # 加载命令数据到编辑器
            self.load_command_to_editor(command)
            
            # 进入编辑模式
            self.editing = True
            self.update_editor_state(True)
            
            self.show_status_message(f"编辑命令: {command.name}")
            
        except Exception as e:
            logger.error(f"Error editing command: {e}")
            self.show_error_message(f"编辑命令失败: {e}")
    
    def load_command_to_editor(self, command: Command):
        """加载命令数据到编辑器"""
        # 基本参数
        self.command_name_edit.setText(command.name)
        
        index = self.command_type_combo.findData(command.command_type)
        if index >= 0:
            self.command_type_combo.setCurrentIndex(index)
        
        index = self.send_mode_combo.findData(command.send_mode)
        if index >= 0:
            self.send_mode_combo.setCurrentIndex(index)
        
        self.period_spin.setValue(command.period)
        self.enabled_check.setChecked(command.enabled)
        
        # 命令特定参数
        if command.command_type == CommandType.CAN_FRAME and command.can_frame:
            self.can_id_edit.setText(hex(command.can_frame.arbitration_id))
            self.can_extended_check.setChecked(command.can_frame.is_extended_id)
            self.can_fd_check.setChecked(command.can_frame.is_fd)
            self.can_data_edit.setText(format_hex(command.can_frame.data))
            self.can_dlc_spin.setValue(command.can_frame.dlc)
            self.can_comment_edit.setText(command.can_frame.comment)
            
            self.command_params_stack.setCurrentIndex(0)
            
        elif command.command_type == CommandType.UDS_COMMAND and command.uds_command:
            self.uds_service_edit.setText(hex(command.uds_command.service_id))
            self.uds_subfunction_edit.setText(
                hex(command.uds_command.subfunction) if command.uds_command.subfunction else ""
            )
            self.uds_data_edit.setText(format_hex(command.uds_command.data))
            self.uds_timeout_spin.setValue(command.uds_command.timeout)
            self.uds_expect_response_check.setChecked(command.uds_command.expect_response)
            self.uds_comment_edit.setText(command.uds_command.comment)
            
            self.command_params_stack.setCurrentIndex(1)
            
        elif command.command_type == CommandType.WAIT and command.wait_command:
            self.wait_duration_spin.setValue(command.wait_command.duration)
            self.wait_comment_edit.setText(command.wait_command.comment)
            
            self.command_params_stack.setCurrentIndex(2)
            
        elif command.command_type == CommandType.COMMENT and command.comment_command:
            self.comment_text_edit.setText(command.comment_command.comment)
            
            self.command_params_stack.setCurrentIndex(3)
            
        elif command.command_type == CommandType.SCRIPT and command.script_command:
            self.script_code_edit.setText(command.script_command.script_code)
            self.script_comment_edit.setText(command.script_command.comment)
            
            self.command_params_stack.setCurrentIndex(4)
    
    def save_current_command(self):
        """保存当前命令"""
        try:
            if not self.editing or not hasattr(self, 'editing_command_id'):
                return
            
            # 获取组和命令
            group = self.current_project.get_group(self.editing_group_id)
            if not group:
                return
            
            command = group.get_command(self.editing_command_id)
            if not command:
                return
            
            # 更新命令数据
            command.name = self.command_name_edit.text()
            command.command_type = self.command_type_combo.currentData()
            command.send_mode = self.send_mode_combo.currentData()
            command.period = self.period_spin.value()
            command.enabled = self.enabled_check.isChecked()
            
            # 更新命令特定数据
            if command.command_type == CommandType.CAN_FRAME:
                # 解析CAN ID
                can_id_text = self.can_id_edit.text().strip()
                can_id = 0
                if can_id_text.startswith('0x'):
                    can_id = int(can_id_text, 16)
                else:
                    can_id = int(can_id_text)
                
                # 解析数据
                data_text = self.can_data_edit.toPlainText().strip()
                data = parse_hex_string(data_text)
                
                command.can_frame = CANFrameCommand(
                    arbitration_id=can_id,
                    data=data,
                    is_extended_id=self.can_extended_check.isChecked(),
                    is_fd=self.can_fd_check.isChecked(),
                    dlc=self.can_dlc_spin.value(),
                    comment=self.can_comment_edit.text()
                )
                
            elif command.command_type == CommandType.UDS_COMMAND:
                # 解析服务ID
                service_text = self.uds_service_edit.text().strip()
                service_id = 0
                if service_text.startswith('0x'):
                    service_id = int(service_text, 16)
                else:
                    service_id = int(service_text)
                
                # 解析子功能
                subfunction = None
                subfunction_text = self.uds_subfunction_edit.text().strip()
                if subfunction_text:
                    if subfunction_text.startswith('0x'):
                        subfunction = int(subfunction_text, 16)
                    else:
                        subfunction = int(subfunction_text)
                
                # 解析数据
                data_text = self.uds_data_edit.toPlainText().strip()
                data = parse_hex_string(data_text)
                
                command.uds_command = UDSCommand(
                    service_id=service_id,
                    subfunction=subfunction,
                    data=data,
                    timeout=self.uds_timeout_spin.value(),
                    expect_response=self.uds_expect_response_check.isChecked(),
                    comment=self.uds_comment_edit.text()
                )
                
            elif command.command_type == CommandType.WAIT:
                command.wait_command = WaitCommand(
                    duration=self.wait_duration_spin.value(),
                    comment=self.wait_comment_edit.text()
                )
                
            elif command.command_type == CommandType.COMMENT:
                command.comment_command = CommentCommand(
                    comment=self.comment_text_edit.toPlainText()
                )
                
            elif command.command_type == CommandType.SCRIPT:
                command.script_command = ScriptCommand(
                    script_code=self.script_code_edit.toPlainText(),
                    comment=self.script_comment_edit.text()
                )
            
            # 退出编辑模式
            self.cancel_edit()
            
            # 更新UI
            self.update_project_tree()
            self.update_command_list(self.editing_group_id)
            
            self.show_status_message(f"命令已保存: {command.name}")
            
        except Exception as e:
            logger.error(f"Error saving command: {e}")
            self.show_error_message(f"保存命令失败: {e}")
    
    def cancel_edit(self):
        """取消编辑"""
        self.editing = False
        
        if hasattr(self, 'editing_command_id'):
            delattr(self, 'editing_command_id')
        if hasattr(self, 'editing_group_id'):
            delattr(self, 'editing_group_id')
        
        self.update_editor_state(False)
        
        # 清空编辑器
        self.command_name_edit.clear()
        self.command_type_combo.setCurrentIndex(0)
        self.send_mode_combo.setCurrentIndex(0)
        self.period_spin.setValue(1000)
        self.enabled_check.setChecked(True)
        
        self.can_id_edit.clear()
        self.can_extended_check.setChecked(False)
        self.can_fd_check.setChecked(False)
        self.can_data_edit.clear()
        self.can_dlc_spin.setValue(8)
        self.can_comment_edit.clear()
        
        self.uds_service_edit.clear()
        self.uds_subfunction_edit.clear()
        self.uds_data_edit.clear()
        self.uds_timeout_spin.setValue(2000)
        self.uds_expect_response_check.setChecked(True)
        self.uds_comment_edit.clear()
        
        self.wait_duration_spin.setValue(1000)
        self.wait_comment_edit.clear()
        
        self.comment_text_edit.clear()
        
        self.script_code_edit.clear()
        self.script_comment_edit.clear()
    
    def copy_command(self):
        """复制命令"""
        try:
            # 获取选中的命令
            selected_items = self.command_list.selectedItems()
            if not selected_items:
                return
            
            item = selected_items[0]
            command_id = item.data(Qt.UserRole)
            
            # 查找命令
            source_command = None
            group_id = None
            
            for group in self.current_project.groups:
                for cmd in group.commands:
                    if cmd.id == command_id:
                        source_command = cmd
                        group_id = group.id
                        break
                if source_command:
                    break
            
            if not source_command:
                return
            
            # 创建命令副本
            import uuid
            new_command_id = str(uuid.uuid4())[:8]
            
            # 深拷贝命令
            new_command = copy.deepcopy(source_command)
            new_command.id = new_command_id
            new_command.name = f"{source_command.name} - 副本"
            
            # 添加到同一组
            group = self.current_project.get_group(group_id)
            if group:
                group.add_command(new_command)
                
                # 更新UI
                self.update_project_tree()
                self.update_command_list(group_id)
                
                self.show_status_message(f"已复制命令: {source_command.name}")
            
        except Exception as e:
            logger.error(f"Error copying command: {e}")
            self.show_error_message(f"复制命令失败: {e}")
    
    def toggle_command_enabled(self):
        """切换命令启用状态"""
        try:
            # 获取选中的命令
            selected_items = self.command_list.selectedItems()
            if not selected_items:
                return
            
            for list_item in selected_items:
                command_id = list_item.data(Qt.UserRole)
                
                # 查找命令
                for group in self.current_project.groups:
                    for cmd in group.commands:
                        if cmd.id == command_id:
                            cmd.enabled = not cmd.enabled
                            
                            # 更新列表项
                            text = list_item.text()
                            if cmd.enabled:
                                list_item.setText(text.replace(" [禁用]", ""))
                                list_item.setForeground(QBrush(QColor(TEXT_PRIMARY)))
                            else:
                                if " [禁用]" not in text:
                                    list_item.setText(f"{text} [禁用]")
                                list_item.setForeground(QBrush(QColor(TEXT_DISABLED)))
                            break
                    else:
                        continue
                    break
            
            # 更新工程树
            self.update_project_tree()
            
            self.show_status_message("命令状态已更新")
            
        except Exception as e:
            logger.error(f"Error toggling command enabled: {e}")
            self.show_error_message(f"更新命令状态失败: {e}")
    
    def move_command_up(self):
        """上移命令"""
        try:
            # 获取选中的命令
            selected_items = self.command_list.selectedItems()
            if not selected_items:
                return
            
            item = selected_items[0]
            command_id = item.data(Qt.UserRole)
            current_row = self.command_list.row(item)
            
            if current_row <= 0:
                return
            
            # 查找命令所在组
            for group in self.current_project.groups:
                for i, cmd in enumerate(group.commands):
                    if cmd.id == command_id:
                        # 交换位置
                        if i > 0:
                            group.commands[i], group.commands[i-1] = group.commands[i-1], group.commands[i]
                            
                            # 更新列表
                            self.update_command_list(group.id)
                            
                            # 重新选中
                            self.command_list.setCurrentRow(current_row - 1)
                            
                            self.show_status_message("命令已上移")
                        return
        
        except Exception as e:
            logger.error(f"Error moving command up: {e}")
            self.show_error_message(f"上移命令失败: {e}")
    
    def move_command_down(self):
        """下移命令"""
        try:
            # 获取选中的命令
            selected_items = self.command_list.selectedItems()
            if not selected_items:
                return
            
            item = selected_items[0]
            command_id = item.data(Qt.UserRole)
            current_row = self.command_list.row(item)
            
            # 查找命令所在组
            for group in self.current_project.groups:
                for i, cmd in enumerate(group.commands):
                    if cmd.id == command_id:
                        # 交换位置
                        if i < len(group.commands) - 1:
                            group.commands[i], group.commands[i+1] = group.commands[i+1], group.commands[i]
                            
                            # 更新列表
                            self.update_command_list(group.id)
                            
                            # 重新选中
                            self.command_list.setCurrentRow(current_row + 1)
                            
                            self.show_status_message("命令已下移")
                        return
        
        except Exception as e:
            logger.error(f"Error moving command down: {e}")
            self.show_error_message(f"下移命令失败: {e}")
    
    def delete_item(self):
        """删除选中的项"""
        try:
            # 确定要删除什么
            selected_tree_items = self.project_tree.selectedItems()
            selected_list_items = self.command_list.selectedItems()
            
            if selected_list_items:
                # 删除命令
                command_ids = [item.data(Qt.UserRole) for item in selected_list_items]
                
                # 查找命令所在组
                for group in self.current_project.groups:
                    # 收集要删除的命令
                    commands_to_remove = []
                    for cmd in group.commands:
                        if cmd.id in command_ids:
                            commands_to_remove.append(cmd)
                    
                    # 删除命令
                    for cmd in commands_to_remove:
                        group.remove_command(cmd.id)
                
                # 更新UI
                self.update_project_tree()
                
                # 如果当前正在显示该组，更新命令列表
                if selected_tree_items:
                    item = selected_tree_items[0]
                    if item.data(0, Qt.UserRole) == "group":
                        group_id = item.data(0, Qt.UserRole + 1)
                        self.update_command_list(group_id)
                
                self.show_status_message(f"已删除 {len(command_ids)} 个命令")
                
            elif selected_tree_items:
                item = selected_tree_items[0]
                item_type = item.data(0, Qt.UserRole)
                
                if item_type == "group":
                    # 删除组
                    group_id = item.data(0, Qt.UserRole + 1)
                    
                    reply = QMessageBox.question(
                        self,
                        "删除组",
                        "确定要删除这个组吗？组内的所有命令也将被删除。",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    
                    if reply == QMessageBox.Yes:
                        self.current_project.remove_group(group_id)
                        
                        # 更新UI
                        self.update_project_tree()
                        self.command_list.clear()
                        
                        self.show_status_message("组已删除")
                
                elif item_type == "command":
                    # 删除命令（通过命令列表）
                    pass
            
        except Exception as e:
            logger.error(f"Error deleting item: {e}")
            self.show_error_message(f"删除失败: {e}")
    
    # ========== 执行控制 ==========
    
    def execute_project(self):
        """执行工程"""
        try:
            if not self.current_project:
                self.show_error_message("没有打开的工程")
                return
            
            # 开始执行
            success = self.command_manager.start_project(self.current_project.id, "default")
            if not success:
                raise Exception("开始执行失败")
            
            # 更新UI状态
            self.execute_project_button.setEnabled(False)
            self.stop_execution_button.setEnabled(True)
            self.execute_single_button.setEnabled(False)
            
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            self.execution_status_label.setVisible(True)
            self.execution_status_label.setText("执行中...")
            
            self.show_status_message("开始执行工程")
            self.execution_started.emit()
            
        except Exception as e:
            logger.error(f"Error executing project: {e}")
            self.show_error_message(f"执行工程失败: {e}")
    
    def stop_execution(self):
        """停止执行"""
        try:
            success = self.command_manager.stop_project()
            if not success:
                raise Exception("停止执行失败")
            
            # 更新UI状态
            self.execute_project_button.setEnabled(True)
            self.stop_execution_button.setEnabled(False)
            self.execute_single_button.setEnabled(True)
            
            self.progress_bar.setVisible(False)
            self.execution_status_label.setVisible(False)
            
            self.show_status_message("停止执行工程")
            self.execution_stopped.emit()
            
        except Exception as e:
            logger.error(f"Error stopping execution: {e}")
            self.show_error_message(f"停止执行失败: {e}")
    
    def execute_selected(self):
        """执行选中的命令"""
        try:
            # 获取选中的命令
            selected_items = self.command_list.selectedItems()
            if not selected_items:
                return
            
            # 只执行第一个选中的命令
            item = selected_items[0]
            command_id = item.data(Qt.UserRole)
            
            # 查找命令
            command = None
            for group in self.current_project.groups:
                for cmd in group.commands:
                    if cmd.id == command_id:
                        command = cmd
                        break
                if command:
                    break
            
            if not command:
                return
            
            # 执行单个命令
            self.show_status_message(f"执行命令: {command.name}")
            
            # 这里可以添加执行单个命令的逻辑
            # 例如: self.command_manager.execute_single_command(command)
            
            # 临时模拟执行
            QTimer.singleShot(100, lambda: self.on_command_completed(command, None))
            
        except Exception as e:
            logger.error(f"Error executing selected command: {e}")
            self.show_error_message(f"执行命令失败: {e}")
    
    # ========== UI更新 ==========
    
    def update_project_tree(self):
        """更新工程树"""
        self.project_tree.clear()
        
        if not self.current_project:
            return
        
        # 添加工程根节点
        project_item = QTreeWidgetItem(self.project_tree)
        project_item.setText(0, self.current_project.name)
        project_item.setText(1, "工程")
        project_item.setText(2, "")
        project_item.setText(3, self.current_project.id)
        project_item.setData(0, Qt.UserRole, "project")
        project_item.setData(0, Qt.UserRole + 1, self.current_project.id)
        
        # 添加组
        for group in self.current_project.groups:
            group_item = QTreeWidgetItem(project_item)
            group_item.setText(0, group.name)
            group_item.setText(1, "组")
            group_item.setText(2, "启用" if group.enabled else "禁用")
            group_item.setText(3, group.id)
            group_item.setData(0, Qt.UserRole, "group")
            group_item.setData(0, Qt.UserRole + 1, group.id)
            
            # 添加命令
            for command in group.commands:
                command_item = QTreeWidgetItem(group_item)
                command_item.setText(0, command.name)
                command_item.setText(1, command.command_type.value)
                status_text = ""
                if command.status == CommandStatus.SUCCESS:
                    status_text = "成功"
                elif command.status == CommandStatus.FAILED:
                    status_text = "失败"
                elif command.status == CommandStatus.RUNNING:
                    status_text = "运行中"
                elif command.status == CommandStatus.STOPPED:
                    status_text = "已停止"
                else:
                    status_text = "等待"
                command_item.setText(2, status_text)
                command_item.setText(3, command.id)
                command_item.setData(0, Qt.UserRole, "command")
                command_item.setData(0, Qt.UserRole + 1, command.id)
                
                # 设置命令状态颜色
                if not command.enabled:
                    for i in range(4):
                        command_item.setForeground(i, QBrush(QColor(TEXT_DISABLED)))
        
        # 展开所有项
        self.project_tree.expandAll()
    
    def update_command_list(self, group_id: str):
        """更新命令列表"""
        self.command_list.clear()
        
        if not self.current_project:
            return
        
        group = self.current_project.get_group(group_id)
        if not group:
            return
        
        for command in group.commands:
            item_text = f"{command.name} ({command.command_type.value})"
            if not command.enabled:
                item_text += " [禁用]"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, command.id)
            
            if not command.enabled:
                item.setForeground(QBrush(QColor(TEXT_DISABLED)))
            
            self.command_list.addItem(item)
    
    def update_ui_state(self):
        """更新UI状态"""
        has_project = self.current_project is not None
        
        self.save_project_button.setEnabled(has_project)
        self.save_as_project_button.setEnabled(has_project)
        self.execute_project_button.setEnabled(has_project)
        self.execute_single_button.setEnabled(has_project)
        self.add_group_button.setEnabled(has_project)
        self.add_command_button.setEnabled(has_project)
        self.delete_item_button.setEnabled(has_project)
    
    def update_editor_state(self, editing: bool):
        """更新编辑器状态"""
        self.save_command_button.setEnabled(editing)
        self.cancel_edit_button.setEnabled(editing)
        
        # 编辑器是否可编辑
        self.command_name_edit.setEnabled(editing)
        self.command_type_combo.setEnabled(editing)
        self.send_mode_combo.setEnabled(editing)
        self.period_spin.setEnabled(editing)
        self.enabled_check.setEnabled(editing)
        
        # 命令参数是否可编辑
        for i in range(self.command_params_stack.count()):
            widget = self.command_params_stack.widget(i)
            for child in widget.findChildren(QWidget):
                child.setEnabled(editing)
    
    # ========== 事件处理 ==========
    
    def on_project_tree_selection_changed(self):
        """工程树选择改变"""
        selected_items = self.project_tree.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        item_type = item.data(0, Qt.UserRole)
        
        if item_type == "group":
            group_id = item.data(0, Qt.UserRole + 1)
            self.update_command_list(group_id)
            
            self.add_command_button.setEnabled(True)
            self.delete_item_button.setEnabled(True)
            
        elif item_type == "command":
            command_id = item.data(0, Qt.UserRole + 1)
            
            # 查找命令所在组
            for group in self.current_project.groups:
                for cmd in group.commands:
                    if cmd.id == command_id:
                        # 显示该组的命令列表
                        self.update_command_list(group.id)
                        
                        # 选中该命令
                        for i in range(self.command_list.count()):
                            list_item = self.command_list.item(i)
                            if list_item.data(Qt.UserRole) == command_id:
                                self.command_list.setCurrentItem(list_item)
                                break
                        
                        self.add_command_button.setEnabled(True)
                        self.delete_item_button.setEnabled(True)
                        return
    
    def on_command_list_selection_changed(self):
        """命令列表选择改变"""
        selected_items = self.command_list.selectedItems()
        
        if selected_items:
            self.execute_single_button.setEnabled(True)
            self.delete_item_button.setEnabled(True)
        else:
            self.execute_single_button.setEnabled(False)
            self.delete_item_button.setEnabled(False)
    
    def on_command_type_changed(self, index):
        """命令类型改变"""
        command_type = self.command_type_combo.currentData()
        
        # 根据命令类型切换到对应的选项卡
        if command_type == CommandType.CAN_FRAME:
            self.command_params_stack.setCurrentIndex(0)
        elif command_type == CommandType.UDS_COMMAND:
            self.command_params_stack.setCurrentIndex(1)
        elif command_type == CommandType.WAIT:
            self.command_params_stack.setCurrentIndex(2)
        elif command_type == CommandType.COMMENT:
            self.command_params_stack.setCurrentIndex(3)
        elif command_type == CommandType.SCRIPT:
            self.command_params_stack.setCurrentIndex(4)
    
    def on_send_mode_changed(self, index):
        """发送模式改变"""
        send_mode = self.send_mode_combo.currentData()
        
        # 如果是周期性发送，启用周期设置
        self.period_spin.setEnabled(send_mode == SendMode.PERIODIC)
    
    # ========== 执行回调 ==========
    
    def on_command_started(self, command: Command):
        """命令开始执行回调"""
        self.show_status_message(f"开始执行: {command.name}")
    
    def on_command_completed(self, command: Command, response):
        """命令完成回调"""
        command.status = CommandStatus.SUCCESS
        command.success_count += 1
        
        # 更新工程树
        self.update_project_tree()
        
        self.show_status_message(f"命令完成: {command.name}")
        self.command_executed.emit(command, response)
    
    def on_command_failed(self, command: Command, error):
        """命令失败回调"""
        command.status = CommandStatus.FAILED
        command.fail_count += 1
        
        # 更新工程树
        self.update_project_tree()
        
        self.show_error_message(f"命令失败: {command.name} - {error}")
    
    def on_group_started(self, group: CommandGroup):
        """组开始执行回调"""
        self.show_status_message(f"开始执行组: {group.name}")
    
    def on_group_completed(self, group: CommandGroup):
        """组完成回调"""
        self.show_status_message(f"组执行完成: {group.name}")
        
        # 更新进度条
        total_groups = len(self.current_project.groups)
        executed_groups = sum(1 for g in self.current_project.groups if g.enabled)
        progress = int((executed_groups / total_groups) * 100) if total_groups > 0 else 0
        self.progress_bar.setValue(progress)
    
    def on_project_started(self, project: CommandProject):
        """工程开始执行回调"""
        self.show_status_message(f"开始执行工程: {project.name}")
        
        # 重置所有命令状态
        for group in project.groups:
            for command in group.commands:
                command.status = CommandStatus.PENDING
        
        # 更新工程树
        self.update_project_tree()
    
    def on_project_completed(self, project: CommandProject):
        """工程完成回调"""
        self.show_status_message(f"工程执行完成: {project.name}")
        
        # 更新UI状态
        self.execute_project_button.setEnabled(True)
        self.stop_execution_button.setEnabled(False)
        self.execute_single_button.setEnabled(True)
        
        self.progress_bar.setVisible(False)
        self.execution_status_label.setVisible(False)
    
    # ========== 辅助函数 ==========
    
    def show_status_message(self, message: str):
        """显示状态消息"""
        self.status_label.setText(message)
        logger.info(f"Status: {message}")
    
    def show_error_message(self, message: str):
        """显示错误消息"""
        self.status_label.setText(f"<font color='{COLOR_ERROR}'>{message}</font>")
        logger.error(f"Error: {message}")
        
        # 发射错误信号
        self.error_occurred.emit(message)