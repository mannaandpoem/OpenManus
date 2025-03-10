import uvicorn
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from loguru import logger as _logger
from app.agent.manus import Manus
from app.logger import logger

app = FastAPI()
agent = Manus()
log_queue = asyncio.Queue()  # using `asyncio.Queue` prevents blocking
templates = Jinja2Templates(directory="templates")

# Log Interceptor: Asynchronously store logs in the queue
async def log_intercept(message: str):
    message = message.strip()
    if message:
        await log_queue.put(message)

# Append log interceptor to `loguru` without affecting existing log handling
_logger.add(lambda msg: asyncio.create_task(log_intercept(msg)), format="{message}")

# Asynchronous log stream using `async for` for efficient real-time streaming
async def log_stream():
    while True:
        message = await log_queue.get()  # ✅ Waits for new log messages
        yield f"data: {message}\n\n"

@app.get("/logs")
async def stream_logs():
    """Frontend can access the real-time log stream via `/logs`"""
    return StreamingResponse(log_stream(), media_type="text/event-stream")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("web.html", {"request": request})

class PromptRequest(BaseModel):
    prompt: str

@app.post("/run")
async def run(request: PromptRequest):
    logger.warning("Processing your request...")
    result = await agent.run(request.prompt)  # ✅ Ensures `agent.run()` executes asynchronously
    return {"result": result}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
