#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UDS诊断工具 - 主程序入口
支持多种CAN卡：PCAN、VECTOR、IXXAT、KVASER、SLCAN、candleLight、NI XNET、virtual
支持CAN FD UDS协议，完整实现ISO 15765-2:2022、ISO 14229-1等标准
"""

import sys
import os
import logging
import traceback
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PyQt5.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PyQt5.QtGui import QPixmap, QFont, QFontDatabase
from PyQt5.QtCore import Qt, QTimer
from ui.main_window import MainWindow
from config.config_manager import ConfigManager
from utils.helpers import setup_logging, check_environment, load_stylesheet
from utils.constants import APP_NAME, APP_VERSION, LOG_FILE

def setup_fonts():
    """设置应用程序字体"""
    try:
        font_path = project_root / "fonts"
        if font_path.exists():
            for font_file in font_path.glob("*.ttf"):
                font_id = QFontDatabase.addApplicationFont(str(font_file))
                if font_id != -1:
                    font_families = QFontDatabase.applicationFontFamilies(font_id)
                    print(f"Loaded font: {font_families}")
    except Exception as e:
        print(f"Font loading error: {e}")

def show_splash_screen():
    """显示启动画面"""
    splash_pix = QPixmap(400, 300)
    splash_pix.fill(Qt.white)
    
    splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
    splash.show()
    
    # 显示应用程序信息
    splash.showMessage(
        f"{APP_NAME}\n"
        f"Version: {APP_VERSION}\n"
        "Loading...",
        Qt.AlignBottom | Qt.AlignHCenter,
        Qt.black
    )
    
    QApplication.processEvents()
    return splash

def main():
    """主函数"""
    try:
        # 检查Python版本
        if sys.version_info < (3, 8):
            print("Error: Python 3.8 or higher is required")
            sys.exit(1)
        
        # 检查环境
        if not check_environment():
            print("Environment check failed")
            sys.exit(1)
        
        # 设置日志
        setup_logging()
        logger = logging.getLogger(__name__)
        logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
        
        # 创建应用程序
        app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        app.setApplicationVersion(APP_VERSION)
        app.setOrganizationName("UDS Diagnostics")
        
        # 设置字体
        setup_fonts()
        
        # 显示启动画面
        splash = show_splash_screen()
        
        # 加载样式表
        style_sheet = load_stylesheet()
        if style_sheet:
            app.setStyleSheet(style_sheet)
        
        # 创建配置管理器
        config_manager = ConfigManager()
        
        # 创建主窗口
        QTimer.singleShot(1000, lambda: splash.close())
        main_window = MainWindow(config_manager)
        main_window.show()
        
        # 处理应用程序退出
        sys.exit(app.exec_())
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("Please install required packages: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Critical error: {e}")
        traceback.print_exc()
        
        # 显示错误对话框
        app = QApplication(sys.argv)
        error_msg = QMessageBox()
        error_msg.setIcon(QMessageBox.Critical)
        error_msg.setWindowTitle("Application Error")
        error_msg.setText(f"A critical error occurred:\n{str(e)}")
        error_msg.setDetailedText(traceback.format_exc())
        error_msg.exec_()
        sys.exit(1)

if __name__ == "__main__":
    main()