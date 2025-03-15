from typing import Any, Dict

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.prompt.manus import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Terminate, ToolCollection
from app.tool.ask_user import AskUser
from app.tool.browser_use_tool import BrowserUseTool
from app.tool.file_saver import FileSaver
from app.tool.python_execute import PythonExecute
from app.tool.terminal import Terminal
from app.tool.web_search import WebSearch


class Manus(ToolCallAgent):
    """
    A versatile general-purpose agent that uses planning to solve various tasks.

    This agent extends PlanningAgent with a comprehensive set of tools and capabilities,
    including Python execution, web browsing, file operations, and information retrieval
    to handle a wide range of user requests.
    """

    name: str = "Manus"
    description: str = (
        "A versatile agent that can solve various tasks using multiple tools"
    )

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    max_observe: int = 2000
    max_steps: int = 20

    # Add general-purpose tools to the tool collection
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            PythonExecute(), 
            WebSearch(), 
            BrowserUseTool(), 
            FileSaver(), 
            Terminal(),
            AskUser(),
            Terminate()
        )
    )
    
    # Add AskUser to the special tools list
    special_tool_names: list = Field(default_factory=lambda: [Terminate().name, AskUser().name])

    async def _handle_special_tool(self, name: str, result: Any, **kwargs):
        if not self._is_special_tool(name):
            return
            
        # For AskUser tool, we don't want to finish execution
        if name.lower() == AskUser().name.lower():
            # The tool has already returned a message to the user
            # The agent will continue execution when the user responds
            return
            
        # For other special tools like Terminate
        await self.available_tools.get_tool(BrowserUseTool().name).cleanup()
        await super()._handle_special_tool(name, result, **kwargs)
    
    @staticmethod
    def _should_finish_execution(name: str, result: Any, **kwargs) -> bool:
        """Determine if tool execution should finish the agent"""
        # Don't finish execution for ask_user tool
        if name.lower() == AskUser().name.lower():
            return False
        return True
