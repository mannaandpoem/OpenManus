"""
思考跟踪器模块，实现Manus风格的任务进展日志系统
"""
import time
import threading
import json
import asyncio
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from collections import deque

# 全局思考步骤存储
class ThinkingStep:
    """表示一个思考步骤"""
    def __init__(self, message: str, step_type: str = "thinking", details: Optional[str] = None):
        self.message = message
        self.step_type = step_type  # thinking, conclusion, error, communication
        self.details = details      # 用于存储通信内容或详细信息
        self.timestamp = time.time()

class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    THINKING = "thinking"
    COMPLETED = "completed"
    ERROR = "error"
    STOPPED = "stopped"

class ThinkingTracker:
    """思考跟踪器，用于记录和管理AI思考过程"""
    
    # 类变量，存储所有会话的思考步骤
    _session_steps: Dict[str, List[ThinkingStep]] = {}
    _session_status: Dict[str, TaskStatus] = {}
    _session_progress: Dict[str, Dict[str, Any]] = {}  # 存储进度信息
    _session_logs: Dict[str, List[Dict]] = {}  # 存储日志内容
    _ws_send_callbacks: Dict[str, Any] = {}  # 存储WebSocket发送回调函数
    _lock = threading.Lock()
    
    @classmethod
    def register_ws_send_callback(cls, session_id: str, callback: Any) -> None:
        """注册WebSocket发送回调函数"""
        with cls._lock:
            cls._ws_send_callbacks[session_id] = callback
    
    @classmethod
    def unregister_ws_send_callback(cls, session_id: str) -> None:
        """取消注册WebSocket发送回调函数"""
        with cls._lock:
            if session_id in cls._ws_send_callbacks:
                del cls._ws_send_callbacks[session_id]
    
    @classmethod
    def start_tracking(cls, session_id: str) -> None:
        """开始追踪一个会话的思考过程"""
        with cls._lock:
            cls._session_steps[session_id] = []
            cls._session_status[session_id] = TaskStatus.THINKING
            cls._session_progress[session_id] = {
                "current_step": "初始化",
                "total_steps": 0,
                "completed_steps": 0,
                "percentage": 0
            }
    
    @classmethod
    def add_thinking_step(cls, session_id: str, message: str, details: Optional[str] = None) -> None:
        """添加一个思考步骤"""
        step = ThinkingStep(message, "thinking", details)
        with cls._lock:
            if session_id in cls._session_steps:
                cls._session_steps[session_id].append(step)
                
                # 更新进度信息
                if session_id in cls._session_progress:
                    progress = cls._session_progress[session_id]
                    progress["current_step"] = message

                    # Attempt to extract step number and total steps from the message
                    import re
                    match = re.search(r"Executing step (\d+)/(\d+)", message)
                    if match:
                        current_step_num = int(match.group(1))
                        total_steps = int(match.group(2))
                        progress["total_steps"] = total_steps
                        progress["completed_steps"] = current_step_num -1  # Mark previous as complete
                    
                    if progress["total_steps"] > 0:
                        progress["percentage"] = min(
                            int(100 * progress["completed_steps"] / progress["total_steps"]),
                            99
                        )

    @classmethod
    def add_communication(cls, session_id: str, direction: str, content: str) -> None:
        """添加一个通信记录
        
        Args:
            session_id: 会话ID
            direction: 通信方向，如 "发送到LLM"、"从LLM接收"
            content: 通信内容
        """
        message = f"{direction}通信"
        step = ThinkingStep(message, "communication", content)
        with cls._lock:
            if session_id in cls._session_steps:
                cls._session_steps[session_id].append(step)
    
    @classmethod
    def update_progress(cls, session_id: str, total_steps: int = None, current_step: str = None):
        """更新任务进度信息"""
        with cls._lock:
            if session_id in cls._session_progress:
                progress = cls._session_progress[session_id]
                
                if total_steps is not None:
                    progress["total_steps"] = total_steps
                
                if current_step is not None:
                    progress["current_step"] = current_step
                
                # 重新计算百分比
                if progress["total_steps"] > 0:
                    progress["percentage"] = min(
                        int(100 * progress["completed_steps"] / progress["total_steps"]), 
                        99  # 最多到99%，完成时才到100%
                    )
    
    @classmethod
    def add_conclusion(cls, session_id: str, message: str, details: Optional[str] = None) -> None:
        """添加一个结论"""
        step = ThinkingStep(message, "conclusion", details)
        with cls._lock:
            if session_id in cls._session_steps:
                cls._session_steps[session_id].append(step)
                cls._session_status[session_id] = TaskStatus.COMPLETED
                
                # 更新进度为100%
                if session_id in cls._session_progress:
                    progress = cls._session_progress[session_id]
                    progress["percentage"] = 100
                    progress["current_step"] = "已完成"
    
    @classmethod
    def add_error(cls, session_id: str, message: str) -> None:
        """添加一个错误信息"""
        step = ThinkingStep(message, "error")
        with cls._lock:
            if session_id in cls._session_steps:
                cls._session_steps[session_id].append(step)
                cls._session_status[session_id] = TaskStatus.ERROR
    
    @classmethod
    def mark_stopped(cls, session_id: str) -> None:
        """标记任务已停止"""
        with cls._lock:
            if session_id in cls._session_status:
                cls._session_status[session_id] = TaskStatus.STOPPED
    
    @classmethod
    def get_thinking_steps(cls, session_id: str, start_index: int = 0) -> List[Dict]:
        """获取指定会话的思考步骤"""
        with cls._lock:
            if session_id not in cls._session_steps:
                return []
            
            steps = cls._session_steps[session_id][start_index:]
            return [
                {
                    "message": step.message,
                    "type": step.step_type,
                    "details": step.details,
                    "timestamp": step.timestamp
                }
                for step in steps
            ]
    
    @classmethod
    def get_progress(cls, session_id: str) -> Dict[str, Any]:
        """获取任务进度信息"""
        with cls._lock:
            if session_id not in cls._session_progress:
                return {
                    "current_step": "未开始",
                    "total_steps": 0,
                    "completed_steps": 0,
                    "percentage": 0
                }
            return cls._session_progress[session_id].copy()
    
    @classmethod
    def get_status(cls, session_id: str) -> str:
        """获取任务状态"""
        with cls._lock:
            if session_id not in cls._session_status:
                return TaskStatus.PENDING.value
            return cls._session_status[session_id].value
    
    @classmethod
    def clear_session(cls, session_id: str) -> None:
        """清除指定会话的记录"""
        with cls._lock:
            if session_id in cls._session_steps:
                del cls._session_steps[session_id]
            if session_id in cls._session_status:
                del cls._session_status[session_id]
            if session_id in cls._session_progress:
                del cls._session_progress[session_id]
            if session_id in cls._session_logs:
                del cls._session_logs[session_id]
    
    @classmethod
    def add_log_entry(cls, session_id: str, entry: Dict) -> None:
        """添加一个日志条目"""
        with cls._lock:
            if session_id not in cls._session_logs:
                cls._session_logs[session_id] = []
            
            # 确保日志条目有必要的字段
            if "timestamp" not in entry:
                entry["timestamp"] = time.time()
            
            cls._session_logs[session_id].append(entry)
            
            # 根据日志级别自动添加对应的思考步骤，更详细地处理日志内容
            msg = entry.get('message', '')
            if entry.get("level") == "INFO":
                # 针对特定类型的日志内容生成更有意义的思考步骤
                if "开始执行" in msg:
                    cls.add_thinking_step(session_id, f"开始执行任务: {msg.replace('开始执行: ', '')}")
                elif "执行步骤" in msg or "步骤" in msg:
                    # 尝试提取步骤信息
                    cls.add_thinking_step(session_id, f"执行: {msg}")
                elif "完成" in msg or "成功" in msg:
                    cls.add_thinking_step(session_id, f"完成: {msg}")
                else:
                    cls.add_thinking_step(session_id, f"信息: {msg}")
            elif entry.get("level") == "ERROR":
                cls.add_error(session_id, f"错误: {msg}")
            elif entry.get("level") == "WARNING":
                cls.add_thinking_step(session_id, f"警告: {msg}", "warning")
            
            # 识别进度信息并更新
            cls._update_progress_from_log(session_id, msg)
        
        # 添加日志后立即通知 WebSocket 客户端
        cls._notify_ws_log_update(session_id, entry)
    
    @classmethod
    def _notify_ws_log_update(cls, session_id: str, log_entry: Dict):
        """通知 WebSocket 客户端有新的日志条目"""
        with cls._lock:
            if session_id in cls._ws_send_callbacks:
                callback = cls._ws_send_callbacks[session_id]
                try:
                    # 使用 asyncio.create_task 确保非阻塞
                    asyncio.create_task(callback(json.dumps({
                        "status": cls.get_status(session_id),
                        "logs": [log_entry]
                    })))
                except Exception as e:
                    print(f"WebSocket 发送回调失败: {str(e)}")
    
    @classmethod
    def _update_progress_from_log(cls, session_id: str, message: str):
        """从日志消息中提取进度信息并更新"""
        import re
        # 尝试从日志中提取步骤信息
        step_match = re.search(r"步骤 (\d+)/(\d+)", message) or re.search(r"Step (\d+)/(\d+)", message)
        if step_match and session_id in cls._session_progress:
            current_step = int(step_match.group(1))
            total_steps = int(step_match.group(2))
            progress = cls._session_progress[session_id]
            
            progress["current_step"] = message
            progress["total_steps"] = total_steps
            progress["completed_steps"] = current_step - 1
            
            # 重新计算百分比
            if total_steps > 0:
                progress["percentage"] = min(
                    int(100 * progress["completed_steps"] / total_steps), 
                    99  # 最多到99%，完成时才到100%
                )
    
    @classmethod
    def add_log_entries(cls, session_id: str, entries: List[Dict]) -> None:
        """批量添加日志条目"""
        for entry in entries:
            cls.add_log_entry(session_id, entry)
    
    @classmethod
    def get_logs(cls, session_id: str, start_index: int = 0) -> List[Dict]:
        """获取指定会话的日志条目"""
        with cls._lock:
            if session_id not in cls._session_logs:
                return []
            return cls._session_logs[session_id][start_index:]

# 预定义的思考步骤模板
RESEARCH_STEPS = [
    "分析问题需求和上下文",
    "确定搜索关键词",
    "检索相关知识库和资料",
    "分析和整理检索到的信息",
    "评估可行的解决方案",
    "整合信息并构建解决框架",
    "生成最终回答"
]

CODING_STEPS = [
    "分析代码需求和功能规格",
    "设计代码结构和接口",
    "开发核心算法逻辑",
    "编写主要功能模块",
    "实现边界情况和错误处理",
    "进行代码测试和调试",
    "优化代码性能和可读性",
    "完成代码和文档"
]

WRITING_STEPS = [
    "收集写作主题的相关资料...",
    "构思内容大纲和关键点...",
    "撰写初稿内容...",
    "完善论述和事实核查...",
    "润色语言和格式..."
]

# 任务类型到预定义步骤的映射
TASK_TYPE_STEPS = {
    "research": RESEARCH_STEPS,
    "coding": CODING_STEPS, 
    "writing": WRITING_STEPS
}

def generate_thinking_steps(session_id: str, task_type: str = "research", task_description: str = "", 
                            show_communication: bool = True) -> None:
    """生成一系列思考步骤，用于模拟AI思考过程"""
    steps = TASK_TYPE_STEPS.get(task_type, RESEARCH_STEPS)
    
    # 如果有描述，添加更具体的步骤
    if task_description:
        specific_steps = [
            f"研究{task_description}的相关信息",
            f"分析{task_description}的关键点",
            f"整理{task_description}的解决方案"
        ]
        steps = specific_steps + steps
    
    ThinkingTracker.start_tracking(session_id)
    ThinkingTracker.update_progress(session_id, total_steps=len(steps)+2)  # +2为开始和结束步骤
    
    # 添加初始步骤
    ThinkingTracker.add_thinking_step(session_id, f"开始处理任务: {task_description if task_description else '新请求'}")
    
    # 模拟每隔一段时间添加一个思考步骤
    for step in steps:
        ThinkingTracker.add_thinking_step(session_id, step)
        
        # 模拟与LLM的通信
        if show_communication:
            # 模拟向LLM发送请求
            ThinkingTracker.add_communication(
                session_id, 
                "发送到LLM", 
                f"请帮我{step}..."
            )
            
            # 模拟接收LLM回复
            ThinkingTracker.add_communication(
                session_id, 
                "从LLM接收", 
                f"我已完成{step}。这是相关结果: [详细信息]"
            )
    
    # 添加结论
    ThinkingTracker.add_conclusion(session_id, "任务处理完成！已生成结果。")
