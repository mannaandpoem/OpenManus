"""
LLM通信监控模块，用于捕获和模拟与LLM的通信内容
"""
import time
import asyncio
import random
from typing import List, Dict, Any, Callable, Optional, Awaitable
from functools import wraps

class LLMMonitor:
    """LLM通信监控器，支持多种方式追踪LLM通信"""
    
    def __init__(self):
        self.interceptors = []
        self.communications = []
    
    def register_interceptor(self, func: Callable):
        """注册一个拦截器函数，该函数将在每次通信时调用"""
        self.interceptors.append(func)
        return func  # 便于当作装饰器使用
    
    def record_communication(self, direction: str, content: Any):
        """记录通信内容"""
        comm_record = {
            "direction": direction,  # "in" 或 "out"
            "content": str(content)[:1000],  # 限制长度
            "timestamp": time.time()
        }
        self.communications.append(comm_record)
        
        # 通知所有拦截器
        for interceptor in self.interceptors:
            try:
                interceptor(comm_record)
            except Exception as e:
                print(f"拦截器错误: {str(e)}")
    
    def get_communications(self, start_idx: int = 0) -> List[Dict[str, Any]]:
        """获取通信记录"""
        return self.communications[start_idx:]
    
    def clear(self):
        """清除所有通信记录"""
        self.communications = []
    
    def intercept_method(self, obj, method_name):
        """拦截对象的方法调用"""
        if not hasattr(obj, method_name):
            return False
        
        original_method = getattr(obj, method_name)
        
        @wraps(original_method)
        async def wrapped_method(*args, **kwargs):
            # 记录输入
            input_data = str(args[0]) if args else str(kwargs)
            self.record_communication("in", input_data)
            
            # 调用原始方法
            result = await original_method(*args, **kwargs)
            
            # 记录输出
            self.record_communication("out", result)
            return result
        
        # 替换原始方法
        setattr(obj, method_name, wrapped_method)
        return True

# 创建一个全局监控器实例
monitor = LLMMonitor()

# 提供一些模拟LLM的函数，可用于演示或测试
async def simulate_llm_thinking(prompt: str, callback: Optional[Callable] = None, steps: int = 5, delay: float = 1.0):
    """模拟LLM思考过程，产生一系列思考步骤"""
    
    # 记录输入
    monitor.record_communication("in", prompt)
    
    thinking_steps = [
        "分析问题需求",
        "检索相关知识",
        "整理和组织信息",
        "撰写初步答案",
        "检查和优化答案",
        "生成最终回复"
    ]
    
    # 根据提示调整思考步骤
    if "代码" in prompt or "编程" in prompt:
        thinking_steps = [
            "理解代码需求",
            "设计代码结构",
            "编写核心函数",
            "实现错误处理",
            "测试代码功能",
            "优化代码效率"
        ]
    
    # 确保步骤数量合理
    actual_steps = min(steps, len(thinking_steps))
    
    # 模拟思考过程
    for i in range(actual_steps):
        step_msg = thinking_steps[i]
        if callback:
            callback(step_msg)
        await asyncio.sleep(delay * (0.5 + random.random()))
    
    # 生成回答
    result = f"这是对问题「{prompt[:30]}...」的回答。\n\n"
    result += "根据我的分析，有以下几点建议：\n"
    result += "1. 首先，确认问题的核心\n"
    result += "2. 接下来，分析可能的解决方案\n"
    result += "3. 最后，选择最合适的方法实施"
    
    # 记录输出
    monitor.record_communication("out", result)
    return result
