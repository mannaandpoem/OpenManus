import asyncio
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from loguru import logger as _logger

from app.agent.manus import Manus
from app.config import PROJECT_ROOT
from app.logger import (
    define_log_level, 
    logger, 
    register_websocket_manager, 
    unregister_websocket_manager, 
    websocket_sink,
    _print_level
)
from app.prompt.templates import standard_prompt_template, file_upload_prompt_template


class ConnectionManager:
    """Manages WebSocket connections and broadcasts messages to clients."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_agents: Dict[str, Manus] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept a new WebSocket connection and store it."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.connection_agents[client_id] = Manus()
    
    def disconnect(self, client_id: str) -> None:
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.connection_agents:
            del self.connection_agents[client_id]
    
    async def send_message(self, client_id: str, message: str, message_type: str = "log") -> None:
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json({
                "type": message_type,
                "content": message,
                "timestamp": datetime.now().isoformat()
            })
    
    async def broadcast(self, message: str, message_type: str = "log") -> None:
        """Send a message to all connected clients."""
        for client_id in list(self.active_connections.keys()):
            await self.send_message(client_id, message, message_type)
    
    def get_agent(self, client_id: str) -> Optional[Manus]:
        """Get the agent associated with a client."""
        return self.connection_agents.get(client_id)


# Create the FastAPI application
app = FastAPI()
manager = ConnectionManager()

# Register the connection manager with the logger
register_websocket_manager("websocket_server", manager)

@app.on_event("startup")
async def startup_event():
    """Add the websocket sink when the FastAPI app starts."""
    # Now we have a running event loop
    _logger.add(websocket_sink, level=_print_level, enqueue=True)
    logger.info("WebSocket logging sink registered")


class WebSocketLogger:
    """Custom logger that sends logs to a WebSocket client."""
    
    def __init__(self, client_id: str, manager: ConnectionManager):
        self.client_id = client_id
        self.manager = manager
    
    async def log(self, level: str, message: str) -> None:
        """Log a message with the specified level."""
        await self.manager.send_message(self.client_id, message, level.lower())
    
    async def info(self, message: str) -> None:
        """Log an info message."""
        logger.info(message)
    
    async def warning(self, message: str) -> None:
        """Log a warning message."""
        logger.warning(message)
    
    async def error(self, message: str) -> None:
        """Log an error message."""
        logger.error(message)
    
    async def debug(self, message: str) -> None:
        """Log a debug message."""
        logger.debug(message)
    
    async def critical(self, message: str) -> None:
        """Log a critical message."""
        logger.critical(message)


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """Handle WebSocket connections and messages."""
    await manager.connect(websocket, client_id)
    ws_logger = WebSocketLogger(client_id, manager)
    
    try:
        # Welcome message
        await ws_logger.info(f"Connected as client {client_id}")
        
        while True:
            # Wait for messages from the client
            data = await websocket.receive_json()
            
            if "prompt" in data:
                prompt = data["prompt"]
                await ws_logger.info(f"Processing prompt: {prompt}")
                
                # Wrap the prompt in a template
                templated_prompt = standard_prompt_template(prompt)
                
                # Run the agent with the templated prompt
                agent = manager.get_agent(client_id)
                if agent:
                    # Replace the logger with our WebSocket logger for this run
                    original_logger = agent.logger if hasattr(agent, "logger") else None
                    agent.logger = ws_logger
                    
                    try:
                        await agent.run(templated_prompt)
                    finally:
                        # Restore the original logger
                        if original_logger:
                            agent.logger = original_logger
                else:
                    await ws_logger.error("Agent not found")
            
            elif "command" in data:
                command = data["command"]
                if command == "exit":
                    await ws_logger.info("Goodbye!")
                    break
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        await ws_logger.error(f"An error occurred: {str(e)}")
        manager.disconnect(client_id)

@app.post("/upload/{client_id}")
async def upload_files(client_id: str, files: List[UploadFile] = File(...), 
                      prompt: Optional[str] = Form(None)):
    """Handle file uploads."""
    # Create tmp directory if it doesn't exist
    tmp_dir = PROJECT_ROOT / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    
    uploaded_files = []
    
    for file in files:
        file_location = tmp_dir / file.filename
        
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
        
        uploaded_files.append(str(file_location))
    
    # If the client is connected, send a message about the uploaded files
    if client_id in manager.active_connections:
        await manager.send_message(
            client_id,
            f"Uploaded {len(uploaded_files)} files: {', '.join(uploaded_files)}",
            "upload"
        )
    
    # If a prompt was provided, process it
    if prompt and client_id in manager.active_connections:
        agent = manager.get_agent(client_id)
        if agent:
            ws_logger = WebSocketLogger(client_id, manager)
            original_logger = agent.logger if hasattr(agent, "logger") else None
            agent.logger = ws_logger
            
            try:
                # Wrap the prompt in a file upload template that includes the uploaded file names
                templated_prompt = file_upload_prompt_template(prompt, uploaded_files)
                await ws_logger.info(f"Processing upload prompt: {prompt}")
                await agent.run(templated_prompt)
            finally:
                if original_logger:
                    agent.logger = original_logger
    
    return {"uploaded_files": uploaded_files, "prompt_processed": bool(prompt)}

def start_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the FastAPI server with uvicorn."""
    import uvicorn
    
    # Setup
    logger.info(f"Starting WebSocket server on {host}:{port}")
    
    # We'll add the websocket sink in app startup event instead
    try:
        uvicorn.run(app, host=host, port=port)
    finally:
        # Cleanup when server stops
        unregister_websocket_manager("websocket_server")