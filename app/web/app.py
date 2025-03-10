from fastapi import FastAPI, WebSocket, Request, BackgroundTasks, HTTPException, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
import os
import uuid
import json
import webbrowser
import threading
import sys
import io
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import contextmanager, redirect_stdout, redirect_stderr
import time
from pydantic import BaseModel
import glob
import re
import shutil

from app.agent.manus import Manus
from app.flow.base import FlowType
from app.flow.flow_factory import FlowFactory
from app.logger import logger
from app.web.log_handler import capture_session_logs, get_logs
from app.web.thinking_tracker import ThinkingTracker, generate_thinking_steps
from app.web.log_parser import parse_log_file, get_latest_log_info, get_all_logs_info

# 控制是否自动打开浏览器 (读取环境变量，默认为True) 
AUTO_OPEN_BROWSER = os.environ.get("AUTO_OPEN_BROWSER", "1") == "1"
last_opened = False  # 跟踪浏览器是否已打开

app = FastAPI(title="OpenManus Web")

# 获取当前文件所在目录
current_dir = Path(__file__).parent
# 设置静态文件目录
app.mount("/static", StaticFiles(directory=current_dir / "static"), name="static")
# 设置模板目录
templates = Jinja2Templates(directory=current_dir / "templates")

# 存储活跃的会话及其结果
active_sessions: Dict[str, dict] = {}

# 存储任务取消事件
cancel_events: Dict[str, asyncio.Event] = {}

# 存储终端输出内容
terminal_outputs: Dict[str, List[Dict]] = {}

# 创建工作区根目录
WORKSPACE_ROOT = Path(__file__).parent.parent.parent / "workspace"
WORKSPACE_ROOT.mkdir(exist_ok=True)

# 日志目录
LOGS_DIR = Path(__file__).parent.parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# 导入日志监视器
from app.utils.log_monitor import LogFileMonitor

# 存储活跃的日志监视器
active_log_monitors: Dict[str, LogFileMonitor] = {}

# 创建工作区目录的函数
def create_workspace(session_id: str) -> Path:
    """为会话创建工作区目录"""
    # 简化session_id作为目录名
    job_id = f"job_{session_id[:8]}"
    workspace_dir = WORKSPACE_ROOT / job_id
    workspace_dir.mkdir(exist_ok=True)
    return workspace_dir

# 终端输出捕获工具
class TerminalOutputCapture:
    """捕获标准输出和标准错误的上下文管理器"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.stdout_buffer = io.StringIO()
        self.stderr_buffer = io.StringIO()
        
        # 初始化会话的终端输出存储
        if session_id not in terminal_outputs:
            terminal_outputs[session_id] = []
    
    def __enter__(self):
        # 开始捕获stdout和stderr
        self.old_stdout = sys.stdout
        self.old_stderr = sys.stderr
        sys.stdout = self.stdout_buffer
        sys.stderr = self.stderr_buffer
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # 恢复原始stdout和stderr
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr
        
        # 处理捕获的输出
        stdout_content = self.stdout_buffer.getvalue()
        stderr_content = self.stderr_buffer.getvalue()
        
        # 如果有输出，保存到会话的终端输出记录中
        if stdout_content:
            for line in stdout_content.splitlines():
                if line.strip():
                    terminal_outputs[self.session_id].append({
                        "type": "stdout",
                        "content": line,
                        "timestamp": time.time()
                    })
                    print(f"捕获到stdout: {line}")  # 实际终端输出
        
        if stderr_content:
            for line in stderr_content.splitlines():
                if line.strip():
                    terminal_outputs[self.session_id].append({
                        "type": "stderr",
                        "content": line,
                        "timestamp": time.time()
                    })
                    print(f"捕获到stderr: {line}", file=self.old_stderr)  # 实际终端错误输出

@app.on_event("startup") 
async def startup_event():
    """启动事件：应用启动时自动打开浏览器"""
    global last_opened
    if AUTO_OPEN_BROWSER and not last_opened:
        # 延迟1秒以确保服务已经启动
        threading.Timer(1.0, lambda: webbrowser.open("http://localhost:8000")).start()
        print("🌐 自动打开浏览器...")
        last_opened = True

class SessionRequest(BaseModel):
    prompt: str

@app.get("/", response_class=HTMLResponse)
async def get_home(request: Request):
    """主页入口 - 使用connected界面"""
    return HTMLResponse(content=open(current_dir / "static" / "connected_interface.html").read())

@app.get("/original", response_class=HTMLResponse)
async def get_original_interface(request: Request):
    """原始界面入口"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/connected", response_class=HTMLResponse)
async def get_connected_interface(request: Request):
    """连接后端的新界面入口 (与主页相同)"""
    return HTMLResponse(content=open(current_dir / "static" / "connected_interface.html").read())

@app.post("/api/chat")
async def create_chat_session(session_req: SessionRequest, background_tasks: BackgroundTasks):
    session_id = str(uuid.uuid4())
    active_sessions[session_id] = {
        "status": "processing",
        "result": None,
        "log": [],
        "workspace": None
    }
    
    # 创建取消事件
    cancel_events[session_id] = asyncio.Event()
    
    # 创建工作区目录
    workspace_dir = create_workspace(session_id)
    active_sessions[session_id]["workspace"] = str(workspace_dir.relative_to(WORKSPACE_ROOT))
    
    background_tasks.add_task(process_prompt, session_id, session_req.prompt)
    return {"session_id": session_id, "workspace": active_sessions[session_id]["workspace"]}

@app.get("/api/chat/{session_id}")
async def get_chat_result(session_id: str):
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 使用新的日志处理模块获取日志
    session = active_sessions[session_id]
    session["log"] = get_logs(session_id)
    
    return session

@app.post("/api/chat/{session_id}/stop")
async def stop_processing(session_id: str):
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_id in cancel_events:
        cancel_events[session_id].set()
        
    active_sessions[session_id]["status"] = "stopped"
    active_sessions[session_id]["result"] = "处理已被用户停止"
    
    return {"status": "stopped"}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    try:
        await websocket.accept()
        
        if session_id not in active_sessions:
            await websocket.send_text(json.dumps({"error": "Session not found"}))
            await websocket.close()
            return
        
        session = active_sessions[session_id]
        
        # 注册 WebSocket 发送回调函数
        async def ws_send(message: str):
            try:
                await websocket.send_text(message)
            except Exception as e:
                print(f"WebSocket 发送消息失败: {str(e)}")
        
        ThinkingTracker.register_ws_send_callback(session_id, ws_send)
        
        # 初始状态通知中添加日志信息
        await websocket.send_text(json.dumps({
            "status": session["status"], 
            "log": session["log"],
            "thinking_steps": ThinkingTracker.get_thinking_steps(session_id),
            "terminal_output": terminal_outputs.get(session_id, []),
            "logs": ThinkingTracker.get_logs(session_id)  # 添加日志信息
        }))
        
        # 获取工作区名称(job_id) - 优先从环境变量获取
        job_id = None
        # 首先检查当前会话的工作空间关联
        if "workspace" in session:
            job_id = session["workspace"]
        
        # 如果当前没有日志监控器，则创建一个
        if session_id not in active_log_monitors and job_id:
            log_path = LOGS_DIR / f"{job_id}.log"
            if log_path.exists():
                log_monitor = LogFileMonitor(job_id)
                observer = log_monitor.start_monitoring()
                active_log_monitors[session_id] = log_monitor
        
        # 跟踪日志更新
        last_log_entries = []
        if job_id and session_id in active_log_monitors:
            last_log_entries = active_log_monitors[session_id].get_log_entries()
        
        # 等待结果更新
        last_log_count = 0
        last_thinking_step_count = 0
        last_terminal_output_count = 0
        last_tracker_log_count = 0  # 添加ThinkingTracker日志计数
        
        while session["status"] == "processing":
            await asyncio.sleep(0.2)  # 降低检查间隔提高实时性
            
            # 检查系统日志更新 (新增)
            if job_id and session_id in active_log_monitors:
                current_log_entries = active_log_monitors[session_id].get_log_entries()
                if len(current_log_entries) > len(last_log_entries):
                    new_logs = current_log_entries[len(last_log_entries):]
                    await websocket.send_text(json.dumps({
                        "status": session["status"],
                        "system_logs": new_logs,
                        # 添加一个chat_logs字段，将系统日志作为聊天消息发送
                        "chat_logs": new_logs
                    }))
                    last_log_entries = current_log_entries
            
            # 检查日志更新
            current_log_count = len(session["log"])
            if current_log_count > last_log_count:
                await websocket.send_text(json.dumps({
                    "status": session["status"],
                    "log": session["log"][last_log_count:]
                }))
                last_log_count = current_log_count
            
            # 检查思考步骤更新
            thinking_steps = ThinkingTracker.get_thinking_steps(session_id)
            current_thinking_step_count = len(thinking_steps)
            if current_thinking_step_count > last_thinking_step_count:
                await websocket.send_text(json.dumps({
                    "status": session["status"],
                    "thinking_steps": thinking_steps[last_thinking_step_count:]
                }))
                last_thinking_step_count = current_thinking_step_count
            
            # 检查终端输出更新
            terminal_output = terminal_outputs.get(session_id, [])
            current_terminal_output_count = len(terminal_output)
            if current_terminal_output_count > last_terminal_output_count:
                await websocket.send_text(json.dumps({
                    "status": session["status"],
                    "terminal_output": terminal_output[last_terminal_output_count:]
                }))
                last_terminal_output_count = current_terminal_output_count
            
            # 检查ThinkingTracker日志更新
            tracker_logs = ThinkingTracker.get_logs(session_id)
            current_tracker_log_count = len(tracker_logs)
            if current_tracker_log_count > last_tracker_log_count:
                await websocket.send_text(json.dumps({
                    "status": session["status"],
                    "logs": tracker_logs[last_tracker_log_count:]
                }))
                last_tracker_log_count = current_tracker_log_count
            
            # 检查结果更新
            if session["result"]:
                await websocket.send_text(json.dumps({
                    "status": session["status"],
                    "result": session["result"],
                    "log": session["log"][last_log_count:],
                    "thinking_steps": ThinkingTracker.get_thinking_steps(session_id, last_thinking_step_count),
                    "terminal_output": terminal_outputs.get(session_id, [])[last_terminal_output_count:],
                    "system_logs": last_log_entries,  # 添加系统日志
                    "logs": ThinkingTracker.get_logs(session_id, last_tracker_log_count)  # 添加ThinkingTracker日志
                }))
        
        # 发送最终结果时也包含最新日志
        await websocket.send_text(json.dumps({
            "status": session["status"],
            "result": session["result"],
            "log": session["log"][last_log_count:],
            "thinking_steps": ThinkingTracker.get_thinking_steps(session_id, last_thinking_step_count),
            "terminal_output": terminal_outputs.get(session_id, [])[last_terminal_output_count:],
            "system_logs": last_log_entries,  # 添加系统日志
            "logs": ThinkingTracker.get_logs(session_id, last_tracker_log_count)  # 添加ThinkingTracker日志
        }))
        
        # 取消注册 WebSocket 发送回调函数
        ThinkingTracker.unregister_ws_send_callback(session_id)
        await websocket.close()
    except WebSocketDisconnect:
        # 客户端断开连接，正常操作
        ThinkingTracker.unregister_ws_send_callback(session_id)
        pass
    except Exception as e:
        # 其他异常，记录日志但不中断应用
        print(f"WebSocket错误: {str(e)}")
        ThinkingTracker.unregister_ws_send_callback(session_id)

# 在适当位置添加LLM通信钩子
from app.web.thinking_tracker import ThinkingTracker

# 修改通信跟踪器的实现方式
class LLMCommunicationTracker:
    """跟踪与LLM的通信内容，使用monkey patching代替回调"""
    
    def __init__(self, session_id: str, agent=None):
        self.session_id = session_id
        self.agent = agent
        self.original_run_method = None
        
        # 如果提供了agent，安装钩子
        if agent and hasattr(agent, "llm") and hasattr(agent.llm, "completion"):
            self.install_hooks()
    
    def install_hooks(self):
        """安装钩子以捕获LLM通信内容"""
        if not self.agent or not hasattr(self.agent, "llm"):
            return False
            
        # 保存原始方法
        llm = self.agent.llm
        if hasattr(llm, "completion"):
            self.original_completion = llm.completion
            # 替换为我们的包装方法
            llm.completion = self._wrap_completion(self.original_completion)
            return True
        return False
    
    def uninstall_hooks(self):
        """卸载钩子，恢复原始方法"""
        if self.agent and hasattr(self.agent, "llm") and self.original_completion:
            self.agent.llm.completion = self.original_completion
    
    def _wrap_completion(self, original_method):
        """包装LLM的completion方法以捕获输入和输出"""
        session_id = self.session_id
        
        async def wrapped_completion(*args, **kwargs):
            # 记录输入
            prompt = kwargs.get('prompt', '')
            if not prompt and args:
                prompt = args[0]
            if prompt:
                ThinkingTracker.add_communication(session_id, "发送到LLM", 
                                                prompt[:500] + ("..." if len(prompt) > 500 else ""))
            
            # 调用原始方法
            result = await original_method(*args, **kwargs)
            
            # 记录输出
            if result:
                content = result
                if isinstance(result, dict) and 'content' in result:
                    content = result['content']
                elif hasattr(result, 'content'):
                    content = result.content
                
                if isinstance(content, str):
                    ThinkingTracker.add_communication(session_id, "从LLM接收", 
                                                    content[:500] + ("..." if len(content) > 500 else ""))
            
            return result
        
        return wrapped_completion

# 导入新创建的LLM包装器
from app.agent.llm_wrapper import LLMCallbackWrapper

# 添加终端输出获取接口
@app.get("/api/terminal/{session_id}")
async def get_terminal_output(session_id: str, start_index: int = 0):
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    outputs = terminal_outputs.get(session_id, [])[start_index:]
    return {"terminal_output": outputs}

# 修改文件API，支持工作区目录
@app.get("/api/files")
async def get_generated_files():
    """获取所有工作区目录和文件"""
    result = []
    
    # 获取所有工作区目录
    workspaces = list(WORKSPACE_ROOT.glob("job_*"))
    workspaces.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    for workspace in workspaces:
        workspace_name = workspace.name
        # 获取工作区内所有文件并按修改时间排序
        files = []
        with os.scandir(workspace) as it:
            for entry in it:
                if entry.is_file() and entry.name.split('.')[-1] in ['txt','md','html','css','js','py','json']:
                    files.append(entry)
        # 按修改时间倒序排序
        files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # 如果有文件，添加该工作区
        if files:
            workspace_item = {
                "name": workspace_name,
                "path": str(workspace.relative_to(Path(__file__).parent.parent.parent)),
                "modified": workspace.stat().st_mtime,
                "files": []
            }
            
            # 添加工作区下的文件
            for file in sorted(files, key=lambda p: p.name):
                workspace_item["files"].append({
                    "name": file.name,
                    "path": str(Path(file.path).relative_to(Path(__file__).parent.parent.parent)),
                    "type": Path(file.path).suffix[1:],  # 去掉.的扩展名
                    "size": file.stat().st_size,
                    "modified": file.stat().st_mtime
                })
            
            result.append(workspace_item)
    
    return {"workspaces": result}

# 新增日志文件接口
@app.get("/api/logs")
async def get_system_logs(limit: int = 10):
    """获取系统日志列表"""
    log_files = []
    for entry in os.scandir(LOGS_DIR):
        if entry.is_file() and entry.name.endswith('.log'):
            log_files.append({
                "name": entry.name,
                "size": entry.stat().st_size,
                "modified": entry.stat().st_mtime
            })
    # 按修改时间倒序排序并限制数量
    log_files.sort(key=lambda x: x["modified"], reverse=True)
    return {"logs": log_files[:limit]}

@app.get("/api/logs/{log_name}")
async def get_log_content(log_name: str, parsed: bool = False):
    """获取特定日志文件内容"""
    log_path = LOGS_DIR / log_name
    # 安全检查
    if not log_path.exists() or not log_path.is_file():
        raise HTTPException(status_code=404, detail="Log file not found")
    
    # 如果请求解析后的日志信息
    if parsed:
        log_info = parse_log_file(str(log_path))
        log_info["name"] = log_name
        return log_info
    
    # 否则返回原始内容
    with open(log_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return {
        "name": log_name,
        "content": content
    }

@app.get("/api/logs_parsed")
async def get_parsed_logs(limit: int = 10):
    """获取解析后的日志信息列表"""
    return {"logs": get_all_logs_info(str(LOGS_DIR), limit)}

@app.get("/api/logs_parsed/{log_name}")
async def get_parsed_log(log_name: str):
    """获取特定日志文件的解析信息"""
    log_path = LOGS_DIR / log_name
    # 安全检查
    if not log_path.exists() or not log_path.is_file():
        raise HTTPException(status_code=404, detail="Log file not found")
    
    log_info = parse_log_file(str(log_path))
    log_info["name"] = log_name
    return log_info

@app.get("/api/latest_log")
async def get_latest_log():
    """获取最新日志文件的解析信息"""
    return get_latest_log_info(str(LOGS_DIR))

@app.get("/api/files/{file_path:path}")
async def get_file_content(file_path: str):
    """获取特定文件的内容"""
    # 安全检查，防止目录遍历攻击
    root_dir = Path(__file__).parent.parent.parent
    full_path = root_dir / file_path
    
    # 确保文件在项目目录内
    try:
        full_path.relative_to(root_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    # 读取文件内容
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 确定文件类型
        file_type = full_path.suffix[1:] if full_path.suffix else "text"
        
        return {
            "name": full_path.name,
            "path": file_path,
            "type": file_type,
            "content": content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")

# 修改process_prompt函数，处理工作区和终端输出
async def process_prompt(session_id: str, prompt: str):
    # 获取会话工作区
    workspace_dir = None
    if session_id in active_sessions and "workspace" in active_sessions[session_id]:
        workspace_path = active_sessions[session_id]["workspace"]
        workspace_dir = WORKSPACE_ROOT / workspace_path
        os.makedirs(workspace_dir, exist_ok=True)
    
    # 如果没有工作区，创建一个
    if not workspace_dir:
        workspace_dir = create_workspace(session_id)
        if session_id in active_sessions:
            active_sessions[session_id]["workspace"] = str(workspace_dir.relative_to(WORKSPACE_ROOT))
    
    # 设置当前工作目录为工作区
    original_cwd = os.getcwd()
    os.chdir(workspace_dir)
    
    # 使用工作区名称作为日志文件名前缀
    job_id = workspace_dir.name
    # 设置日志文件路径
    task_log_path = LOGS_DIR / f"{job_id}.log"
    
    # 创建日志监视器并开始监控
    log_monitor = LogFileMonitor(job_id)
    observer = log_monitor.start_monitoring()
    active_log_monitors[session_id] = log_monitor
    
    async def sync_logs():
        """定期从LogFileMonitor获取日志并实时更新到ThinkingTracker"""
        last_count = 0
        try:
            while True:
                if session_id not in active_log_monitors:
                    break
                current_logs = active_log_monitors[session_id].get_log_entries()
                if len(current_logs) > last_count:
                    # 处理新的日志条目
                    new_logs = current_logs[last_count:]
                    # 逐条处理每条新日志，确保实时性
                    for log_entry in new_logs:
                        # 单独处理每条日志，立即添加到ThinkingTracker
                        ThinkingTracker.add_log_entry(session_id, {
                            "level": log_entry.get("level", "INFO"),
                            "message": log_entry.get("message", ""),
                            "timestamp": log_entry.get("timestamp", time.time())
                        })
                    last_count = len(current_logs)
                # 减少轮询间隔，提高实时性
                await asyncio.sleep(0.1)  # 每0.1秒检查一次
        except Exception as e:
            print(f"同步日志时发生错误: {str(e)}")
    
    # 启动日志同步任务
    sync_task = asyncio.create_task(sync_logs())
    
    # 设置环境变量告知logger使用此日志文件，确保两种方式都设置
    os.environ["OPENMANUS_LOG_FILE"] = str(task_log_path)
    os.environ["OPENMANUS_TASK_ID"] = job_id
    
    try:
        # 使用终端输出捕获工具捕获命令行输出，确保实时性
        with TerminalOutputCapture(session_id):
            # 使用日志捕获上下文管理器解析日志级别和内容
            with capture_session_logs(session_id) as log:
                # 初始化思考跟踪
                ThinkingTracker.start_tracking(session_id)
                ThinkingTracker.add_thinking_step(session_id, "开始处理用户请求")
                ThinkingTracker.add_thinking_step(session_id, f"工作区目录: {workspace_dir.name}")
                
                # 直接记录用户输入的prompt
                ThinkingTracker.add_communication(session_id, "用户输入", prompt)
                
                # 初始化代理和任务流程
                ThinkingTracker.add_thinking_step(session_id, "初始化AI代理和任务流程")
                agent = Manus()
                
                # 使用包装器包装LLM
                if hasattr(agent, "llm"):
                    original_llm = agent.llm
                    wrapped_llm = LLMCallbackWrapper(original_llm)
                    
                    # 注册回调函数
                    def on_before_request(data):
                        # 提取请求内容
                        prompt_content = None
                        if data.get("args") and len(data["args"]) > 0:
                            prompt_content = str(data["args"][0])
                        elif data.get("kwargs") and "prompt" in data["kwargs"]:
                            prompt_content = data["kwargs"]["prompt"]
                        else:
                            prompt_content = str(data)
                        
                        # 记录通信内容
                        print(f"发送到LLM: {prompt_content[:100]}...")
                        ThinkingTracker.add_communication(session_id, "发送到LLM", prompt_content)
                    
                    def on_after_request(data):
                        # 提取响应内容
                        response = data.get("response", "")
                        response_content = ""
                        
                        # 尝试从不同格式中提取文本内容
                        if isinstance(response, str):
                            response_content = response
                        elif isinstance(response, dict):
                            if "content" in response:
                                response_content = response["content"]
                            elif "text" in response:
                                response_content = response["text"]
                            else:
                                response_content = str(response)
                        elif hasattr(response, "content"):
                            response_content = response.content
                        else:
                            response_content = str(response)
                        
                        # 记录通信内容
                        print(f"从LLM接收: {response_content[:100]}...")
                        ThinkingTracker.add_communication(session_id, "从LLM接收", response_content)
                    
                    # 注册回调
                    wrapped_llm.register_callback("before_request", on_before_request)
                    wrapped_llm.register_callback("after_request", on_after_request)
                    
                    # 替换原始LLM
                    agent.llm = wrapped_llm
                
                flow = FlowFactory.create_flow(
                    flow_type=FlowType.PLANNING,
                    agents=agent,
                )
                
                # 记录处理开始
                ThinkingTracker.add_thinking_step(session_id, f"分析用户请求: {prompt[:50]}{'...' if len(prompt) > 50 else ''}")
                log.info(f"开始执行: {prompt[:50]}{'...' if len(prompt) > 50 else ''}")
                
                # 检查任务是否被取消
                cancel_event = cancel_events.get(session_id)
                if cancel_event and cancel_event.is_set():
                    log.warning("处理已被用户取消")
                    ThinkingTracker.mark_stopped(session_id)
                    active_sessions[session_id]["status"] = "stopped"
                    active_sessions[session_id]["result"] = "处理已被用户停止"
                    return
                
                # 执行前检查工作区已有文件
                existing_files = set()
                for ext in ["*.txt", "*.md", "*.html", "*.css", "*.js", "*.py", "*.json"]:
                    existing_files.update(f.name for f in workspace_dir.glob(ext))
                
                # 跟踪计划创建过程
                ThinkingTracker.add_thinking_step(session_id, "创建任务执行计划")
                ThinkingTracker.add_thinking_step(session_id, "开始执行任务计划")
                
                # 获取取消事件以传递给flow.execute
                cancel_event = cancel_events.get(session_id)
                
                # 初始检查，如果已经取消则不执行
                if cancel_event and cancel_event.is_set():
                    log.warning("处理已被用户取消")
                    ThinkingTracker.mark_stopped(session_id)
                    active_sessions[session_id]["status"] = "stopped"
                    active_sessions[session_id]["result"] = "处理已被用户停止"
                    return
                
                # 执行实际处理 - 传递job_id和cancel_event给flow.execute方法
                result = await flow.execute(prompt, job_id, cancel_event)
                
                # 执行结束后检查新生成的文件
                new_files = set()
                for ext in ["*.txt", "*.md", "*.html", "*.css", "*.js", "*.py", "*.json"]:
                    new_files.update(f.name for f in workspace_dir.glob(ext))
                newly_created = new_files - existing_files
                
                if newly_created:
                    files_list = ", ".join(newly_created)
                    ThinkingTracker.add_thinking_step(
                        session_id, 
                        f"在工作区 {workspace_dir.name} 中生成了{len(newly_created)}个文件: {files_list}"
                    )
                    # 将文件列表也添加到会话结果中
                    active_sessions[session_id]["generated_files"] = list(newly_created)
                
                # 记录完成情况
                log.info("处理完成")
                ThinkingTracker.add_conclusion(session_id, f"任务处理完成！已在工作区 {workspace_dir.name} 中生成结果。")
                
                active_sessions[session_id]["status"] = "completed"
                active_sessions[session_id]["result"] = result
                active_sessions[session_id]["thinking_steps"] = ThinkingTracker.get_thinking_steps(session_id)
                
    except asyncio.CancelledError:
        # 处理取消情况
        print("处理已取消")
        ThinkingTracker.mark_stopped(session_id)
        active_sessions[session_id]["status"] = "stopped"
        active_sessions[session_id]["result"] = "处理已被取消"
    except Exception as e:
        # 处理错误情况
        error_msg = f"处理出错: {str(e)}"
        print(error_msg)
        ThinkingTracker.add_error(session_id, f"处理遇到错误: {str(e)}")
        active_sessions[session_id]["status"] = "error"
        active_sessions[session_id]["result"] = f"发生错误: {str(e)}"
    finally:
        # 恢复原始工作目录
        os.chdir(original_cwd)
        
        # 清除日志文件环境变量
        if "OPENMANUS_LOG_FILE" in os.environ:
            del os.environ["OPENMANUS_LOG_FILE"]
        if "OPENMANUS_TASK_ID" in os.environ:
            del os.environ["OPENMANUS_TASK_ID"]
            
        # 清理资源
        if 'agent' in locals() and hasattr(agent, "llm") and isinstance(agent.llm, LLMCallbackWrapper):
            try:
                # 正确地移除回调
                if 'on_before_request' in locals():
                    agent.llm._callbacks["before_request"].remove(on_before_request)
                if 'on_after_request' in locals():
                    agent.llm._callbacks["after_request"].remove(on_after_request)
            except (ValueError, Exception) as e:
                print(f"清理回调时出错: {str(e)}")
                
        # 清理取消事件
        if session_id in cancel_events:
            del cancel_events[session_id]
        
        # 如果监视器存在，停止监控
        if session_id in active_log_monitors:
            observer.stop()
            observer.join(timeout=1)
            del active_log_monitors[session_id]
        
        # 取消日志同步任务
        if sync_task:
            sync_task.cancel()
            try:
                await sync_task
            except asyncio.CancelledError:
                pass

# 添加一个新的API端点来获取思考步骤
@app.get("/api/thinking/{session_id}")
async def get_thinking_steps(session_id: str, start_index: int = 0):
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "status": ThinkingTracker.get_status(session_id),
        "thinking_steps": ThinkingTracker.get_thinking_steps(session_id, start_index)
    }

# 添加获取进度信息的API端点
@app.get("/api/progress/{session_id}")
async def get_progress(session_id: str):
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return ThinkingTracker.get_progress(session_id)

# 添加API端点获取指定会话的系统日志
@app.get("/api/systemlogs/{session_id}")
async def get_system_logs(session_id: str):
    """获取指定会话的系统日志"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    job_id = None
    if "workspace" in active_sessions[session_id]:
        workspace_path = active_sessions[session_id]["workspace"]
        job_id = workspace_path
    
    if not job_id:
        return {"logs": []}
    
    # 如果有监控器使用监控器
    if session_id in active_log_monitors:
        logs = active_log_monitors[session_id].get_log_entries()
        return {"logs": logs}
    
    # 否则直接读取日志文件
    log_path = LOGS_DIR / f"{job_id}.log"
    if not log_path.exists():
        return {"logs": []}
    
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            logs = [line.strip() for line in f.readlines()]
        return {"logs": logs}
    except Exception as e:
        return {"error": f"Error reading log file: {str(e)}"}
