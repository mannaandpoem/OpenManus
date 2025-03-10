"""
简单的日志处理模块，用于Web应用日志捕获
"""
import time
import threading
from typing import Dict, List, Callable, Optional
from contextlib import contextmanager
from datetime import datetime
import sys
import io
from loguru import logger

# 全局日志存储
session_logs: Dict[str, List[Dict]] = {}
_lock = threading.Lock()

# 注册自定义日志处理器，按会话ID分类存储日志
class SessionLogHandler:
    def __init__(self, session_id: str):
        self.session_id = session_id
        
    def __call__(self, record):
        log_entry = {
            "time": record["time"].strftime("%Y-%m-%d %H:%M:%S.%f"),
            "level": record["level"].name,
            "message": record["message"],
            "timestamp": datetime.now().timestamp()
        }
        
        with _lock:
            if self.session_id not in session_logs:
                session_logs[self.session_id] = []
            session_logs[self.session_id].append(log_entry)
        
        # 传递记录，继续处理链
        return True

class SimpleLogCapture:
    """简单的日志捕获器，提供类似logger的接口"""
    def __init__(self, session_id: str):
        self.session_id = session_id
    
    def info(self, message: str) -> None:
        """记录信息级别日志"""
        add_log(self.session_id, "INFO", message)
        logger.info(message)
    
    def warning(self, message: str) -> None:
        """记录警告级别日志"""
        add_log(self.session_id, "WARNING", message)
        logger.warning(message)
    
    def error(self, message: str) -> None:
        """记录错误级别日志"""
        add_log(self.session_id, "ERROR", message)
        logger.error(message)
    
    def debug(self, message: str) -> None:
        """记录调试级别日志"""
        add_log(self.session_id, "DEBUG", message)
        logger.debug(message)
        
    def exception(self, message: str) -> None:
        """记录异常级别日志"""
        add_log(self.session_id, "ERROR", message)
        logger.exception(message)

@contextmanager
def capture_session_logs(session_id: str):
    """
    上下文管理器，用于捕获指定会话的日志
    返回一个SimpleLogCapture实例，而不是直接返回日志列表
    """
    # 创建该会话的日志存储
    with _lock:
        if session_id not in session_logs:
            session_logs[session_id] = []
    
    # 添加会话特定的日志处理器
    handler_id = logger.add(SessionLogHandler(session_id))
    
    # 创建一个简单的日志捕获器
    log_capture = SimpleLogCapture(session_id)
    
    try:
        # 返回日志捕获器而不是日志列表
        yield log_capture
    finally:
        # 移除临时添加的处理器
        logger.remove(handler_id)

def add_log(session_id: str, level: str, message: str) -> None:
    """添加日志到指定会话"""
    with _lock:
        if session_id not in session_logs:
            session_logs[session_id] = []
        
        session_logs[session_id].append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "level": level,
            "message": message,
            "timestamp": datetime.now().timestamp()
        })

def get_logs(session_id: str) -> List[Dict]:
    """获取指定会话的日志"""
    with _lock:
        return session_logs.get(session_id, [])[:]

def clear_logs(session_id: str) -> None:
    """清除指定会话的日志"""
    with _lock:
        if session_id in session_logs:
            session_logs[session_id] = []
