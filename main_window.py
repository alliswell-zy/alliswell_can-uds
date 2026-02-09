#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主窗口 - 应用程序主窗口界面
"""

import sys
import os
import logging
from pathlib import Path

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QTabWidget, QToolBar, QAction, QStatusBar,
                            QMessageBox, QSplitter, QMenu, QMenuBar,
                            QApplication, QLabel, QDockWidget, QFrame)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize, QSettings
from PyQt5.QtGui import QIcon, QKeySequence, QCloseEvent

from .can_setting_dialog import CANSettingDialog
from .uds_session_widget import UDSSessionWidget
from .command_project_widget import CommandProjectWidget
from .monitor_widget import MonitorWidget
from utils.helpers import create_icon, show_about_dialog
from utils.constants import *
from config.config_manager import ConfigManager
from core.can_interface import CANInterfaceManager
from core.isotp_protocol import ISOTPManager
from core.uds_session_manager import UDSManager
from core.command_project_manager import CommandProjectManager
from core.monitor_manager import MonitorService

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """应用程序主窗口"""
    
    # 信号定义
    app_exiting = pyqtSignal()
    
    def __init__(self, config_manager: ConfigManager):
        """
        初始化主窗口
        
        Args:
            config_manager: 配置管理器
        """
        super().__init__()
        
        self.config_manager = config_manager
        self.setup_managers()
        self.setup_ui()
        self.setup_connections()
        self.load_settings()
        
        logger.info("Main window initialized")
    
    def setup_managers(self):
        """设置管理器"""
        # CAN接口管理器
        self.can_manager = CANInterfaceManager()
        
        # ISO-TP管理器
        self.isotp_manager = ISOTPManager()
        
        # UDS管理器
        self.uds_manager = UDSManager(self.isotp_manager)
        
        # 命令工程管理器
        self.command_project_manager = CommandProjectManager(
            self.can_manager, 
            self.uds_manager.get_session("default")
        )
        
        # 监控服务
        self.monitor_service = MonitorService(self.can_manager, self.isotp_manager)
        
        # 当前连接的接口ID
        self.current_interface_id = "default"
        
        # 当前项目
        self.current_project = None
        
        logger.info("Managers setup completed")
    
    def setup_ui(self):
        """设置用户界面"""
        # 设置窗口属性
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.resize(MAIN_WINDOW_WIDTH, MAIN_WINDOW_HEIGHT)
        
        # 设置窗口图标
        app_icon = create_icon(ICON_APP)
        if app_icon:
            self.setWindowIcon(app_icon)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建工具栏
        self.setup_toolbar()
        
        # 创建菜单栏
        self.setup_menubar()
        
        # 创建状态栏
        self.setup_statusbar()
        
        # 创建主内容区域
        self.setup_main_content()
        
        # 创建停靠窗口
        self.setup_dock_widgets()
        
        logger.info("UI setup completed")
    
    def setup_toolbar(self):
        """设置工具栏"""
        toolbar = QToolBar("主工具栏")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # CAN设置按钮
        self.can_setting_action = QAction(
            create_icon(ICON_SETTINGS),
            "CAN设置",
            self
        )
        self.can_setting_action.setToolTip("配置CAN接口参数")
        self.can_setting_action.setShortcut("Ctrl+S")
        toolbar.addAction(self.can_setting_action)
        
        toolbar.addSeparator()
        
        # 连接/断开连接按钮
        self.connect_action = QAction(
            create_icon(ICON_CONNECT),
            "连接",
            self
        )
        self.connect_action.setToolTip("连接CAN接口")
        self.connect_action.setShortcut("Ctrl+C")
        toolbar.addAction(self.connect_action)
        
        self.disconnect_action = QAction(
            create_icon(ICON_DISCONNECT),
            "断开连接",
            self
        )
        self.disconnect_action.setToolTip("断开CAN接口连接")
        self.disconnect_action.setShortcut("Ctrl+D")
        self.disconnect_action.setEnabled(False)
        toolbar.addAction(self.disconnect_action)
        
        toolbar.addSeparator()
        
        # 监控控制按钮
        self.monitor_start_action = QAction(
            create_icon(ICON_PLAY),
            "开始监控",
            self
        )
        self.monitor_start_action.setToolTip("开始监控CAN总线")
        self.monitor_start_action.setShortcut("Ctrl+M")
        toolbar.addAction(self.monitor_start_action)
        
        self.monitor_stop_action = QAction(
            create_icon(ICON_STOP),
            "停止监控",
            self
        )
        self.monitor_stop_action.setToolTip("停止监控CAN总线")
        self.monitor_stop_action.setEnabled(False)
        toolbar.addAction(self.monitor_stop_action)
        
        self.monitor_clear_action = QAction(
            create_icon(ICON_CLEAR),
            "清空监控",
            self
        )
        self.monitor_clear_action.setToolTip("清空监控数据")
        toolbar.addAction(self.monitor_clear_action)
        
        toolbar.addSeparator()
        
        # 项目控制按钮
        self.project_new_action = QAction(
            create_icon(ICON_ADD),
            "新建项目",
            self
        )
        self.project_new_action.setToolTip("新建命令工程")
        self.project_new_action.setShortcut(KEY_NEW_PROJECT)
        toolbar.addAction(self.project_new_action)
        
        self.project_open_action = QAction(
            create_icon(ICON_LOAD),
            "打开项目",
            self
        )
        self.project_open_action.setToolTip("打开命令工程")
        self.project_open_action.setShortcut(KEY_OPEN_PROJECT)
        toolbar.addAction(self.project_open_action)
        
        self.project_save_action = QAction(
            create_icon(ICON_SAVE),
            "保存项目",
            self
        )
        self.project_save_action.setToolTip("保存命令工程")
        self.project_save_action.setShortcut(KEY_SAVE_PROJECT)
        self.project_save_action.setEnabled(False)
        toolbar.addAction(self.project_save_action)
        
        toolbar.addSeparator()
        
        # 执行控制按钮
        self.execute_start_action = QAction(
            create_icon(ICON_PLAY),
            "开始执行",
            self
        )
        self.execute_start_action.setToolTip("开始执行命令工程")
        self.execute_start_action.setShortcut("Ctrl+R")
        self.execute_start_action.setEnabled(False)
        toolbar.addAction(self.execute_start_action)
        
        self.execute_stop_action = QAction(
            create_icon(ICON_STOP),
            "停止执行",
            self
        )
        self.execute_stop_action.setToolTip("停止执行命令工程")
        self.execute_stop_action.setEnabled(False)
        toolbar.addAction(self.execute_stop_action)
        
        toolbar.addSeparator()
        
        # 帮助按钮
        self.help_action = QAction(
            create_icon(ICON_HELP),
            "帮助",
            self
        )
        self.help_action.setToolTip("显示帮助")
        self.help_action.setShortcut(KEY_HELP)
        toolbar.addAction(self.help_action)
        
        self.about_action = QAction(
            create_icon(ICON_ABOUT),
            "关于",
            self
        )
        self.about_action.setToolTip("关于本程序")
        self.about_action.setShortcut(KEY_ABOUT)
        toolbar.addAction(self.about_action)
    
    def setup_menubar(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        
        file_menu.addAction(self.project_new_action)
        file_menu.addAction(self.project_open_action)
        file_menu.addAction(self.project_save_action)
        
        file_menu.addSeparator()
        
        export_action = QAction("导出监控数据...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self.export_monitor_data)
        file_menu.addAction(export_action)
        
        import_action = QAction("导入项目...", self)
        import_action.setShortcut("Ctrl+I")
        import_action.triggered.connect(self.import_project)
        file_menu.addAction(import_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut(KEY_EXIT)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = menubar.addMenu("编辑(&E)")
        
        copy_action = QAction("复制(&C)", self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self.copy_text)
        edit_menu.addAction(copy_action)
        
        paste_action = QAction("粘贴(&V)", self)
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(self.paste_text)
        edit_menu.addAction(paste_action)
        
        edit_menu.addSeparator()
        
        find_action = QAction("查找(&F)", self)
        find_action.setShortcut("Ctrl+F")
        find_action.triggered.connect(self.find_text)
        edit_menu.addAction(find_action)
        
        # 视图菜单
        view_menu = menubar.addMenu("视图(&V)")
        
        self.toolbar_action = QAction("工具栏", self)
        self.toolbar_action.setCheckable(True)
        self.toolbar_action.setChecked(True)
        self.toolbar_action.triggered.connect(self.toggle_toolbar)
        view_menu.addAction(self.toolbar_action)
        
        self.statusbar_action = QAction("状态栏", self)
        self.statusbar_action.setCheckable(True)
        self.statusbar_action.setChecked(True)
        self.statusbar_action.triggered.connect(self.toggle_statusbar)
        view_menu.addAction(self.statusbar_action)
        
        view_menu.addSeparator()
        
        self.monitor_dock_action = QAction("监控窗口", self)
        self.monitor_dock_action.setCheckable(True)
        self.monitor_dock_action.setChecked(True)
        self.monitor_dock_action.triggered.connect(self.toggle_monitor_dock)
        view_menu.addAction(self.monitor_dock_action)
        
        view_menu.addSeparator()
        
        zoom_in_action = QAction("放大(&+)", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(self.zoom_in)
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("缩小(&-)", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(self.zoom_out)
        view_menu.addAction(zoom_out_action)
        
        reset_zoom_action = QAction("重置缩放(&0)", self)
        reset_zoom_action.setShortcut("Ctrl+0")
        reset_zoom_action.triggered.connect(self.reset_zoom)
        view_menu.addAction(reset_zoom_action)
        
        # 工具菜单
        tool_menu = menubar.addMenu("工具(&T)")
        
        tool_menu.addAction(self.can_setting_action)
        tool_menu.addSeparator()
        
        calculator_action = QAction("计算器(&C)", self)
        calculator_action.setShortcut("Ctrl+Alt+C")
        calculator_action.triggered.connect(self.open_calculator)
        tool_menu.addAction(calculator_action)
        
        converter_action = QAction("转换器(&V)", self)
        converter_action.setShortcut("Ctrl+Alt+V")
        converter_action.triggered.connect(self.open_converter)
        tool_menu.addAction(converter_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        
        help_menu.addAction(self.help_action)
        help_menu.addSeparator()
        help_menu.addAction(self.about_action)
    
    def setup_statusbar(self):
        """设置状态栏"""
        statusbar = QStatusBar()
        self.setStatusBar(statusbar)
        
        # 连接状态指示器
        self.connection_status_label = QLabel("未连接")
        self.connection_status_label.setStyleSheet(
            f"padding: 2px 8px; border-radius: 10px; background-color: {COLOR_ERROR}; color: white;"
        )
        statusbar.addPermanentWidget(self.connection_status_label)
        
        # 监控状态指示器
        self.monitor_status_label = QLabel("监控停止")
        self.monitor_status_label.setStyleSheet(
            f"padding: 2px 8px; border-radius: 10px; background-color: {COLOR_DISABLED}; color: white;"
        )
        statusbar.addPermanentWidget(self.monitor_status_label)
        
        # 帧计数
        self.frame_count_label = QLabel("帧: 0")
        statusbar.addPermanentWidget(self.frame_count_label)
        
        # 帧率
        self.frame_rate_label = QLabel("帧率: 0.0 fps")
        statusbar.addPermanentWidget(self.frame_rate_label)
        
        # 状态消息
        self.status_message_label = QLabel("就绪")
        statusbar.addWidget(self.status_message_label)
        
        # 更新状态栏的定时器
        self.statusbar_timer = QTimer()
        self.statusbar_timer.timeout.connect(self.update_statusbar)
        self.statusbar_timer.start(1000)  # 每秒更新一次
    
    def setup_main_content(self):
        """设置主内容区域"""
        # 创建主分割器
        main_splitter = QSplitter(Qt.Horizontal)
        
        # 创建左侧部件（选项卡）
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建选项卡部件
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.West)
        
        # UDS会话选项卡
        self.uds_session_widget = UDSSessionWidget(
            self.can_manager,
            self.uds_manager,
            self.config_manager
        )
        self.tab_widget.addTab(self.uds_session_widget, create_icon("uds.png"), "UDS会话")
        
        # 命令工程选项卡
        self.command_project_widget = CommandProjectWidget(
            self.command_project_manager,
            self.config_manager
        )
        self.tab_widget.addTab(self.command_project_widget, create_icon("project.png"), "命令工程")
        
        left_layout.addWidget(self.tab_widget)
        
        # 创建右侧部件（监控）
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 监控部件
        self.monitor_widget = MonitorWidget(self.monitor_service)
        right_layout.addWidget(self.monitor_widget)
        
        # 添加部件到分割器
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        
        # 设置分割器初始大小
        main_splitter.setSizes([700, 300])
        
        # 设置中心部件布局
        central_widget = self.centralWidget()
        central_layout = central_widget.layout()
        central_layout.addWidget(main_splitter)
    
    def setup_dock_widgets(self):
        """设置停靠窗口"""
        # 创建消息窗口停靠部件
        self.message_dock = QDockWidget("消息", self)
        self.message_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        
        # 创建消息部件
        from PyQt5.QtWidgets import QTextEdit
        self.message_text_edit = QTextEdit()
        self.message_text_edit.setReadOnly(True)
        self.message_text_edit.setMaximumHeight(150)
        self.message_dock.setWidget(self.message_text_edit)
        
        self.addDockWidget(Qt.BottomDockWidgetArea, self.message_dock)
        
        # 默认隐藏消息窗口
        self.message_dock.hide()
    
    def setup_connections(self):
        """设置信号槽连接"""
        # 工具栏动作
        self.can_setting_action.triggered.connect(self.open_can_settings)
        self.connect_action.triggered.connect(self.connect_can)
        self.disconnect_action.triggered.connect(self.disconnect_can)
        self.monitor_start_action.triggered.connect(self.start_monitoring)
        self.monitor_stop_action.triggered.connect(self.stop_monitoring)
        self.monitor_clear_action.triggered.connect(self.clear_monitoring)
        self.project_new_action.triggered.connect(self.new_project)
        self.project_open_action.triggered.connect(self.open_project)
        self.project_save_action.triggered.connect(self.save_project)
        self.execute_start_action.triggered.connect(self.start_execution)
        self.execute_stop_action.triggered.connect(self.stop_execution)
        self.help_action.triggered.connect(self.show_help)
        self.about_action.triggered.connect(self.show_about)
        
        # 监控服务信号
        if hasattr(self.monitor_service.monitor_manager, 'on_frame_received'):
            self.monitor_service.monitor_manager.on_frame_received = self.on_monitor_frame_received
        
        # 命令工程管理器信号
        self.command_project_manager.executor.on_command_completed = self.on_command_completed
        self.command_project_manager.executor.on_command_failed = self.on_command_failed
        self.command_project_manager.executor.on_project_completed = self.on_project_completed
        
        # 窗口关闭信号
        self.app_exiting.connect(self.cleanup)
    
    def load_settings(self):
        """加载设置"""
        try:
            # 从配置管理器加载窗口设置
            user_settings = self.config_manager.user_settings
            
            if user_settings.get('window_geometry'):
                self.restoreGeometry(user_settings['window_geometry'])
            
            if user_settings.get('window_state'):
                self.restoreState(user_settings['window_state'])
            
            # 加载其他设置
            theme = user_settings.get('theme', 'light')
            # TODO: 应用主题
            
            logger.info("Settings loaded")
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
    
    def save_settings(self):
        """保存设置"""
        try:
            # 保存窗口状态
            self.config_manager.user_settings['window_geometry'] = self.saveGeometry()
            self.config_manager.user_settings['window_state'] = self.saveState()
            
            # 保存配置
            self.config_manager.save_config()
            
            logger.info("Settings saved")
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
    
    def update_statusbar(self):
        """更新状态栏"""
        try:
            # 更新连接状态
            interface = self.can_manager.get_interface(self.current_interface_id)
            if interface and interface.is_connected:
                self.connection_status_label.setText("已连接")
                self.connection_status_label.setStyleSheet(
                    f"padding: 2px 8px; border-radius: 10px; background-color: {COLOR_SUCCESS}; color: white;"
                )
            else:
                self.connection_status_label.setText("未连接")
                self.connection_status_label.setStyleSheet(
                    f"padding: 2px 8px; border-radius: 10px; background-color: {COLOR_ERROR}; color: white;"
                )
            
            # 更新监控状态
            if self.monitor_service.monitor_manager.is_running():
                self.monitor_status_label.setText("监控运行中")
                self.monitor_status_label.setStyleSheet(
                    f"padding: 2px 8px; border-radius: 10px; background-color: {COLOR_SUCCESS}; color: white;"
                )
            else:
                self.monitor_status_label.setText("监控停止")
                self.monitor_status_label.setStyleSheet(
                    f"padding: 2px 8px; border-radius: 10px; background-color: {COLOR_DISABLED}; color: white;"
                )
            
            # 更新帧统计
            stats = self.monitor_service.monitor_manager.get_statistics()
            self.frame_count_label.setText(f"帧: {stats.get('total_frames', 0)}")
            self.frame_rate_label.setText(f"帧率: {stats.get('frame_rate', 0):.1f} fps")
            
        except Exception as e:
            logger.error(f"Error updating statusbar: {e}")
    
    # ========== 槽函数 ==========
    
    def open_can_settings(self):
        """打开CAN设置对话框"""
        dialog = CANSettingDialog(self.config_manager, self)
        if dialog.exec_() == CANSettingDialog.Accepted:
            # 更新配置
            self.config_manager.save_config()
            logger.info("CAN settings updated")
    
    def connect_can(self):
        """连接CAN接口"""
        try:
            # 获取配置
            can_config = self.config_manager.can_config
            
            # 创建接口
            interface = self.can_manager.create_interface(
                self.current_interface_id,
                can_config.interface_type.value,
                channel=can_config.channel,
                bitrate=can_config.bitrate,
                fd_enabled=can_config.fd_enabled,
                data_bitrate=can_config.data_bitrate,
                **can_config.to_dict()
            )
            
            # 连接接口
            if interface.connect():
                # 更新按钮状态
                self.connect_action.setEnabled(False)
                self.disconnect_action.setEnabled(True)
                
                # 开始监控
                self.monitor_service.start_monitoring(self.current_interface_id)
                self.start_monitoring()
                
                # 显示消息
                self.show_status_message("CAN接口连接成功")
                logger.info("CAN interface connected")
            else:
                self.show_status_message("CAN接口连接失败", error=True)
                logger.error("CAN interface connection failed")
                
        except Exception as e:
            self.show_status_message(f"连接失败: {e}", error=True)
            logger.error(f"Error connecting CAN interface: {e}")
    
    def disconnect_can(self):
        """断开CAN接口连接"""
        try:
            # 停止监控
            self.stop_monitoring()
            
            # 断开接口
            if self.can_manager.disconnect_interface(self.current_interface_id):
                # 更新按钮状态
                self.connect_action.setEnabled(True)
                self.disconnect_action.setEnabled(False)
                
                # 显示消息
                self.show_status_message("CAN接口已断开")
                logger.info("CAN interface disconnected")
            else:
                self.show_status_message("断开连接失败", error=True)
                logger.error("CAN interface disconnection failed")
                
        except Exception as e:
            self.show_status_message(f"断开连接失败: {e}", error=True)
            logger.error(f"Error disconnecting CAN interface: {e}")
    
    def start_monitoring(self):
        """开始监控"""
        try:
            if self.monitor_service.monitor_manager.start():
                self.monitor_start_action.setEnabled(False)
                self.monitor_stop_action.setEnabled(True)
                self.show_status_message("监控已启动")
                logger.info("Monitoring started")
            else:
                self.show_status_message("监控启动失败", error=True)
                logger.error("Monitoring start failed")
        except Exception as e:
            self.show_status_message(f"监控启动失败: {e}", error=True)
            logger.error(f"Error starting monitoring: {e}")
    
    def stop_monitoring(self):
        """停止监控"""
        try:
            if self.monitor_service.monitor_manager.stop():
                self.monitor_start_action.setEnabled(True)
                self.monitor_stop_action.setEnabled(False)
                self.show_status_message("监控已停止")
                logger.info("Monitoring stopped")
            else:
                self.show_status_message("监控停止失败", error=True)
                logger.error("Monitoring stop failed")
        except Exception as e:
            self.show_status_message(f"监控停止失败: {e}", error=True)
            logger.error(f"Error stopping monitoring: {e}")
    
    def clear_monitoring(self):
        """清空监控数据"""
        try:
            self.monitor_service.monitor_manager.clear_buffer()
            self.show_status_message("监控数据已清空")
            logger.info("Monitoring data cleared")
        except Exception as e:
            self.show_status_message(f"清空监控数据失败: {e}", error=True)
            logger.error(f"Error clearing monitoring data: {e}")
    
    def new_project(self):
        """新建项目"""
        try:
            self.command_project_widget.new_project()
            self.project_save_action.setEnabled(True)
            self.execute_start_action.setEnabled(True)
            self.show_status_message("新建项目成功")
            logger.info("New project created")
        except Exception as e:
            self.show_status_message(f"新建项目失败: {e}", error=True)
            logger.error(f"Error creating new project: {e}")
    
    def open_project(self):
        """打开项目"""
        try:
            if self.command_project_widget.open_project():
                self.project_save_action.setEnabled(True)
                self.execute_start_action.setEnabled(True)
                self.show_status_message("打开项目成功")
                logger.info("Project opened")
            else:
                self.show_status_message("打开项目失败", error=True)
                logger.error("Project open failed")
        except Exception as e:
            self.show_status_message(f"打开项目失败: {e}", error=True)
            logger.error(f"Error opening project: {e}")
    
    def save_project(self):
        """保存项目"""
        try:
            if self.command_project_widget.save_project():
                self.show_status_message("保存项目成功")
                logger.info("Project saved")
            else:
                self.show_status_message("保存项目失败", error=True)
                logger.error("Project save failed")
        except Exception as e:
            self.show_status_message(f"保存项目失败: {e}", error=True)
            logger.error(f"Error saving project: {e}")
    
    def start_execution(self):
        """开始执行命令工程"""
        try:
            if self.command_project_manager.start_project("current", self.current_interface_id):
                self.execute_start_action.setEnabled(False)
                self.execute_stop_action.setEnabled(True)
                self.show_status_message("开始执行命令工程")
                logger.info("Command project execution started")
            else:
                self.show_status_message("开始执行失败", error=True)
                logger.error("Command project execution start failed")
        except Exception as e:
            self.show_status_message(f"开始执行失败: {e}", error=True)
            logger.error(f"Error starting command project execution: {e}")
    
    def stop_execution(self):
        """停止执行命令工程"""
        try:
            if self.command_project_manager.stop_project():
                self.execute_start_action.setEnabled(True)
                self.execute_stop_action.setEnabled(False)
                self.show_status_message("停止执行命令工程")
                logger.info("Command project execution stopped")
            else:
                self.show_status_message("停止执行失败", error=True)
                logger.error("Command project execution stop failed")
        except Exception as e:
            self.show_status_message(f"停止执行失败: {e}", error=True)
            logger.error(f"Error stopping command project execution: {e}")
    
    def export_monitor_data(self):
        """导出监控数据"""
        try:
            from PyQt5.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出监控数据",
                "",
                "文本文件 (*.txt);;CSV文件 (*.csv);;所有文件 (*.*)"
            )
            
            if file_path:
                self.monitor_service.monitor_manager.export_to_file(file_path)
                self.show_status_message(f"监控数据已导出到: {file_path}")
                logger.info(f"Monitor data exported to: {file_path}")
        except Exception as e:
            self.show_status_message(f"导出失败: {e}", error=True)
            logger.error(f"Error exporting monitor data: {e}")
    
    def import_project(self):
        """导入项目"""
        try:
            from PyQt5.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "导入项目",
                "",
                "UDS项目文件 (*.udsp);;JSON文件 (*.json);;所有文件 (*.*)"
            )
            
            if file_path:
                # 这里可以实现项目导入逻辑
                self.show_status_message(f"导入项目: {file_path}")
                logger.info(f"Project import requested: {file_path}")
        except Exception as e:
            self.show_status_message(f"导入失败: {e}", error=True)
            logger.error(f"Error importing project: {e}")
    
    def copy_text(self):
        """复制文本"""
        try:
            # 获取当前焦点控件
            focused_widget = QApplication.focusWidget()
            if hasattr(focused_widget, 'copy'):
                focused_widget.copy()
                self.show_status_message("已复制")
        except Exception as e:
            logger.error(f"Error copying text: {e}")
    
    def paste_text(self):
        """粘贴文本"""
        try:
            # 获取当前焦点控件
            focused_widget = QApplication.focusWidget()
            if hasattr(focused_widget, 'paste'):
                focused_widget.paste()
                self.show_status_message("已粘贴")
        except Exception as e:
            logger.error(f"Error pasting text: {e}")
    
    def find_text(self):
        """查找文本"""
        try:
            # 这里可以实现查找功能
            self.show_status_message("查找功能")
            logger.info("Find text requested")
        except Exception as e:
            logger.error(f"Error finding text: {e}")
    
    def toggle_toolbar(self):
        """切换工具栏显示"""
        self.toolBar().setVisible(self.toolbar_action.isChecked())
    
    def toggle_statusbar(self):
        """切换状态栏显示"""
        self.statusBar().setVisible(self.statusbar_action.isChecked())
    
    def toggle_monitor_dock(self):
        """切换监控窗口显示"""
        if self.monitor_dock_action.isChecked():
            self.message_dock.show()
        else:
            self.message_dock.hide()
    
    def zoom_in(self):
        """放大"""
        try:
            # 这里可以实现放大功能
            self.show_status_message("放大")
            logger.info("Zoom in requested")
        except Exception as e:
            logger.error(f"Error zooming in: {e}")
    
    def zoom_out(self):
        """缩小"""
        try:
            # 这里可以实现缩小功能
            self.show_status_message("缩小")
            logger.info("Zoom out requested")
        except Exception as e:
            logger.error(f"Error zooming out: {e}")
    
    def reset_zoom(self):
        """重置缩放"""
        try:
            # 这里可以实现重置缩放功能
            self.show_status_message("重置缩放")
            logger.info("Reset zoom requested")
        except Exception as e:
            logger.error(f"Error resetting zoom: {e}")
    
    def open_calculator(self):
        """打开计算器"""
        try:
            # 这里可以实现计算器功能
            self.show_status_message("计算器")
            logger.info("Calculator requested")
        except Exception as e:
            logger.error(f"Error opening calculator: {e}")
    
    def open_converter(self):
        """打开转换器"""
        try:
            # 这里可以实现转换器功能
            self.show_status_message("转换器")
            logger.info("Converter requested")
        except Exception as e:
            logger.error(f"Error opening converter: {e}")
    
    def show_help(self):
        """显示帮助"""
        try:
            # 这里可以实现帮助功能
            QMessageBox.information(
                self,
                "帮助",
                "UDS诊断工具帮助\n\n"
                "1. CAN设置: 配置CAN接口参数\n"
                "2. UDS会话: 发送UDS诊断命令\n"
                "3. 命令工程: 创建和管理命令序列\n"
                "4. 监控: 实时监控CAN总线数据\n\n"
                "快捷键:\n"
                "Ctrl+N: 新建项目\n"
                "Ctrl+O: 打开项目\n"
                "Ctrl+S: 保存项目\n"
                "Ctrl+C: 连接CAN接口\n"
                "Ctrl+D: 断开CAN接口\n"
                "F1: 帮助\n"
                "F2: 关于"
            )
            logger.info("Help displayed")
        except Exception as e:
            logger.error(f"Error showing help: {e}")
    
    def show_about(self):
        """显示关于对话框"""
        try:
            show_about_dialog(self)
            logger.info("About dialog displayed")
        except Exception as e:
            logger.error(f"Error showing about dialog: {e}")
    
    # ========== 事件处理 ==========
    
    def closeEvent(self, event: QCloseEvent):
        """关闭事件处理"""
        try:
            # 询问是否保存
            if self.current_project:
                reply = QMessageBox.question(
                    self,
                    "退出",
                    "是否保存当前项目？",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                    QMessageBox.Yes
                )
                
                if reply == QMessageBox.Cancel:
                    event.ignore()
                    return
                elif reply == QMessageBox.Yes:
                    self.save_project()
            
            # 清理资源
            self.cleanup()
            
            # 保存设置
            self.save_settings()
            
            # 发送退出信号
            self.app_exiting.emit()
            
            # 接受关闭事件
            event.accept()
            
            logger.info("Application closing")
            
        except Exception as e:
            logger.error(f"Error during close event: {e}")
            event.accept()
    
    # ========== 回调函数 ==========
    
    def on_monitor_frame_received(self, frame):
        """监控帧接收回调"""
        # 在消息窗口中显示帧
        if self.message_dock.isVisible():
            formatted_frame = frame.format(self.monitor_service.monitor_manager.config)
            self.message_text_edit.append(formatted_frame)
    
    def on_command_completed(self, command, response):
        """命令完成回调"""
        self.show_status_message(f"命令完成: {command.name}")
    
    def on_command_failed(self, command, error):
        """命令失败回调"""
        self.show_status_message(f"命令失败: {command.name} - {error}", error=True)
    
    def on_project_completed(self, project):
        """项目完成回调"""
        self.show_status_message(f"项目执行完成: {project.name}")
        self.execute_start_action.setEnabled(True)
        self.execute_stop_action.setEnabled(False)
    
    def show_status_message(self, message: str, error: bool = False):
        """显示状态消息"""
        try:
            if error:
                self.status_message_label.setText(f"<font color='{COLOR_ERROR}'>{message}</font>")
                logger.error(f"Status: {message}")
            else:
                self.status_message_label.setText(message)
                logger.info(f"Status: {message}")
            
            # 3秒后清除消息
            QTimer.singleShot(3000, lambda: self.status_message_label.setText("就绪"))
        except Exception as e:
            logger.error(f"Error showing status message: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            # 停止监控
            self.stop_monitoring()
            
            # 断开CAN连接
            self.disconnect_can()
            
            # 停止命令执行
            self.stop_execution()
            
            # 关闭监控服务
            self.monitor_service.close()
            
            # 关闭管理器
            self.uds_manager.close_all_sessions()
            
            logger.info("Resources cleaned up")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")