import json
from typing import Any, List, Literal, Union, Dict

from pydantic import Field

from app.agent.react import ReActAgent
from app.logger import logger
from app.prompt.toolcall import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.schema import AgentState, Message, ToolCall
from app.tool import CreateChatCompletion, Terminate, ToolCollection


TOOL_CALL_REQUIRED = "Tool calls required but none provided"


class ToolCallAgent(ReActAgent):
    """Base agent class for handling tool/function calls with enhanced abstraction"""

    name: str = "toolcall"
    description: str = "an agent that can execute tool calls."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = ToolCollection(
        CreateChatCompletion(), Terminate()
    )
    tool_choices: Literal["none", "auto", "required"] = "auto"
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    tool_calls: List[Union[ToolCall, Dict]] = Field(default_factory=list)  # Change here.

    max_steps: int = 30

    async def think(self) -> bool:
        """Process current state and decide next actions using tools"""
        if self.next_step_prompt:
            user_msg = Message.user_message(self.next_step_prompt)
            self.messages += [user_msg]

        # Get response with tool options
        response = await self.llm.ask_tool(
            messages=self.messages,
            system_msgs=[Message.system_message(self.system_prompt)]
            if self.system_prompt
            else None,
            tools=self.available_tools.to_params(),
            tool_choice=self.tool_choices,
        )
        if self.llm.model.startswith('gemini'):  # check if it is gemini
            self.tool_calls = response.tool_calls  # if gemini, it will be GeminiToolCallMessage
        else:
            self.tool_calls = response.tool_calls  # if openai, it will be ChatCompletionMessage

        # Log response info
        logger.info(f"✨ {self.name}'s thoughts: {response.content}")
        # Log the tools being prepared
        tool_names = []
        if self.tool_calls:
            if self.llm.model.startswith('gemini'):
                # If using Gemini, handle dictionaries
                tool_names = [call["function"]["name"] for call in self.tool_calls if call]
            else:
                # If using OpenAI, handle ToolCall objects
                tool_names = [call.function.name for call in self.tool_calls if call]
        logger.info(f"🛠️ {self.name} selected {len(tool_names)} tools to use")
        if tool_names:
            logger.info(f"🧰 Tools being prepared: {tool_names}")
        try:
            # Handle different tool_choices modes
            if self.tool_choices == "none":
                if self.tool_calls:
                    logger.warning(
                        f"🤔 Hmm, {self.name} tried to use tools when they weren't available!"
                    )
                if response.content:
                    self.memory.add_message(Message.assistant_message(response.content))
                    return True
                return False

            # Create and add assistant message
            assistant_msg = (
                Message.from_tool_calls(
                    content=response.content, tool_calls=self.tool_calls
                )
                if self.tool_calls and not self.llm.model.startswith('gemini')
                else Message.assistant_message(response.content)
            )
            self.memory.add_message(assistant_msg)

            if self.tool_choices == "required" and not self.tool_calls:
                return True  # Will be handled in act()

            # For 'auto' mode, continue with content if no commands but content exists
            if self.tool_choices == "auto" and not self.tool_calls:
                return bool(response.content)

            return bool(self.tool_calls)
        except Exception as e:
            logger.error(f"🚨 Oops! The {self.name}'s thinking process hit a snag: {e}")
            self.memory.add_message(
                Message.assistant_message(
                    f"Error encountered while processing: {str(e)}"
                )
            )
            return False

    async def act(self) -> str:
        """Execute tool calls and handle their results"""
        if not self.tool_calls:
            if self.tool_choices == "required":
                raise ValueError(TOOL_CALL_REQUIRED)

            # Return last message content if no tool calls
            return self.messages[-1].content or "No content or commands to execute"

        results = []
        for command in self.tool_calls:
            result = await self.execute_tool(command)
            # Add check here!
            if self.llm.model.startswith("gemini"):  # Check if it is Gemini
                tool_name = command["function"]["name"]
            else:
                tool_name = command.function.name
            logger.info(
                f"🎯 Tool '{tool_name}' completed its mission! Result: {result}"
            )

            # Add tool response to memory
            if self.llm.model.startswith("gemini"):  # check if it is gemini
                tool_msg = Message.tool_message(
                    content=result, tool_call_id=command["id"], name=command["function"]["name"]
                )
            else:
                tool_msg = Message.tool_message(
                    content=result, tool_call_id=command.id, name=command.function.name
                )
            self.memory.add_message(tool_msg)
            results.append(result)

        return "\n\n".join(results)

    async def execute_tool(self, command: Union[ToolCall, Dict]) -> str:
        """Execute a single tool call with robust error handling"""
        if not command:
            return "Error: Invalid command format"
        if self.llm.model.startswith("gemini"):  # check if it is gemini
            if not command["function"] or not command["function"]["name"]:
                return "Error: Invalid command format"
            name = command["function"]["name"]
        else:
            if not command.function or not command.function.name:
                return "Error: Invalid command format"
            name = command.function.name

        if name not in self.available_tools.tool_map:
            return f"Error: Unknown tool '{name}'"

        try:
            # Parse arguments
            if self.llm.model.startswith("gemini"):  # check if it is gemini
                args_str = command["function"].get("arguments") or "{}" # change here
                if isinstance(args_str, str):
                    try:
                        args = json.loads(args_str) # change here
                    except json.JSONDecodeError:
                        args = {} # change here
                else:
                    args = {} # change here
                # Extract 'query' specifically for GoogleSearch
                if name == "google_search":
                    query = args.get("query")
                    num_results = args.get("num_results") or 3
                    result = await self.available_tools.execute(name=name, tool_input={"query": query,"num_results":num_results})  # change here.
                else:
                    result = await self.available_tools.execute(name=name, tool_input=args)
            else:
                args = json.loads(command.function.arguments or "{}")
                result = await self.available_tools.execute(name=name, tool_input=args)

            # Format result for display
            observation = (
                f"Observed output of cmd `{name}` executed:\n{str(result)}"
                if result
                else f"Cmd `{name}` completed with no output"
            )

            # Handle special tools like `finish`
            await self._handle_special_tool(name=name, result=result)

            return observation
        except json.JSONDecodeError:
            error_msg = f"Error parsing arguments for {name}: Invalid JSON format"
            logger.error(
                f"📝 Oops! The arguments for '{name}' don't make sense - invalid JSON, arguments:{command.function.arguments}"
            )
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"⚠️ Tool '{name}' encountered a problem: {str(e)}"
            logger.error(error_msg)
            return f"Error: {error_msg}"

    async def _handle_special_tool(self, name: str, result: Any, **kwargs):
        """Handle special tool execution and state changes"""
        if not self._is_special_tool(name):
            return

        if self._should_finish_execution(name=name, result=result, **kwargs):
            # Set agent state to finished
            logger.info(f"🏁 Special tool '{name}' has completed the task!")
            self.state = AgentState.FINISHED

    @staticmethod
    def _should_finish_execution(**kwargs) -> bool:
        """Determine if tool execution should finish the agent"""
        return True

    def _is_special_tool(self, name: str) -> bool:
        """Check if tool name is in special tools list"""
        return name.lower() in [n.lower() for n in self.special_tool_names]