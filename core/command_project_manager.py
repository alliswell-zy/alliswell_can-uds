#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令工程管理器 - 管理命令工程和发送任务
支持CAN帧、UDS帧的发送，支持周期性发送和单次发送
"""

import logging
import time
import threading
import json
import queue
from enum import Enum
from typing import Optional, Dict, List, Any, Tuple, Union, Callable
from dataclasses import dataclass, field, asdict
from dataclasses_json import dataclass_json
import copy

from .can_interface import CANFrame, CANInterfaceManager
from .uds_session_manager import UDSSessionManager, UDSRequest, UDSResponse
from .isotp_protocol import ISOTPConfig
from config.protocol_definitions import ProtocolDefinitions, UDSServiceDefinition

logger = logging.getLogger(__name__)

class CommandType(Enum):
    """命令类型"""
    CAN_FRAME = "can_frame"
    UDS_COMMAND = "uds_command"
    WAIT = "wait"
    COMMENT = "comment"
    SCRIPT = "script"

class SendMode(Enum):
    """发送模式"""
    SINGLE = "single"      # 单次发送
    PERIODIC = "periodic"  # 周期性发送
    ON_CHANGE = "on_change"  # 变化时发送

class CommandStatus(Enum):
    """命令状态"""
    PENDING = "pending"     # 等待执行
    RUNNING = "running"     # 正在执行
    SUCCESS = "success"     # 执行成功
    FAILED = "failed"       # 执行失败
    STOPPED = "stopped"     # 已停止

@dataclass_json
@dataclass
class CANFrameCommand:
    """CAN帧命令"""
    arbitration_id: int = 0x000
    data: bytes = field(default_factory=bytes)
    is_extended_id: bool = False
    is_fd: bool = False
    bitrate_switch: bool = False
    error_state_indicator: bool = False
    dlc: int = 8
    comment: str = ""
    
    def to_can_frame(self) -> CANFrame:
        """转换为CANFrame对象"""
        return CANFrame(
            timestamp=time.time(),
            arbitration_id=self.arbitration_id,
            data=self.data,
            is_extended_id=self.is_extended_id,
            is_fd=self.is_fd,
            bitrate_switch=self.bitrate_switch,
            error_state_indicator=self.error_state_indicator,
            dlc=self.dlc
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CANFrameCommand':
        """从字典创建"""
        if isinstance(data.get('data'), str):
            # 十六进制字符串转bytes
            hex_str = data['data'].replace(' ', '')
            data['data'] = bytes.fromhex(hex_str)
        return cls(**data)

@dataclass_json
@dataclass
class UDSCommand:
    """UDS命令"""
    service_id: int = 0x00
    data: bytes = field(default_factory=bytes)
    subfunction: Optional[int] = None
    timeout: int = 2000
    expect_response: bool = True
    comment: str = ""
    
    def to_uds_request(self) -> UDSRequest:
        """转换为UDSRequest对象"""
        return UDSRequest(
            service_id=self.service_id,
            data=self.data,
            subfunction=self.subfunction,
            timeout=self.timeout,
            expect_response=self.expect_response
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UDSCommand':
        """从字典创建"""
        if isinstance(data.get('data'), str):
            # 十六进制字符串转bytes
            hex_str = data['data'].replace(' ', '')
            data['data'] = bytes.fromhex(hex_str)
        return cls(**data)

@dataclass_json
@dataclass
class WaitCommand:
    """等待命令"""
    duration: int = 1000  # 毫秒
    comment: str = ""

@dataclass_json
@dataclass
class CommentCommand:
    """注释命令"""
    comment: str = ""

@dataclass_json
@dataclass
class ScriptCommand:
    """脚本命令"""
    script_code: str = ""
    comment: str = ""

@dataclass_json
@dataclass
class Command:
    """命令项"""
    id: str
    name: str
    command_type: CommandType
    send_mode: SendMode = SendMode.SINGLE
    period: int = 1000  # 毫秒，用于周期性发送
    enabled: bool = True
    status: CommandStatus = CommandStatus.PENDING
    last_executed: float = 0
    execution_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    
    # 命令数据
    can_frame: Optional[CANFrameCommand] = None
    uds_command: Optional[UDSCommand] = None
    wait_command: Optional[WaitCommand] = None
    comment_command: Optional[CommentCommand] = None
    script_command: Optional[ScriptCommand] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['command_type'] = self.command_type.value
        data['send_mode'] = self.send_mode.value
        data['status'] = self.status.value
        
        # 清理None值
        if self.can_frame:
            data['can_frame'] = self.can_frame.to_dict()
        else:
            data.pop('can_frame', None)
            
        if self.uds_command:
            data['uds_command'] = self.uds_command.to_dict()
        else:
            data.pop('uds_command', None)
            
        if self.wait_command:
            data['wait_command'] = self.wait_command.to_dict()
        else:
            data.pop('wait_command', None)
            
        if self.comment_command:
            data['comment_command'] = self.comment_command.to_dict()
        else:
            data.pop('comment_command', None)
            
        if self.script_command:
            data['script_command'] = self.script_command.to_dict()
        else:
            data.pop('script_command', None)
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Command':
        """从字典创建"""
        # 转换枚举值
        data['command_type'] = CommandType(data['command_type'])
        data['send_mode'] = SendMode(data['send_mode'])
        data['status'] = CommandStatus(data['status'])
        
        # 创建子命令对象
        if data.get('can_frame'):
            data['can_frame'] = CANFrameCommand.from_dict(data['can_frame'])
        if data.get('uds_command'):
            data['uds_command'] = UDSCommand.from_dict(data['uds_command'])
        if data.get('wait_command'):
            data['wait_command'] = WaitCommand(**data['wait_command'])
        if data.get('comment_command'):
            data['comment_command'] = CommentCommand(**data['comment_command'])
        if data.get('script_command'):
            data['script_command'] = ScriptCommand(**data['script_command'])
        
        return cls(**data)

@dataclass_json
@dataclass
class CommandGroup:
    """命令组"""
    id: str
    name: str
    description: str = ""
    enabled: bool = True
    commands: List[Command] = field(default_factory=list)
    repeat_count: int = 1  # 重复次数，0表示无限重复
    repeat_interval: int = 1000  # 重复间隔（毫秒）
    run_in_sequence: bool = True  # 是否顺序执行
    
    def add_command(self, command: Command) -> None:
        """添加命令"""
        self.commands.append(command)
    
    def remove_command(self, command_id: str) -> bool:
        """移除命令"""
        for i, cmd in enumerate(self.commands):
            if cmd.id == command_id:
                self.commands.pop(i)
                return True
        return False
    
    def get_command(self, command_id: str) -> Optional[Command]:
        """获取命令"""
        for cmd in self.commands:
            if cmd.id == command_id:
                return cmd
        return None

@dataclass_json
@dataclass
class CommandProject:
    """命令工程"""
    id: str
    name: str
    description: str = ""
    version: str = "1.0"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    groups: List[CommandGroup] = field(default_factory=list)
    
    def add_group(self, group: CommandGroup) -> None:
        """添加组"""
        self.groups.append(group)
    
    def remove_group(self, group_id: str) -> bool:
        """移除组"""
        for i, group in enumerate(self.groups):
            if group.id == group_id:
                self.groups.pop(i)
                return True
        return False
    
    def get_group(self, group_id: str) -> Optional[CommandGroup]:
        """获取组"""
        for group in self.groups:
            if group.id == group_id:
                return group
        return None

class CommandExecutor:
    """命令执行器"""
    
    def __init__(self, can_manager: CANInterfaceManager, uds_manager: UDSSessionManager = None):
        """
        初始化命令执行器
        
        Args:
            can_manager: CAN接口管理器
            uds_manager: UDS会话管理器
        """
        self.can_manager = can_manager
        self.uds_manager = uds_manager
        self.protocol_defs = ProtocolDefinitions()
        
        # 执行状态
        self.running = False
        self.current_project: Optional[CommandProject] = None
        self.current_group: Optional[CommandGroup] = None
        self.current_command: Optional[Command] = None
        
        # 回调函数
        self.on_command_started = None
        self.on_command_completed = None
        self.on_command_failed = None
        self.on_group_started = None
        self.on_group_completed = None
        self.on_project_started = None
        self.on_project_completed = None
        
        # 线程管理
        self.execution_thread: Optional[threading.Thread] = None
        self.periodic_threads: Dict[str, threading.Thread] = {}
        self.stop_event = threading.Event()
        
        logger.info("Command executor initialized")
    
    def start_project(self, project: CommandProject, interface_id: str = "default") -> bool:
        """
        开始执行命令工程
        
        Args:
            project: 命令工程
            interface_id: CAN接口ID
            
        Returns:
            bool: 是否成功启动
        """
        if self.running:
            logger.warning("Executor is already running")
            return False
        
        self.current_project = project
        self.interface_id = interface_id
        self.running = True
        self.stop_event.clear()
        
        # 调用项目开始回调
        if self.on_project_started:
            try:
                self.on_project_started(project)
            except Exception as e:
                logger.error(f"Error in project started callback: {e}")
        
        # 启动执行线程
        self.execution_thread = threading.Thread(
            target=self._execute_project,
            daemon=True,
            name=f"CommandExecutor-{project.id}"
        )
        self.execution_thread.start()
        
        logger.info(f"Started project '{project.name}'")
        return True
    
    def stop_project(self) -> bool:
        """停止执行命令工程"""
        if not self.running:
            return False
        
        self.running = False
        self.stop_event.set()
        
        # 停止所有周期性线程
        for thread_id, thread in list(self.periodic_threads.items()):
            if thread.is_alive():
                thread.join(timeout=1.0)
            self.periodic_threads.pop(thread_id, None)
        
        # 等待执行线程结束
        if self.execution_thread and self.execution_thread.is_alive():
            self.execution_thread.join(timeout=2.0)
        
        # 重置状态
        self.current_project = None
        self.current_group = None
        self.current_command = None
        
        logger.info("Project execution stopped")
        return True
    
    def _execute_project(self) -> None:
        """执行项目线程函数"""
        try:
            project = self.current_project
            if not project:
                return
            
            # 更新项目信息
            project.updated_at = time.time()
            
            # 执行每个组
            for group in project.groups:
                if not group.enabled or self.stop_event.is_set():
                    continue
                
                self.current_group = group
                
                # 调用组开始回调
                if self.on_group_started:
                    try:
                        self.on_group_started(group)
                    except Exception as e:
                        logger.error(f"Error in group started callback: {e}")
                
                # 执行组
                self._execute_group(group)
                
                # 调用组完成回调
                if self.on_group_completed:
                    try:
                        self.on_group_completed(group)
                    except Exception as e:
                        logger.error(f"Error in group completed callback: {e}")
                
                # 检查是否停止
                if self.stop_event.is_set():
                    break
                
                # 组间等待（如果设置了重复间隔）
                if group.repeat_interval > 0 and not self.stop_event.is_set():
                    time.sleep(group.repeat_interval / 1000.0)
            
            # 项目执行完成
            self.running = False
            
            # 调用项目完成回调
            if self.on_project_completed:
                try:
                    self.on_project_completed(project)
                except Exception as e:
                    logger.error(f"Error in project completed callback: {e}")
            
            logger.info(f"Project '{project.name}' execution completed")
            
        except Exception as e:
            logger.error(f"Error executing project: {e}")
            self.running = False
    
    def _execute_group(self, group: CommandGroup) -> None:
        """执行命令组"""
        repeat_count = 0
        
        while repeat_count < group.repeat_count or group.repeat_count == 0:
            if self.stop_event.is_set():
                break
            
            # 执行组内命令
            for command in group.commands:
                if not command.enabled or self.stop_event.is_set():
                    continue
                
                self.current_command = command
                
                try:
                    # 调用命令开始回调
                    if self.on_command_started:
                        try:
                            self.on_command_started(command)
                        except Exception as e:
                            logger.error(f"Error in command started callback: {e}")
                    
                    # 执行命令
                    success = self._execute_command(command)
                    
                    # 更新命令状态
                    command.last_executed = time.time()
                    command.execution_count += 1
                    
                    if success:
                        command.status = CommandStatus.SUCCESS
                        command.success_count += 1
                        
                        # 调用命令完成回调
                        if self.on_command_completed:
                            try:
                                self.on_command_completed(command, None)
                            except Exception as e:
                                logger.error(f"Error in command completed callback: {e}")
                    else:
                        command.status = CommandStatus.FAILED
                        command.fail_count += 1
                        
                        # 调用命令失败回调
                        if self.on_command_failed:
                            try:
                                self.on_command_failed(command, "Execution failed")
                            except Exception as e:
                                logger.error(f"Error in command failed callback: {e}")
                    
                except Exception as e:
                    logger.error(f"Error executing command '{command.name}': {e}")
                    command.status = CommandStatus.FAILED
                    command.fail_count += 1
                
                # 检查是否需要停止
                if self.stop_event.is_set():
                    break
            
            repeat_count += 1
            
            # 如果不是无限重复且已达到重复次数，则退出
            if group.repeat_count > 0 and repeat_count >= group.repeat_count:
                break
    
    def _execute_command(self, command: Command) -> bool:
        """执行单个命令"""
        try:
            if command.command_type == CommandType.CAN_FRAME and command.can_frame:
                return self._execute_can_frame_command(command)
            elif command.command_type == CommandType.UDS_COMMAND and command.uds_command:
                return self._execute_uds_command(command)
            elif command.command_type == CommandType.WAIT and command.wait_command:
                return self._execute_wait_command(command)
            elif command.command_type == CommandType.COMMENT and command.comment_command:
                return self._execute_comment_command(command)
            elif command.command_type == CommandType.SCRIPT and command.script_command:
                return self._execute_script_command(command)
            else:
                logger.warning(f"Unknown or invalid command type: {command.command_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error in command execution: {e}")
            return False
    
    def _execute_can_frame_command(self, command: Command) -> bool:
        """执行CAN帧命令"""
        can_frame_cmd = command.can_frame
        if not can_frame_cmd:
            return False
        
        # 创建CAN帧
        can_frame = can_frame_cmd.to_can_frame()
        
        # 根据发送模式处理
        if command.send_mode == SendMode.SINGLE:
            # 单次发送
            success = self.can_manager.send_frame(self.interface_id, can_frame)
            logger.debug(f"Sent CAN frame: ID={can_frame.id_hex}, success={success}")
            return success
            
        elif command.send_mode == SendMode.PERIODIC:
            # 周期性发送 - 启动后台线程
            thread = threading.Thread(
                target=self._periodic_can_frame_sender,
                args=(command, can_frame),
                daemon=True,
                name=f"PeriodicCAN-{command.id}"
            )
            self.periodic_threads[command.id] = thread
            thread.start()
            return True
            
        else:
            logger.warning(f"Unsupported send mode for CAN frame: {command.send_mode}")
            return False
    
    def _periodic_can_frame_sender(self, command: Command, can_frame: CANFrame) -> None:
        """周期性发送CAN帧"""
        try:
            command.status = CommandStatus.RUNNING
            
            while self.running and not self.stop_event.is_set():
                # 发送CAN帧
                success = self.can_manager.send_frame(self.interface_id, can_frame)
                
                # 更新统计
                command.last_executed = time.time()
                command.execution_count += 1
                if success:
                    command.success_count += 1
                else:
                    command.fail_count += 1
                
                # 等待下一个周期
                time.sleep(command.period / 1000.0)
            
            command.status = CommandStatus.STOPPED
            
        except Exception as e:
            logger.error(f"Error in periodic CAN frame sender: {e}")
            command.status = CommandStatus.FAILED
    
    def _execute_uds_command(self, command: Command) -> bool:
        """执行UDS命令"""
        uds_cmd = command.uds_command
        if not uds_cmd or not self.uds_manager:
            return False
        
        # 创建UDS请求
        uds_request = uds_cmd.to_uds_request()
        
        # 根据发送模式处理
        if command.send_mode == SendMode.SINGLE:
            # 单次发送
            response = self.uds_manager.send_request(uds_request)
            
            if response:
                success = response.is_positive
                logger.debug(f"Sent UDS command: SID=0x{uds_cmd.service_id:02X}, success={success}")
                
                # 如果命令期望响应但没有收到，视为失败
                if uds_cmd.expect_response and not response:
                    success = False
                
                return success
            else:
                # 超时或无响应
                return not uds_cmd.expect_response  # 如果不期望响应，则超时不算失败
            
        elif command.send_mode == SendMode.PERIODIC:
            # 周期性发送 - 启动后台线程
            thread = threading.Thread(
                target=self._periodic_uds_command_sender,
                args=(command, uds_request),
                daemon=True,
                name=f"PeriodicUDS-{command.id}"
            )
            self.periodic_threads[command.id] = thread
            thread.start()
            return True
            
        else:
            logger.warning(f"Unsupported send mode for UDS command: {command.send_mode}")
            return False
    
    def _periodic_uds_command_sender(self, command: Command, uds_request: UDSRequest) -> None:
        """周期性发送UDS命令"""
        try:
            command.status = CommandStatus.RUNNING
            
            while self.running and not self.stop_event.is_set():
                # 发送UDS命令
                response = self.uds_manager.send_request(uds_request)
                
                # 更新统计
                command.last_executed = time.time()
                command.execution_count += 1
                
                if response and response.is_positive:
                    command.success_count += 1
                    command.status = CommandStatus.SUCCESS
                elif not uds_request.expect_response:
                    # 不期望响应的情况
                    command.success_count += 1
                    command.status = CommandStatus.SUCCESS
                else:
                    command.fail_count += 1
                    command.status = CommandStatus.FAILED
                
                # 等待下一个周期
                time.sleep(command.period / 1000.0)
            
            command.status = CommandStatus.STOPPED
            
        except Exception as e:
            logger.error(f"Error in periodic UDS command sender: {e}")
            command.status = CommandStatus.FAILED
    
    def _execute_wait_command(self, command: Command) -> bool:
        """执行等待命令"""
        wait_cmd = command.wait_command
        if not wait_cmd:
            return False
        
        try:
            # 计算等待时间（毫秒）
            wait_time = wait_cmd.duration / 1000.0
            
            # 等待指定时间
            time.sleep(wait_time)
            
            logger.debug(f"Wait command executed: {wait_cmd.duration}ms")
            return True
            
        except Exception as e:
            logger.error(f"Error in wait command: {e}")
            return False
    
    def _execute_comment_command(self, command: Command) -> bool:
        """执行注释命令"""
        comment_cmd = command.comment_command
        if not comment_cmd:
            return False
        
        logger.debug(f"Comment: {comment_cmd.comment}")
        return True  # 注释命令总是成功
    
    def _execute_script_command(self, command: Command) -> bool:
        """执行脚本命令"""
        script_cmd = command.script_command
        if not script_cmd:
            return False
        
        try:
            # 这里可以实现脚本执行逻辑
            # 由于安全考虑，默认不执行脚本
            logger.warning("Script execution is disabled by default for security reasons")
            
            # 如果要启用脚本执行，可以在这里添加代码
            # exec(script_cmd.script_code, {})
            
            return True
            
        except Exception as e:
            logger.error(f"Error executing script: {e}")
            return False
    
    def send_single_can_frame(self, can_frame_cmd: CANFrameCommand, interface_id: str = "default") -> bool:
        """
        发送单个CAN帧
        
        Args:
            can_frame_cmd: CAN帧命令
            interface_id: CAN接口ID
            
        Returns:
            bool: 发送是否成功
        """
        can_frame = can_frame_cmd.to_can_frame()
        return self.can_manager.send_frame(interface_id, can_frame)
    
    def send_single_uds_command(self, uds_cmd: UDSCommand) -> Optional[UDSResponse]:
        """
        发送单个UDS命令
        
        Args:
            uds_cmd: UDS命令
            
        Returns:
            UDSResponse or None: 响应
        """
        if not self.uds_manager:
            logger.error("UDS manager not available")
            return None
        
        uds_request = uds_cmd.to_uds_request()
        return self.uds_manager.send_request(uds_request)
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.running
    
    def get_current_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        status = {
            'running': self.running,
            'current_project': self.current_project.name if self.current_project else None,
            'current_group': self.current_group.name if self.current_group else None,
            'current_command': self.current_command.name if self.current_command else None,
            'periodic_threads': len(self.periodic_threads),
        }
        
        return status
    
    def stop_periodic_command(self, command_id: str) -> bool:
        """停止周期性命令"""
        if command_id in self.periodic_threads:
            thread = self.periodic_threads.pop(command_id, None)
            if thread and thread.is_alive():
                # 标记停止，线程会在下次循环时退出
                return True
        
        return False
    
    def stop_all_periodic_commands(self) -> None:
        """停止所有周期性命令"""
        for command_id in list(self.periodic_threads.keys()):
            self.stop_periodic_command(command_id)

class CommandProjectManager:
    """命令工程管理器"""
    
    def __init__(self, can_manager: CANInterfaceManager, uds_manager: UDSSessionManager = None):
        """
        初始化命令工程管理器
        
        Args:
            can_manager: CAN接口管理器
            uds_manager: UDS会话管理器
        """
        self.can_manager = can_manager
        self.uds_manager = uds_manager
        
        # 命令工程存储
        self.projects: Dict[str, CommandProject] = {}
        self.current_project_id: Optional[str] = None
        
        # 命令执行器
        self.executor = CommandExecutor(can_manager, uds_manager)
        
        # 文件路径
        self.projects_dir = "projects"
        
        logger.info("Command project manager initialized")
    
    def create_project(self, project_id: str, name: str, description: str = "") -> Optional[CommandProject]:
        """
        创建命令工程
        
        Args:
            project_id: 工程ID
            name: 工程名称
            description: 工程描述
            
        Returns:
            CommandProject or None: 创建的工程
        """
        if project_id in self.projects:
            logger.warning(f"Project '{project_id}' already exists")
            return self.projects[project_id]
        
        project = CommandProject(
            id=project_id,
            name=name,
            description=description,
            created_at=time.time(),
            updated_at=time.time()
        )
        
        self.projects[project_id] = project
        self.current_project_id = project_id
        
        logger.info(f"Created project '{name}' (ID: {project_id})")
        return project
    
    def load_project(self, file_path: str) -> Optional[CommandProject]:
        """
        从文件加载命令工程
        
        Args:
            file_path: 文件路径
            
        Returns:
            CommandProject or None: 加载的工程
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 验证数据格式
            if 'id' not in data or 'name' not in data:
                logger.error("Invalid project file format")
                return None
            
            # 创建工程对象
            project = CommandProject.from_dict(data)
            
            # 添加到管理器
            self.projects[project.id] = project
            self.current_project_id = project.id
            
            logger.info(f"Loaded project '{project.name}' from '{file_path}'")
            return project
            
        except Exception as e:
            logger.error(f"Error loading project from '{file_path}': {e}")
            return None
    
    def save_project(self, project_id: str, file_path: str) -> bool:
        """
        保存命令工程到文件
        
        Args:
            project_id: 工程ID
            file_path: 文件路径
            
        Returns:
            bool: 是否保存成功
        """
        project = self.get_project(project_id)
        if not project:
            logger.error(f"Project '{project_id}' not found")
            return False
        
        try:
            # 更新修改时间
            project.updated_at = time.time()
            
            # 转换为字典
            data = project.to_dict()
            
            # 保存到文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved project '{project.name}' to '{file_path}'")
            return True
            
        except Exception as e:
            logger.error(f"Error saving project to '{file_path}': {e}")
            return False
    
    def get_project(self, project_id: str) -> Optional[CommandProject]:
        """
        获取命令工程
        
        Args:
            project_id: 工程ID
            
        Returns:
            CommandProject or None: 工程
        """
        return self.projects.get(project_id)
    
    def get_current_project(self) -> Optional[CommandProject]:
        """获取当前工程"""
        if self.current_project_id:
            return self.projects.get(self.current_project_id)
        return None
    
    def remove_project(self, project_id: str) -> bool:
        """
        移除命令工程
        
        Args:
            project_id: 工程ID
            
        Returns:
            bool: 是否移除成功
        """
        if project_id not in self.projects:
            return False
        
        # 如果正在执行，先停止
        if self.executor.is_running() and self.executor.current_project and self.executor.current_project.id == project_id:
            self.executor.stop_project()
        
        # 移除工程
        del self.projects[project_id]
        
        # 如果移除的是当前工程，清空当前工程ID
        if self.current_project_id == project_id:
            self.current_project_id = None
        
        logger.info(f"Removed project '{project_id}'")
        return True
    
    def start_project(self, project_id: str, interface_id: str = "default") -> bool:
        """
        开始执行命令工程
        
        Args:
            project_id: 工程ID
            interface_id: CAN接口ID
            
        Returns:
            bool: 是否启动成功
        """
        project = self.get_project(project_id)
        if not project:
            logger.error(f"Project '{project_id}' not found")
            return False
        
        return self.executor.start_project(project, interface_id)
    
    def stop_project(self) -> bool:
        """停止执行命令工程"""
        return self.executor.stop_project()
    
    def create_command(self, project_id: str, group_id: str, command: Command) -> bool:
        """
        创建命令
        
        Args:
            project_id: 工程ID
            group_id: 组ID
            command: 命令
            
        Returns:
            bool: 是否创建成功
        """
        project = self.get_project(project_id)
        if not project:
            logger.error(f"Project '{project_id}' not found")
            return False
        
        group = project.get_group(group_id)
        if not group:
            logger.error(f"Group '{group_id}' not found in project '{project_id}'")
            return False
        
        # 检查命令ID是否已存在
        for existing_cmd in group.commands:
            if existing_cmd.id == command.id:
                logger.warning(f"Command '{command.id}' already exists in group '{group_id}'")
                return False
        
        group.add_command(command)
        project.updated_at = time.time()
        
        logger.debug(f"Created command '{command.name}' in group '{group.name}'")
        return True
    
    def update_command(self, project_id: str, group_id: str, command: Command) -> bool:
        """
        更新命令
        
        Args:
            project_id: 工程ID
            group_id: 组ID
            command: 命令
            
        Returns:
            bool: 是否更新成功
        """
        project = self.get_project(project_id)
        if not project:
            return False
        
        group = project.get_group(group_id)
        if not group:
            return False
        
        # 查找并替换命令
        for i, existing_cmd in enumerate(group.commands):
            if existing_cmd.id == command.id:
                group.commands[i] = command
                project.updated_at = time.time()
                return True
        
        return False
    
    def delete_command(self, project_id: str, group_id: str, command_id: str) -> bool:
        """
        删除命令
        
        Args:
            project_id: 工程ID
            group_id: 组ID
            command_id: 命令ID
            
        Returns:
            bool: 是否删除成功
        """
        project = self.get_project(project_id)
        if not project:
            return False
        
        group = project.get_group(group_id)
        if not group:
            return False
        
        return group.remove_command(command_id)
    
    def get_all_projects(self) -> List[CommandProject]:
        """获取所有工程"""
        return list(self.projects.values())
    
    def get_executor_status(self) -> Dict[str, Any]:
        """获取执行器状态"""
        return self.executor.get_current_status()
    
    def is_executor_running(self) -> bool:
        """检查执行器是否正在运行"""
        return self.executor.is_running()
    
    def set_executor_callbacks(self, **callbacks) -> None:
        """设置执行器回调函数"""
        for callback_name, callback_func in callbacks.items():
            if hasattr(self.executor, callback_name):
                setattr(self.executor, callback_name, callback_func)
    
    def create_can_frame_command_template(self) -> Dict[str, Any]:
        """创建CAN帧命令模板"""
        return {
            "name": "New CAN Frame",
            "command_type": CommandType.CAN_FRAME.value,
            "send_mode": SendMode.SINGLE.value,
            "period": 1000,
            "enabled": True,
            "can_frame": {
                "arbitration_id": 0x7E0,
                "data": "02 10 01",
                "is_extended_id": False,
                "is_fd": False,
                "comment": "Diagnostic Session Control"
            }
        }
    
    def create_uds_command_template(self) -> Dict[str, Any]:
        """创建UDS命令模板"""
        return {
            "name": "New UDS Command",
            "command_type": CommandType.UDS_COMMAND.value,
            "send_mode": SendMode.SINGLE.value,
            "period": 1000,
            "enabled": True,
            "uds_command": {
                "service_id": 0x10,
                "subfunction": 0x01,
                "data": "",
                "timeout": 2000,
                "expect_response": True,
                "comment": "Enter Diagnostic Session"
            }
        }
    
    def export_project_template(self, template_name: str) -> Dict[str, Any]:
        """导出工程模板"""
        template = {
            "template_name": template_name,
            "version": "1.0",
            "created_at": time.time(),
            "description": f"{template_name} template",
            "groups": [
                {
                    "id": "group1",
                    "name": "ECU Identification",
                    "description": "Read ECU identification information",
                    "enabled": True,
                    "commands": [
                        {
                            "id": "cmd1",
                            "name": "Read VIN",
                            "command_type": CommandType.UDS_COMMAND.value,
                            "send_mode": SendMode.SINGLE.value,
                            "uds_command": {
                                "service_id": 0x22,
                                "data": "F1 81",
                                "timeout": 2000,
                                "comment": "Read Vehicle Identification Number"
                            }
                        }
                    ]
                }
            ]
        }
        
        return template