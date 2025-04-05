import json
from typing import List

from pydantic import Field
from typing import Any, Dict, List
from app.logger import logger
from app.schema import ToolCall

from app.agent.fixtoolcall import FixedToolCallAgent
from app.tool import Terminate, Validator, ToolCollection, LatexGenerator

class PPTAgent(FixedToolCallAgent):
    """An agent that implements the validate paradigm."""

    name: str = "PPTAgent"
    description: str = "An AI-driven generation agent that produces answer with validation process."

    available_tools: ToolCollection = ToolCollection(
        LatexGenerator(), Validator()
    )

    fixed_tools: List[Dict[str, Any]] = [
        {"name": "latexgenerator", "arguments": {}},
        {"name": "validator", "arguments": {}},
    ]
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    max_steps: int = 30

    working_dir: str = "."

    async def execute_tool(self, command: ToolCall) -> str:
        """Execute a single tool call with robust error handling"""
        if not command or not command.function or not command.function.name:
            return "Error: Invalid command format"

        name = command.function.name
        if name not in self.available_tools.tool_map:
            return f"Error: Unknown tool '{name}'"

        try:
            # Parse arguments
            args = json.loads(command.function.arguments or "{}")

            # Execute the tool
            logger.info(f"🔧 Activating tool: '{name}'...")
            if name != 'terminate':
                # Get the first message from memory if it exists
                if self.memory and self.memory.messages:
                    args['request'] = self.memory.messages[0].content
                    args['history'] = str(self.memory.messages)
                result = await self.available_tools.execute(name=name, tool_input=args)
            else:
                # For terminate tool, ensure status is provided
                if 'status' not in args:
                    args['status'] = 'success'  # Default to success if not specified
                result = await self.available_tools.execute(name=name, tool_input=args)

            # Handle special tools
            await self._handle_special_tool(name=name, result=result)

            # Format result for display (standard case)
            observation = (
                f"Observed output of cmd `{name}` executed:\n{str(result)}"
                if result
                else f"Cmd `{name}` completed with no output"
            )

            return observation
        except json.JSONDecodeError:
            error_msg = f"Error parsing arguments for {name}: Invalid JSON format"
            logger.error(
                f"📝 Oops! The arguments for '{name}' don't make sense - invalid JSON, arguments:{command.function.arguments}"
            )
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"⚠️ Tool '{name}' encountered a problem: {str(e)}"
            logger.exception(error_msg)
            return f"Error: {error_msg}"
