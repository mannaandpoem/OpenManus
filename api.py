from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List
from app.config import config
from app.agent.manus import Manus
from app.agent.planning import PlanningAgent
from app.agent.swe import SWEAgent
from app.flow.flow_factory import FlowFactory
from app.logger import get_logs

app = FastAPI(
    title="OpenManus API",
    description="API for OpenManus AI Assistant",
    version="0.1.0"
)

# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有源访问，生产环境建议设置具体的源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有请求头
)

class ChatRequest(BaseModel):
    message: str
    agent_type: str = "manus"  # manus, planning, or swe
    flow_type: str | None = None

class ChatResponse(BaseModel):
    response: str
    agent_type: str
    flow_type: str | None = None

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """处理聊天请求并返回AI助手的响应"""
    try:
        # 根据请求类型选择合适的Agent
        if request.agent_type == "manus":
            agent = Manus()
        elif request.agent_type == "planning":
            agent = PlanningAgent()
        elif request.agent_type == "swe":
            agent = SWEAgent()
        else:
            raise HTTPException(status_code=400, detail=f"不支持的agent类型: {request.agent_type}")

        # 如果指定了flow_type，使用FlowFactory创建flow
        if request.flow_type:
            flow = FlowFactory.create_flow(request.flow_type)
            response = await flow.run(request.message)
        else:
            response = await agent.run(request.message)

        return ChatResponse(
            response=response,
            agent_type=request.agent_type,
            flow_type=request.flow_type
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/config")
async def get_config() -> Dict[str, Any]:
    """获取当前系统配置信息"""
    return {"llm": config.llm}

@app.get("/logs")
async def get_system_logs() -> Dict[str, List[str]]:
    """获取系统日志信息"""
    logs = get_logs()
    return {"logs": logs}

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8008)
