#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
样式表定义 - 应用程序的样式和主题
"""

from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt
from utils.constants import *

def get_light_theme_stylesheet() -> str:
    """获取明亮主题样式表"""
    return f"""
    /* 主窗口样式 */
    QMainWindow {{
        background-color: {BG_LIGHT};
    }}
    
    /* 中央部件 */
    QWidget {{
        background-color: {BG_LIGHT};
        color: {TEXT_PRIMARY};
        font-family: "{FONT_FAMILY}", "Microsoft YaHei", sans-serif;
        font-size: {FONT_SIZE_NORMAL}px;
    }}
    
    /* 按钮样式 */
    QPushButton {{
        background-color: {COLOR_PRIMARY};
        color: {TEXT_LIGHT};
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: bold;
        font-size: {FONT_SIZE_NORMAL}px;
        min-height: 32px;
        min-width: 80px;
    }}
    
    QPushButton:hover {{
        background-color: #106EBE;
    }}
    
    QPushButton:pressed {{
        background-color: #005A9E;
    }}
    
    QPushButton:disabled {{
        background-color: {COLOR_DISABLED};
        color: {TEXT_DISABLED};
    }}
    
    /* 主要操作按钮 */
    QPushButton.primary {{
        background-color: {COLOR_PRIMARY};
        color: {TEXT_LIGHT};
    }}
    
    /* 成功按钮 */
    QPushButton.success {{
        background-color: {COLOR_SUCCESS};
        color: {TEXT_LIGHT};
    }}
    
    /* 警告按钮 */
    QPushButton.warning {{
        background-color: {COLOR_WARNING};
        color: {TEXT_PRIMARY};
    }}
    
    /* 危险按钮 */
    QPushButton.danger {{
        background-color: {COLOR_ERROR};
        color: {TEXT_LIGHT};
    }}
    
    /* 次要按钮 */
    QPushButton.secondary {{
        background-color: {COLOR_SECONDARY};
        color: {TEXT_LIGHT};
    }}
    
    /* 小型按钮 */
    QPushButton.small {{
        padding: 4px 8px;
        font-size: {FONT_SIZE_SMALL}px;
        min-height: 24px;
        min-width: 60px;
    }}
    
    /* 大型按钮 */
    QPushButton.large {{
        padding: 12px 24px;
        font-size: {FONT_SIZE_LARGE}px;
        min-height: 40px;
        min-width: 100px;
    }}
    
    /* 文本输入框样式 */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        border: 1px solid {BORDER_MEDIUM};
        border-radius: 2px;
        padding: 6px 8px;
        background-color: {BG_LIGHT};
        selection-background-color: {COLOR_PRIMARY};
        selection-color: {TEXT_LIGHT};
        font-size: {FONT_SIZE_NORMAL}px;
    }}
    
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border: 2px solid {COLOR_PRIMARY};
        padding: 5px 7px;
    }}
    
    QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
        background-color: {BG_DARK};
        color: {TEXT_DISABLED};
    }}
    
    /* 只读文本框 */
    QLineEdit[readOnly="true"], QTextEdit[readOnly="true"], QPlainTextEdit[readOnly="true"] {{
        background-color: {BG_DARK};
        color: {TEXT_SECONDARY};
    }}
    
    /* 组合框样式 */
    QComboBox {{
        border: 1px solid {BORDER_MEDIUM};
        border-radius: 2px;
        padding: 6px 8px;
        background-color: {BG_LIGHT};
        min-height: 32px;
        font-size: {FONT_SIZE_NORMAL}px;
    }}
    
    QComboBox:editable {{
        background-color: {BG_LIGHT};
    }}
    
    QComboBox:focus {{
        border: 2px solid {COLOR_PRIMARY};
        padding: 5px 7px;
    }}
    
    QComboBox:disabled {{
        background-color: {BG_DARK};
        color: {TEXT_DISABLED};
    }}
    
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    
    QComboBox::down-arrow {{
        image: url(:/icons/down_arrow.png);
        width: 12px;
        height: 12px;
    }}
    
    /* 表格样式 */
    QTableView, QTableWidget {{
        background-color: {BG_LIGHT};
        alternate-background-color: {BG_ALTERNATE};
        gridline-color: {BORDER_LIGHT};
        selection-background-color: {COLOR_PRIMARY};
        selection-color: {TEXT_LIGHT};
        border: 1px solid {BORDER_LIGHT};
        font-size: {FONT_SIZE_NORMAL}px;
    }}
    
    QTableView::item, QTableWidget::item {{
        padding: 4px;
    }}
    
    QTableView::item:selected, QTableWidget::item:selected {{
        background-color: {COLOR_PRIMARY};
        color: {TEXT_LIGHT};
    }}
    
    QHeaderView::section {{
        background-color: {BG_DARK};
        padding: 8px;
        border: 1px solid {BORDER_LIGHT};
        font-weight: bold;
        font-size: {FONT_SIZE_NORMAL}px;
    }}
    
    /* 标签页样式 */
    QTabWidget::pane {{
        border: 1px solid {BORDER_MEDIUM};
        background-color: {BG_LIGHT};
        border-radius: 4px;
        margin-top: -1px;
    }}
    
    QTabBar::tab {{
        background-color: {BG_DARK};
        padding: 8px 16px;
        margin-right: 2px;
        border: 1px solid {BORDER_MEDIUM};
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        font-size: {FONT_SIZE_NORMAL}px;
        min-width: 80px;
        min-height: 30px;
    }}
    
    QTabBar::tab:selected {{
        background-color: {BG_LIGHT};
        border-bottom: 2px solid {COLOR_PRIMARY};
        font-weight: bold;
    }}
    
    QTabBar::tab:hover:!selected {{
        background-color: #E1DFDD;
    }}
    
    QTabBar::tab:disabled {{
        background-color: {BG_DARK};
        color: {TEXT_DISABLED};
    }}
    
    /* 标签样式 */
    QLabel {{
        color: {TEXT_PRIMARY};
        font-size: {FONT_SIZE_NORMAL}px;
    }}
    
    QLabel.title {{
        font-size: {FONT_SIZE_TITLE}px;
        font-weight: bold;
        color: {COLOR_PRIMARY};
    }}
    
    QLabel.header {{
        font-size: {FONT_SIZE_HEADER}px;
        font-weight: bold;
        color: {TEXT_PRIMARY};
    }}
    
    QLabel.subtitle {{
        font-size: {FONT_SIZE_LARGE}px;
        font-weight: bold;
        color: {TEXT_SECONDARY};
    }}
    
    QLabel.caption {{
        font-size: {FONT_SIZE_SMALL}px;
        color: {TEXT_SECONDARY};
    }}
    
    /* 进度条样式 */
    QProgressBar {{
        border: 1px solid {BORDER_MEDIUM};
        border-radius: 4px;
        text-align: center;
        background-color: {BG_DARK};
        font-size: {FONT_SIZE_NORMAL}px;
        height: 20px;
    }}
    
    QProgressBar::chunk {{
        background-color: {COLOR_PRIMARY};
        border-radius: 3px;
    }}
    
    /* 滚动条样式 */
    QScrollBar:vertical {{
        border: none;
        background-color: {BG_DARK};
        width: 12px;
        border-radius: 6px;
    }}
    
    QScrollBar::handle:vertical {{
        background-color: {COLOR_SECONDARY};
        border-radius: 6px;
        min-height: 20px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background-color: {COLOR_PRIMARY};
    }}
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    
    QScrollBar:horizontal {{
        border: none;
        background-color: {BG_DARK};
        height: 12px;
        border-radius: 6px;
    }}
    
    QScrollBar::handle:horizontal {{
        background-color: {COLOR_SECONDARY};
        border-radius: 6px;
        min-width: 20px;
    }}
    
    QScrollBar::handle:horizontal:hover {{
        background-color: {COLOR_PRIMARY};
    }}
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    
    /* 菜单栏样式 */
    QMenuBar {{
        background-color: {BG_DARK};
        border-bottom: 1px solid {BORDER_LIGHT};
        padding: 2px;
    }}
    
    QMenuBar::item {{
        padding: 6px 12px;
        background-color: transparent;
        border-radius: 2px;
    }}
    
    QMenuBar::item:selected {{
        background-color: #E1DFDD;
    }}
    
    QMenuBar::item:pressed {{
        background-color: {COLOR_PRIMARY};
        color: {TEXT_LIGHT};
    }}
    
    /* 菜单样式 */
    QMenu {{
        background-color: {BG_LIGHT};
        border: 1px solid {BORDER_MEDIUM};
        padding: 4px;
    }}
    
    QMenu::item {{
        padding: 6px 24px 6px 12px;
    }}
    
    QMenu::item:selected {{
        background-color: {COLOR_PRIMARY};
        color: {TEXT_LIGHT};
    }}
    
    QMenu::separator {{
        height: 1px;
        background-color: {BORDER_LIGHT};
        margin: 4px 0px;
    }}
    
    /* 状态栏样式 */
    QStatusBar {{
        background-color: {BG_DARK};
        border-top: 1px solid {BORDER_LIGHT};
        padding: 4px;
        font-size: {FONT_SIZE_SMALL}px;
    }}
    
    /* 分组框样式 */
    QGroupBox {{
        border: 1px solid {BORDER_MEDIUM};
        border-radius: 4px;
        margin-top: 12px;
        padding-top: 12px;
        font-weight: bold;
        font-size: {FONT_SIZE_LARGE}px;
        color: {COLOR_PRIMARY};
    }}
    
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px 0 6px;
    }}
    
    /* 工具提示样式 */
    QToolTip {{
        background-color: #323130;
        color: white;
        border: 1px solid #323130;
        padding: 6px;
        border-radius: 2px;
        font-size: {FONT_SIZE_SMALL}px;
    }}
    
    /* 复选框样式 */
    QCheckBox, QRadioButton {{
        spacing: 8px;
        font-size: {FONT_SIZE_NORMAL}px;
    }}
    
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 18px;
        height: 18px;
    }}
    
    QCheckBox::indicator:unchecked {{
        border: 2px solid {BORDER_MEDIUM};
        background-color: {BG_LIGHT};
        border-radius: 2px;
    }}
    
    QCheckBox::indicator:checked {{
        border: 2px solid {COLOR_PRIMARY};
        background-color: {COLOR_PRIMARY};
        border-radius: 2px;
        image: url(:/icons/checkmark.png);
    }}
    
    QCheckBox::indicator:disabled {{
        border: 2px solid {COLOR_DISABLED};
        background-color: {BG_DARK};
    }}
    
    QRadioButton::indicator:unchecked {{
        border: 2px solid {BORDER_MEDIUM};
        background-color: {BG_LIGHT};
        border-radius: 9px;
    }}
    
    QRadioButton::indicator:checked {{
        border: 2px solid {COLOR_PRIMARY};
        background-color: {COLOR_PRIMARY};
        border-radius: 9px;
        image: url(:/icons/dot.png);
    }}
    
    QRadioButton::indicator:disabled {{
        border: 2px solid {COLOR_DISABLED};
        background-color: {BG_DARK};
    }}
    
    /* 滑块样式 */
    QSlider::groove:horizontal {{
        border: 1px solid {BORDER_MEDIUM};
        height: 6px;
        background-color: {BG_DARK};
        border-radius: 3px;
    }}
    
    QSlider::handle:horizontal {{
        background-color: {COLOR_PRIMARY};
        border: 1px solid {COLOR_PRIMARY};
        width: 18px;
        height: 18px;
        margin: -6px 0;
        border-radius: 9px;
    }}
    
    QSlider::handle:horizontal:hover {{
        background-color: #106EBE;
        border-color: #106EBE;
    }}
    
    /* 分隔线样式 */
    QFrame[frameShape="4"], QFrame[frameShape="5"] {{ /* HLine and VLine */
        background-color: {BORDER_LIGHT};
    }}
    
    /* 工具栏样式 */
    QToolBar {{
        background-color: {BG_DARK};
        border-bottom: 1px solid {BORDER_LIGHT};
        spacing: 4px;
        padding: 4px;
    }}
    
    QToolBar::separator {{
        background-color: {BORDER_LIGHT};
        width: 1px;
        margin: 0px 4px;
    }}
    
    /* 列表视图样式 */
    QListView, QListWidget {{
        background-color: {BG_LIGHT};
        border: 1px solid {BORDER_MEDIUM};
        border-radius: 2px;
        padding: 2px;
        font-size: {FONT_SIZE_NORMAL}px;
    }}
    
    QListView::item, QListWidget::item {{
        padding: 6px;
        border-bottom: 1px solid {BORDER_LIGHT};
    }}
    
    QListView::item:selected, QListWidget::item:selected {{
        background-color: {COLOR_PRIMARY};
        color: {TEXT_LIGHT};
        border: none;
    }}
    
    QListView::item:hover, QListWidget::item:hover {{
        background-color: #E1DFDD;
    }}
    
    /* 树视图样式 */
    QTreeView, QTreeWidget {{
        background-color: {BG_LIGHT};
        border: 1px solid {BORDER_MEDIUM};
        border-radius: 2px;
        font-size: {FONT_SIZE_NORMAL}px;
    }}
    
    QTreeView::item, QTreeWidget::item {{
        padding: 4px;
    }}
    
    QTreeView::item:selected, QTreeWidget::item:selected {{
        background-color: {COLOR_PRIMARY};
        color: {TEXT_LIGHT};
    }}
    
    QTreeView::item:hover, QTreeWidget::item:hover {{
        background-color: #E1DFDD;
    }}
    
    /* 停靠窗口样式 */
    QDockWidget {{
        titlebar-close-icon: url(:/icons/close.png);
        titlebar-normal-icon: url(:/icons/restore.png);
    }}
    
    QDockWidget::title {{
        background-color: {BG_DARK};
        padding: 6px;
        border-bottom: 1px solid {BORDER_LIGHT};
    }}
    
    QDockWidget::close-button, QDockWidget::float-button {{
        border: none;
        padding: 0px;
        background: transparent;
    }}
    
    /* 消息框样式 */
    QMessageBox {{
        background-color: {BG_LIGHT};
    }}
    
    QMessageBox QLabel {{
        font-size: {FONT_SIZE_NORMAL}px;
    }}
    
    /* 自定义类样式 */
    
    /* 状态指示器 */
    StatusIndicator {{
        qproperty-indicatorSize: 12;
        qproperty-indicatorMargin: 4;
    }}
    
    StatusIndicator[status="connected"] {{
        qproperty-indicatorColor: {COLOR_SUCCESS};
    }}
    
    StatusIndicator[status="disconnected"] {{
        qproperty-indicatorColor: {COLOR_ERROR};
    }}
    
    StatusIndicator[status="connecting"] {{
        qproperty-indicatorColor: {COLOR_WARNING};
    }}
    
    StatusIndicator[status="error"] {{
        qproperty-indicatorColor: {COLOR_ERROR};
    }}
    
    /* 控制台输出 */
    ConsoleOutput {{
        font-family: "Consolas", "Courier New", monospace;
        font-size: {FONT_SIZE_SMALL}px;
        background-color: #1E1E1E;
        color: #D4D4D4;
    }}
    
    /* 十六进制查看器 */
    HexViewer {{
        font-family: "Consolas", "Courier New", monospace;
        font-size: {FONT_SIZE_SMALL}px;
        background-color: #1E1E1E;
        color: #D4D4D4;
    }}
    
    /* 波形图 */
    WaveformPlot {{
        background-color: #1E1E1E;
        border: 1px solid {BORDER_MEDIUM};
    }}
    
    /* 仪表盘 */
    GaugeWidget {{
        background-color: {BG_LIGHT};
        border: 1px solid {BORDER_MEDIUM};
        border-radius: 8px;
    }}
    """

def get_dark_theme_stylesheet() -> str:
    """获取暗色主题样式表"""
    dark_bg = "#1E1E1E"
    dark_bg_light = "#252526"
    dark_bg_dark = "#181818"
    dark_text = "#CCCCCC"
    dark_text_light = "#FFFFFF"
    dark_text_disabled = "#666666"
    dark_border = "#3E3E40"
    dark_primary = "#007ACC"
    
    return f"""
    /* 暗色主题样式表 */
    QMainWindow {{
        background-color: {dark_bg};
    }}
    
    QWidget {{
        background-color: {dark_bg};
        color: {dark_text};
        font-family: "{FONT_FAMILY}", "Microsoft YaHei", sans-serif;
        font-size: {FONT_SIZE_NORMAL}px;
    }}
    
    QPushButton {{
        background-color: {dark_primary};
        color: {dark_text_light};
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: bold;
        font-size: {FONT_SIZE_NORMAL}px;
        min-height: 32px;
        min-width: 80px;
    }}
    
    QPushButton:hover {{
        background-color: #1C8FD6;
    }}
    
    QPushButton:pressed {{
        background-color: #005A9E;
    }}
    
    QPushButton:disabled {{
        background-color: #3E3E40;
        color: {dark_text_disabled};
    }}
    
    QLineEdit, QTextEdit, QPlainTextEdit {{
        border: 1px solid {dark_border};
        border-radius: 2px;
        padding: 6px 8px;
        background-color: {dark_bg_light};
        selection-background-color: {dark_primary};
        selection-color: {dark_text_light};
        font-size: {FONT_SIZE_NORMAL}px;
    }}
    
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border: 2px solid {dark_primary};
        padding: 5px 7px;
    }}
    
    QTableView, QTableWidget {{
        background-color: {dark_bg_light};
        alternate-background-color: {dark_bg};
        gridline-color: {dark_border};
        selection-background-color: {dark_primary};
        selection-color: {dark_text_light};
        border: 1px solid {dark_border};
    }}
    
    QHeaderView::section {{
        background-color: {dark_bg_dark};
        color: {dark_text};
        padding: 8px;
        border: 1px solid {dark_border};
    }}
    
    QTabWidget::pane {{
        border: 1px solid {dark_border};
        background-color: {dark_bg};
    }}
    
    QTabBar::tab {{
        background-color: {dark_bg_dark};
        color: {dark_text};
        padding: 8px 16px;
        margin-right: 2px;
        border: 1px solid {dark_border};
        border-bottom: none;
    }}
    
    QTabBar::tab:selected {{
        background-color: {dark_bg};
        border-bottom: 2px solid {dark_primary};
    }}
    
    QLabel {{
        color: {dark_text};
    }}
    
    QGroupBox {{
        border: 1px solid {dark_border};
        color: {dark_text_light};
    }}
    
    QMenuBar {{
        background-color: {dark_bg_dark};
        color: {dark_text};
    }}
    
    QMenu {{
        background-color: {dark_bg_dark};
        color: {dark_text};
        border: 1px solid {dark_border};
    }}
    
    QStatusBar {{
        background-color: {dark_bg_dark};
        color: {dark_text};
    }}
    
    QScrollBar:vertical {{
        background-color: {dark_bg_dark};
    }}
    
    QScrollBar::handle:vertical {{
        background-color: {dark_border};
    }}
    """

def get_stylesheet(theme: str = "light") -> str:
    """
    获取样式表
    
    Args:
        theme: 主题名称 (light/dark)
        
    Returns:
        str: 样式表内容
    """
    if theme == "dark":
        return get_dark_theme_stylesheet()
    else:
        return get_light_theme_stylesheet()

def apply_palette(app, theme: str = "light"):
    """
    应用调色板
    
    Args:
        app: QApplication实例
        theme: 主题名称
    """
    palette = QPalette()
    
    if theme == "dark":
        # 暗色主题调色板
        palette.setColor(QPalette.Window, QColor("#1E1E1E"))
        palette.setColor(QPalette.WindowText, QColor("#CCCCCC"))
        palette.setColor(QPalette.Base, QColor("#252526"))
        palette.setColor(QPalette.AlternateBase, QColor("#1E1E1E"))
        palette.setColor(QPalette.ToolTipBase, QColor("#323232"))
        palette.setColor(QPalette.ToolTipText, QColor("#CCCCCC"))
        palette.setColor(QPalette.Text, QColor("#CCCCCC"))
        palette.setColor(QPalette.Button, QColor("#3E3E40"))
        palette.setColor(QPalette.ButtonText, QColor("#CCCCCC"))
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor("#007ACC"))
        palette.setColor(QPalette.Highlight, QColor("#007ACC"))
        palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    else:
        # 明亮主题调色板
        palette.setColor(QPalette.Window, QColor(BG_LIGHT))
        palette.setColor(QPalette.WindowText, QColor(TEXT_PRIMARY))
        palette.setColor(QPalette.Base, QColor(BG_LIGHT))
        palette.setColor(QPalette.AlternateBase, QColor(BG_ALTERNATE))
        palette.setColor(QPalette.ToolTipBase, QColor("#323130"))
        palette.setColor(QPalette.ToolTipText, QColor("#FFFFFF"))
        palette.setColor(QPalette.Text, QColor(TEXT_PRIMARY))
        palette.setColor(QPalette.Button, QColor(BG_DARK))
        palette.setColor(QPalette.ButtonText, QColor(TEXT_PRIMARY))
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(COLOR_PRIMARY))
        palette.setColor(QPalette.Highlight, QColor(COLOR_PRIMARY))
        palette.setColor(QPalette.HighlightedText, QColor(TEXT_LIGHT))
    
    app.setPalette(palette)

def setup_theme(app, theme: str = "light"):
    """
    设置应用程序主题
    
    Args:
        app: QApplication实例
        theme: 主题名称
    """
    # 应用调色板
    apply_palette(app, theme)
    
    # 应用样式表
    stylesheet = get_stylesheet(theme)
    app.setStyleSheet(stylesheet)
    
    # 设置高DPI缩放
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)