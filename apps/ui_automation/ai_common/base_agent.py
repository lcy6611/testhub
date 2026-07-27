"""
统一Agent基类
借鉴ui-automation项目的BaseAgent设计，提供通用功能
"""
import time
import uuid
from typing import Dict, Optional, Any, Callable, Awaitable
from abc import ABC
import logging

from .types import MessageType, MessageRegion

logger = logging.getLogger('django')


class BaseAgentMixin(ABC):
    """Agent功能混入类，提供统一的错误处理、性能监控、消息发送等功能"""
    
    def __init__(self, agent_name: str = "BaseAgent"):
        """初始化Agent混入
        
        Args:
            agent_name: Agent名称，用于日志标识
        """
        self.agent_name = agent_name
        self.performance_metrics: Dict[str, Dict[str, Any]] = {}
    
    def send_message(self, 
                    content: str, 
                    message_type: MessageType = MessageType.LOG,
                    region: MessageRegion = MessageRegion.PROCESS,
                    callback: Optional[Callable] = None) -> None:
        """发送消息（同步版本）
        
        Args:
            content: 消息内容
            message_type: 消息类型
            region: 消息区域
            callback: 回调函数（如果提供）
        """
        message = {
            'type': message_type.value,
            'content': content,
            'region': region.value,
            'source': self.agent_name
        }
        
        if callback:
            try:
                callback(message)
            except Exception as e:
                logger.warning(f"[{self.agent_name}] Callback执行失败: {e}")
        
        logger.debug(f"[{self.agent_name}] {message_type.value}: {content[:50]}...")
    
    async def send_message_async(self,
                                 content: str,
                                 message_type: MessageType = MessageType.LOG,
                                 region: MessageRegion = MessageRegion.PROCESS,
                                 callback: Optional[Callable] = None) -> None:
        """发送消息（异步版本）"""
        message = {
            'type': message_type.value,
            'content': content,
            'region': region.value,
            'source': self.agent_name
        }
        
        if callback:
            try:
                if hasattr(callback, '__call__'):
                    import asyncio
                    if asyncio.iscoroutinefunction(callback):
                        await callback(message)
                    else:
                        callback(message)
            except Exception as e:
                logger.warning(f"[{self.agent_name}] Callback执行失败: {e}")
        
        logger.debug(f"[{self.agent_name}] {message_type.value}: {content[:50]}...")
    
    def send_success(self, content: str, callback: Optional[Callable] = None) -> None:
        """发送成功消息"""
        self.send_message(f"✅ {content}", MessageType.SUCCESS, MessageRegion.SUCCESS, callback)
    
    def send_warning(self, content: str, callback: Optional[Callable] = None) -> None:
        """发送警告消息"""
        logger.warning(f"[{self.agent_name}] 警告: {content}")
        self.send_message(f"⚠️ {content}", MessageType.WARNING, MessageRegion.WARNING, callback)
    
    def send_error(self, error_message: str, callback: Optional[Callable] = None) -> None:
        """发送错误消息"""
        logger.error(f"[{self.agent_name}] 错误: {error_message}")
        self.send_message(f"❌ {error_message}", MessageType.ERROR, MessageRegion.ERROR, callback)
    
    def send_info(self, content: str, callback: Optional[Callable] = None) -> None:
        """发送信息消息"""
        self.send_message(f"ℹ️ {content}", MessageType.INFO, MessageRegion.INFO, callback)
    
    def send_progress(self, content: str, progress_percent: Optional[float] = None, callback: Optional[Callable] = None) -> None:
        """发送进度消息"""
        result = {"progress": progress_percent} if progress_percent is not None else None
        message = {
            'type': MessageType.PROGRESS.value,
            'content': content,
            'region': MessageRegion.PROCESS.value,
            'source': self.agent_name,
            'result': result
        }
        if callback:
            try:
                callback(message)
            except Exception as e:
                logger.warning(f"[{self.agent_name}] Callback执行失败: {e}")
    
    def handle_exception(self, func_name: str, exception: Exception, send_error_message: bool = True, callback: Optional[Callable] = None) -> None:
        """处理异常并可选发送错误消息
        
        Args:
            func_name: 发生异常的函数名
            exception: 异常对象
            send_error_message: 是否发送错误消息
            callback: 回调函数
        """
        error_msg = f"在{func_name}中发生错误: {str(exception)}"
        logger.error(f"[{self.agent_name}] {error_msg}", exc_info=True)
        
        if send_error_message:
            self.send_error(error_msg, callback)
    
    def start_performance_monitoring(self, operation_name: str = "operation") -> str:
        """开始性能监控
        
        Args:
            operation_name: 操作名称
            
        Returns:
            str: 监控ID
        """
        monitor_id = f"{operation_name}_{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        
        self.performance_metrics[monitor_id] = {
            "operation": operation_name,
            "start_time": start_time,
            "agent": self.agent_name
        }
        
        logger.debug(f"[{self.agent_name}] 开始性能监控: {operation_name} (ID: {monitor_id})")
        return monitor_id
    
    def end_performance_monitoring(self, monitor_id: str, log_result: bool = True) -> Optional[Dict[str, Any]]:
        """结束性能监控
        
        Args:
            monitor_id: 监控ID
            log_result: 是否记录结果到日志
            
        Returns:
            Dict[str, Any]: 性能指标数据
        """
        if monitor_id not in self.performance_metrics:
            logger.warning(f"[{self.agent_name}] 未找到监控ID: {monitor_id}")
            return None
        
        metric = self.performance_metrics[monitor_id]
        end_time = time.time()
        duration = end_time - metric["start_time"]
        
        result = {
            **metric,
            "end_time": end_time,
            "duration": duration,
            "duration_formatted": f"{duration:.2f}秒"
        }
        
        if log_result:
            logger.info(f"[{self.agent_name}] {metric['operation']} 耗时: {duration:.2f}秒")
        
        # 清理已完成的监控
        del self.performance_metrics[monitor_id]
        
        return result
