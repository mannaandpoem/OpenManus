"""
LLM回调包装器，为现有LLM添加回调功能
"""
import asyncio
import inspect
import functools
import os
from typing import Dict, List, Any, Callable, Optional

class LLMCallbackWrapper:
    """为LLM添加回调功能的包装类"""
    
    def __init__(self, llm_instance):
        self._llm = llm_instance
        self._callbacks = {
            "before_request": [],  # 发送请求前
            "after_request": [],   # 收到回复后
            "on_error": []         # 发生错误时
        }
        self._wrap_methods()
    
    def _wrap_methods(self):
        """包装LLM实例的方法以添加回调支持"""
        # 常见的方法名称
        method_names = ["completion", "chat", "generate", "run", "call", "__call__"]
        
        for name in method_names:
            if hasattr(self._llm, name) and callable(getattr(self._llm, name)):
                original_method = getattr(self._llm, name)
                
                # 检查是否是异步方法
                is_async = inspect.iscoroutinefunction(original_method)
                
                if is_async:
                    @functools.wraps(original_method)
                    async def async_wrapped(*args, **kwargs):
                        # 执行前回调
                        request_data = {"args": args, "kwargs": kwargs}
                        self._execute_callbacks("before_request", request_data)
                        
                        try:
                            # 调用原始方法
                            result = await original_method(*args, **kwargs)
                            
                            # 执行后回调
                            response_data = {"request": request_data, "response": result}
                            self._execute_callbacks("after_request", response_data)
                            
                            # 保存文件到当前工作目录（如果是在工作区内）
                            current_dir = os.getcwd()
                            if "workspace" in current_dir:
                                self._save_conversation_to_file(args, kwargs, result)
                            
                            return result
                        except Exception as e:
                            # 错误回调
                            error_data = {"request": request_data, "error": str(e), "exception": e}
                            self._execute_callbacks("on_error", error_data)
                            raise
                    
                    # 替换为包装后的方法
                    setattr(self, name, async_wrapped)
                else:
                    @functools.wraps(original_method)
                    def wrapped(*args, **kwargs):
                        # 执行前回调
                        request_data = {"args": args, "kwargs": kwargs}
                        self._execute_callbacks("before_request", request_data)
                        
                        try:
                            # 调用原始方法
                            result = original_method(*args, **kwargs)
                            
                            # 执行后回调
                            response_data = {"request": request_data, "response": result}
                            self._execute_callbacks("after_request", response_data)
                            
                            return result
                        except Exception as e:
                            # 错误回调
                            error_data = {"request": request_data, "error": str(e), "exception": e}
                            self._execute_callbacks("on_error", error_data)
                            raise
                    
                    # 替换为包装后的方法
                    setattr(self, name, wrapped)
    
    def _save_conversation_to_file(self, args, kwargs, result):
        """保存对话到文件（如果设置了）"""
        try:
            # 检查是否有保存对话的环境变量
            if os.environ.get("SAVE_LLM_CONVERSATION", "0") == "1":
                prompt = kwargs.get('prompt', '')
                if not prompt and args:
                    prompt = args[0]
                
                if not prompt:
                    return
                
                # 创建对话记录文件
                with open("llm_conversation.txt", "a", encoding="utf-8") as f:
                    f.write("\n--- LLM REQUEST ---\n")
                    f.write(str(prompt)[:2000])  # 限制长度
                    f.write("\n\n--- LLM RESPONSE ---\n")
                    
                    # 获取响应内容
                    response_content = ""
                    if isinstance(result, str):
                        response_content = result
                    elif isinstance(result, dict) and 'content' in result:
                        response_content = result['content']
                    elif hasattr(result, 'content'):
                        response_content = result.content
                    else:
                        response_content = str(result)
                    
                    f.write(response_content[:2000])  # 限制长度
                    f.write("\n\n--------------------\n")
        except Exception as e:
            print(f"保存对话到文件时出错: {str(e)}")
    
    def register_callback(self, event_type: str, callback: Callable):
        """注册回调函数
        
        Args:
            event_type: 事件类型，可以是"before_request"、"after_request"或"on_error"
            callback: 回调函数，接收相应的数据
        """
        if event_type in self._callbacks:
            self._callbacks[event_type].append(callback)
            return True
        return False
    
    def unregister_callback(self, event_type: str, callback: Callable):
        """注销特定的回调函数"""
        if event_type in self._callbacks and callback in self._callbacks[event_type]:
            self._callbacks[event_type].remove(callback)
            return True
        return False
    
    def clear_callbacks(self, event_type: str = None):
        """清除所有回调函数"""
        if event_type is None:
            # 清除所有类型的回调
            for event in self._callbacks:
                self._callbacks[event] = []
        elif event_type in self._callbacks:
            # 清除特定类型的回调
            self._callbacks[event_type] = []
    
    def _execute_callbacks(self, event_type: str, data: Dict[str, Any]):
        """执行指定类型的回调函数"""
        if event_type in self._callbacks:
            for callback in self._callbacks[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    print(f"回调执行出错: {str(e)}")
    
    def __getattr__(self, name):
        """转发其他属性访问到原始LLM实例"""
        return getattr(self._llm, name)
