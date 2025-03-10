from fastapi import FastAPI, Request, Body, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import asyncio
import uuid
from json import dumps

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Task(BaseModel):
    id: str
    prompt: str
    created_at: datetime
    status: str
    steps: list = []

    def model_dump(self, *args, **kwargs):
        data = super().model_dump(*args, **kwargs)
        data['created_at'] = self.created_at.isoformat()
        return data

class TaskManager:
    def __init__(self):
        self.tasks = {}
        self.queues = {}

    def create_task(self, prompt: str) -> Task:
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            prompt=prompt,
            created_at=datetime.now(),
            status="pending"
        )
        self.tasks[task_id] = task
        self.queues[task_id] = asyncio.Queue()
        return task

    async def update_task_step(self, task_id: str, step: int, result: str, step_type: str = "step"):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.steps.append({"step": step, "result": result, "type": step_type})
            await self.queues[task_id].put({
                "type": step_type,
                "step": step,
                "result": result
            })
            await self.queues[task_id].put({
                "type": "status",
                "status": task.status,
                "steps": task.steps
            })

    async def complete_task(self, task_id: str):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = "completed"
            await self.queues[task_id].put({
                "type": "status",
                "status": task.status,
                "steps": task.steps
            })
            await self.queues[task_id].put({"type": "complete"})

    async def fail_task(self, task_id: str, error: str):
        if task_id in self.tasks:
            self.tasks[task_id].status = f"failed: {error}"
            await self.queues[task_id].put({
                "type": "error",
                "message": error
            })

task_manager = TaskManager()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/tasks")
async def create_task(prompt: str = Body(..., embed=True)):
    task = task_manager.create_task(prompt)
    asyncio.create_task(run_task(task.id, prompt))
    return {"task_id": task.id}

from app.agent.toolcall import ToolCallAgent

async def run_task(task_id: str, prompt: str):
    try:
        task_manager.tasks[task_id].status = "running"
        
        agent = ToolCallAgent(
            name="TaskAgent",
            description="Agent for handling task execution",
            max_steps=30
        )
        
        async def on_think(thought):
            await task_manager.update_task_step(task_id, 0, thought, "think")
            
        async def on_tool_execute(tool, input):
            await task_manager.update_task_step(task_id, 0, f"执行工具: {tool}\n输入: {input}", "tool")
            
        async def on_action(action):
            await task_manager.update_task_step(task_id, 0, f"执行动作: {action}", "act")
            
        async def on_run(step, result):
            await task_manager.update_task_step(task_id, step, result, "run")
            
        from app.logger import logger
        
        class SSELogHandler:
            def __init__(self, task_id):
                self.task_id = task_id
                
            async def __call__(self, message):
                import re
                # 提取 - 后面的内容
                cleaned_message = re.sub(r'^.*? - ', '', message)
                
                event_type = "log"
                if "✨ TaskAgent's thoughts:" in cleaned_message:
                    event_type = "think"
                elif "🛠️ TaskAgent selected" in cleaned_message:
                    event_type = "tool"
                elif "🎯 Tool" in cleaned_message:
                    event_type = "act"
                elif "📝 Oops!" in cleaned_message:
                    event_type = "error"
                elif "🏁 Special tool" in cleaned_message:
                    event_type = "complete"
                    
                await task_manager.update_task_step(self.task_id, 0, cleaned_message, event_type)
                
        sse_handler = SSELogHandler(task_id)
        logger.add(sse_handler)

        result = await agent.run(prompt)
        await task_manager.update_task_step(task_id, 1, result, "result")
        await task_manager.complete_task(task_id)
    except Exception as e:
        await task_manager.fail_task(task_id, str(e))

@app.get("/tasks/{task_id}/events")
async def task_events(task_id: str):
    async def event_generator():
        if task_id not in task_manager.queues:
            yield f"event: error\ndata: {dumps({'message': 'Task not found'})}\n\n"
            return

        queue = task_manager.queues[task_id]
        
        task = task_manager.tasks.get(task_id)
        if task:
            yield f"event: status\ndata: {dumps({
                'type': 'status',
                'status': task.status,
                'steps': task.steps
            })}\n\n"

        while True:
            try:
                event = await queue.get()
                formatted_event = dumps(event)
                
                yield ": heartbeat\n\n"
                
                if event["type"] == "complete":
                    yield f"event: complete\ndata: {formatted_event}\n\n"
                    break
                elif event["type"] == "error":
                    yield f"event: error\ndata: {formatted_event}\n\n"
                    break
                elif event["type"] == "step":
                    task = task_manager.tasks.get(task_id)
                    if task:
                        yield f"event: status\ndata: {dumps({
                            'type': 'status',
                            'status': task.status,
                            'steps': task.steps
                        })}\n\n"
                    yield f"event: {event['type']}\ndata: {formatted_event}\n\n"
                elif event["type"] in ["think", "tool", "act", "run"]:
                    yield f"event: {event['type']}\ndata: {formatted_event}\n\n"
                else:
                    yield f"event: {event['type']}\ndata: {formatted_event}\n\n"
                    
            except asyncio.CancelledError:
                print(f"Client disconnected for task {task_id}")
                break
            except Exception as e:
                print(f"Error in event stream: {str(e)}")
                yield f"event: error\ndata: {dumps({'message': str(e)})}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/tasks")
async def get_tasks():
    sorted_tasks = sorted(
        task_manager.tasks.values(),
        key=lambda task: task.created_at,
        reverse=True
    )
    return JSONResponse(
        content=[task.model_dump() for task in sorted_tasks],
        headers={"Content-Type": "application/json"}
    )

@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    if task_id not in task_manager.tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_manager.tasks[task_id]

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": f"服务器内部错误: {str(exc)}"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
