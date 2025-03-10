"""
为流程添加思考过程追踪功能
"""
import time
import asyncio
from typing import Dict, List, Any, Optional, Callable, AsyncGenerator
from functools import wraps
from app.web.thinking_tracker import ThinkingTracker

class FlowTracker:
    """流程跟踪器，用于钩入流程执行过程，添加思考步骤记录"""
    
    @staticmethod
    def patch_flow(flow_obj, session_id: str):
        """为流程对象应用跟踪补丁"""
        if not hasattr(flow_obj, "_original_execute"):
            # 保存原始方法
            flow_obj._original_execute = flow_obj.execute
            
            # 添加会话ID
            flow_obj._tracker_session_id = session_id
            
            # 替换execute方法
            @wraps(flow_obj._original_execute)
            async def tracked_execute(prompt, *args, **kwargs):
                # 在执行前添加思考步骤
                ThinkingTracker.add_thinking_step(session_id, "开始执行流程")
                
                # 跟踪子步骤执行
                if hasattr(flow_obj, "_execute_step"):
                    original_step = flow_obj._execute_step
                    
                    @wraps(original_step)
                    async def tracked_step():
                        if hasattr(flow_obj, "current_step_description"):
                            step_desc = flow_obj.current_step_description
                            ThinkingTracker.add_thinking_step(session_id, f"执行步骤: {step_desc}")
                        else:
                            ThinkingTracker.add_thinking_step(session_id, "执行流程步骤")
                            
                        result = await original_step()
                        return result
                        
                    flow_obj._execute_step = tracked_step
                
                # 执行原始方法
                result = await flow_obj._original_execute(prompt, *args, **kwargs)
                
                # 在执行后添加思考步骤
                ThinkingTracker.add_thinking_step(session_id, "流程执行完成")
                
                return result
                
            flow_obj.execute = tracked_execute
            
            return True
        return False
