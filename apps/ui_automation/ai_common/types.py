"""
消息类型和枚举定义
借鉴ui-automation项目的类型系统设计
"""
from enum import Enum


class MessageType(str, Enum):
    """消息类型枚举"""
    LOG = "log"
    PROGRESS = "progress"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"
    DONE_RESULT = "done_result"


class MessageRegion(str, Enum):
    """消息区域枚举"""
    PROCESS = "process"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"


class AgentStatus(str, Enum):
    """Agent状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class ExecutionMode(str, Enum):
    """执行模式枚举"""
    TEXT = "text"
    VISION = "vision"
    AUTO = "auto"
