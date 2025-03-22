import asyncio
import json
import os
import threading
import tomllib
import uuid
import webbrowser
from datetime import datetime
from functools import partial
from json import dumps
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel


app = FastAPI()

app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

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
        data["created_at"] = self.created_at.isoformat()
        return data


class TaskManager:
    def __init__(self):
        self.tasks = {}
        self.queues = {}

    def create_task(self, prompt: str) -> Task:
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id, prompt=prompt, created_at=datetime.now(), status="pending"
        )
        self.tasks[task_id] = task
        self.queues[task_id] = asyncio.Queue()
        return task

    async def update_task_step(
        self, task_id: str, step: int, result: str, step_type: str = "step"
    ):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.steps.append({"step": step, "result": result, "type": step_type})
            await self.queues[task_id].put(
                {"type": step_type, "step": step, "result": result}
            )
            await self.queues[task_id].put(
                {"type": "status", "status": task.status, "steps": task.steps}
            )

    async def complete_task(self, task_id: str):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = "completed"
            await self.queues[task_id].put(
                {"type": "status", "status": task.status, "steps": task.steps}
            )
            await self.queues[task_id].put({"type": "complete"})

    async def fail_task(self, task_id: str, error: str):
        if task_id in self.tasks:
            self.tasks[task_id].status = f"failed: {error}"
            await self.queues[task_id].put({"type": "error", "message": error})


task_manager = TaskManager()


def get_available_themes():
    """Scan themes directory to get all available themes"""
    themes_dir = "web/static/themes"
    if not os.path.exists(themes_dir):
        return [{"id": "openmanus", "name": "Manus", "description": "Default theme"}]

    themes = []
    for item in os.listdir(themes_dir):
        theme_path = os.path.join(themes_dir, item)
        if os.path.isdir(theme_path):
            # Verify if the theme folder contains necessary files
            templates_dir = os.path.join(theme_path, "templates")
            static_dir = os.path.join(theme_path, "static")
            config_file = os.path.join(theme_path, "theme.json")

            if os.path.exists(templates_dir) and os.path.exists(static_dir):
                if os.path.exists(os.path.join(templates_dir, "chat.html")):
                    theme_info = {"id": item, "name": item, "description": ""}

                    # If there is a configuration file, read the theme name and description
                    if os.path.exists(config_file):
                        try:
                            with open(config_file, "r", encoding="utf-8") as f:
                                config = json.load(f)
                                theme_info["name"] = config.get("name", item)
                                theme_info["description"] = config.get(
                                    "description", ""
                                )
                        except Exception as e:
                            print(f"Error reading theme configuration file: {str(e)}")

                    themes.append(theme_info)

    # Ensure Normal theme always exists
    normal_exists = any(theme["id"] == "openmanus" for theme in themes)
    if not normal_exists:
        themes.append(
            {"id": "openmanus", "name": "Manus", "description": "Default theme"}
        )

    return themes


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # Get available theme list
    themes = get_available_themes()

    # Sort themes: Normal first, cyberpunk second, other themes in original order
    sorted_themes = []
    normal_theme = None
    cyberpunk_theme = None
    other_themes = []

    for theme in themes:
        if theme["id"] == "openmanus":
            normal_theme = theme
        elif theme["id"] == "cyberpunk":
            cyberpunk_theme = theme
        else:
            other_themes.append(theme)

    # Combine themes in specified order
    if normal_theme:
        sorted_themes.append(normal_theme)
    if cyberpunk_theme:
        sorted_themes.append(cyberpunk_theme)
    sorted_themes.extend(other_themes)

    return templates.TemplateResponse(
        "index.html", {"request": request, "themes": sorted_themes}
    )


@app.get("/chat", response_class=HTMLResponse)
async def chat(request: Request):
    theme = request.query_params.get("theme", "openmanus")
    # Try to load chat.html from theme folder
    theme_chat_path = f"web/static/themes/{theme}/templates/chat.html"
    if os.path.exists(theme_chat_path):
        with open(theme_chat_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Read theme configuration file
        theme_config_path = f"web/static/themes/{theme}/theme.json"
        theme_name = theme
        if os.path.exists(theme_config_path):
            try:
                with open(theme_config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    theme_name = config.get("name", theme)
            except Exception:
                pass

        # Add theme name to HTML title
        content = content.replace(
            "<title>Manus</title>", f"<title>Manus - {theme_name}</title>"
        )
        return HTMLResponse(content=content)
    else:
        # Default use templates chat.html
        return templates.TemplateResponse("chat.html", {"request": request})


@app.get("/download")
async def download_file(file_path: str):
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path, filename=os.path.basename(file_path))


@app.post("/tasks")
async def create_task(prompt: str = Body(..., embed=True)):
    task = task_manager.create_task(prompt)
    asyncio.create_task(run_task(task.id, prompt))
    return {"task_id": task.id}


from app.agent.manus import Manus


async def run_task(task_id: str, prompt: str):
    try:
        task_manager.tasks[task_id].status = "running"

        agent = Manus(
            name="Manus",
            description="A versatile agent that can solve various tasks using multiple tools",
        )

        async def on_think(thought):
            await task_manager.update_task_step(task_id, 0, thought, "think")

        async def on_tool_execute(tool, input):
            await task_manager.update_task_step(
                task_id, 0, f"Executing tool: {tool}\nInput: {input}", "tool"
            )

        async def on_action(action):
            await task_manager.update_task_step(
                task_id, 0, f"Executing action: {action}", "act"
            )

        async def on_run(step, result):
            await task_manager.update_task_step(task_id, step, result, "run")

        from app.logger import logger

        class SSELogHandler:
            def __init__(self, task_id):
                self.task_id = task_id

            async def __call__(self, message):
                import re

                # Extract - Subsequent Content
                cleaned_message = re.sub(r"^.*? - ", "", message)

                event_type = "log"
                if "✨ Manus's thoughts:" in cleaned_message:
                    event_type = "think"
                elif "🛠️ Manus selected" in cleaned_message:
                    event_type = "tool"
                elif "🎯 Tool" in cleaned_message:
                    event_type = "act"
                elif "📝 Oops!" in cleaned_message:
                    event_type = "error"
                elif "🏁 Special tool" in cleaned_message:
                    event_type = "complete"

                await task_manager.update_task_step(
                    self.task_id, 0, cleaned_message, event_type
                )

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
            yield f"event: status\ndata: {dumps({'type': 'status', 'status': task.status, 'steps': task.steps})}\n\n"

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
                        yield f"event: status\ndata: {dumps({'type': 'status', 'status': task.status, 'steps': task.steps})}\n\n"
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
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/tasks")
async def get_tasks():
    sorted_tasks = sorted(
        task_manager.tasks.values(), key=lambda task: task.created_at, reverse=True
    )
    return JSONResponse(
        content=[task.model_dump() for task in sorted_tasks],
        headers={"Content-Type": "application/json"},
    )


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    if task_id not in task_manager.tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_manager.tasks[task_id]


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500, content={"message": f"Server error: {str(exc)}"}
    )


def open_local_browser(config):
    webbrowser.open_new_tab(f"http://{config['host']}:{config['port']}")


def load_config():
    try:
        config_path = Path(__file__).parent / "config" / "config.toml"

        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        return {"host": config["server"]["host"], "port": config["server"]["port"]}
    except FileNotFoundError:
        raise RuntimeError(
            "Configuration file not found, please check if config/fig.toml exists"
        )
    except KeyError as e:
        raise RuntimeError(
            f"The configuration file is missing necessary fields: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    config = load_config()
    open_with_config = partial(open_local_browser, config)
    threading.Timer(3, open_with_config).start()
    uvicorn.run(app, host=config["host"], port=config["port"])
