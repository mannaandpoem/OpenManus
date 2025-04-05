import json
from typing import Any, Dict, List

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.exceptions import TokenLimitExceeded
from app.logger import logger
from app.schema import AgentState, Message, ToolCall
from app.tool import (
    Terminate,
    ToolCollection,
    Validator,
    LatexGenerator
)

class FixedToolCallAgent(ToolCallAgent):
    """Agent that executes a fixed sequence of tools"""

    name: str = "fixed_toolcall"
    description: str = (
        "an agent that executes a fixed sequence of tools in predefined order"
    )

    available_tools: ToolCollection = ToolCollection()

    # 存储工具名称和参数
    fixed_tools: List[Dict[str, Any]] = []

    current_tool_index: int = Field(
        0, description="Index of the current tool in the sequence"
    )
    max_steps: int = 30
    current_step: int = 0

    def set_fixed_tools(self, tools: List[Dict[str, Any]]):
        """Set the sequence of tools to execute"""
        self.fixed_tools = tools
        self.current_tool_index = 0
        self.current_step = 0

    async def think(self) -> bool:
        """Select the next tool in the fixed sequence without calling LLM"""
        if not self.fixed_tools:
            logger.warning("🔧 No fixed tools defined. Agent cannot proceed.")
            return False

        # Check if we've reached the maximum number of steps
        if self.current_step >= self.max_steps:
            logger.warning("🔧 Maximum number of steps reached.")
            self.state = AgentState.FINISHED
            return False

        # Get the current tool from the sequence
        current_tool = self.fixed_tools[self.current_tool_index]

        # Create a ToolCall object from the current tool
        tool_call = ToolCall(
            id=f"call_{self.current_tool_index}",
            function={
                "name": current_tool["name"],
                "arguments": json.dumps(current_tool.get("arguments", {}))
            }
        )

        # Set the tool call for execution
        self.tool_calls = [tool_call]

        # Increment the index for next time
        self.current_tool_index = (self.current_tool_index + 1) % len(self.fixed_tools)
        self.current_step += 1

        # Add assistant message to memory
        assistant_msg = Message.from_tool_calls(
            content=f"Executing tool {current_tool['name']}",
            tool_calls=self.tool_calls
        )
        self.memory.add_message(assistant_msg)

        return True
