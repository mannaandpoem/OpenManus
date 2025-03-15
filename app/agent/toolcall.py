import json
import re
from typing import Any, Dict, List, Optional, Union

from pydantic import Field

from app.agent.react import ReActAgent
from app.exceptions import TokenLimitExceeded
from app.logger import logger
from app.prompt.toolcall import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.schema import TOOL_CHOICE_TYPE, AgentState, Message, ToolCall, ToolChoice, Function
from app.tool import CreateChatCompletion, Terminate, ToolCollection
from app.tool.ask_user import AskUser


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
    tool_choices: TOOL_CHOICE_TYPE = ToolChoice.AUTO  # type: ignore
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    tool_calls: List[ToolCall] = Field(default_factory=list)

    max_steps: int = 30
    max_observe: Optional[Union[int, bool]] = None

    async def think(self) -> bool:
        """Process current state and decide next actions using tools"""
        if self.next_step_prompt:
            user_msg = Message.user_message(self.next_step_prompt)
            self.messages += [user_msg]

        try:
            # Get response with tool options
            response = await self.llm.ask_tool(
                messages=self.messages,
                system_msgs=[Message.system_message(self.system_prompt)]
                if self.system_prompt
                else None,
                tools=self.available_tools.to_params(),
                tool_choice=self.tool_choices,
            )
        except ValueError:
            raise
        except Exception as e:
            # Check if this is a RetryError containing TokenLimitExceeded
            if hasattr(e, "__cause__") and isinstance(e.__cause__, TokenLimitExceeded):
                token_limit_error = e.__cause__
                logger.error(
                    f"🚨 Token limit error (from RetryError): {token_limit_error}"
                )
                self.memory.add_message(
                    Message.assistant_message(
                        f"Maximum token limit reached, cannot continue execution: {str(token_limit_error)}"
                    )
                )
                self.state = AgentState.FINISHED
                return False
            raise

        self.tool_calls = response.tool_calls

        # Log response info
        logger.info(f"✨ {self.name}'s thoughts: {response.content}")
        logger.info(
            f"🛠️ {self.name} selected {len(response.tool_calls) if response.tool_calls else 0} tools to use"
        )
        if response.tool_calls:
            logger.info(
                f"🧰 Tools being prepared: {[call.function.name for call in response.tool_calls]}"
            )

        try:
            # Handle different tool_choices modes
            if self.tool_choices == ToolChoice.NONE:
                if response.tool_calls:
                    logger.warning(
                        f"🤔 Hmm, {self.name} tried to use tools when they weren't available!"
                    )
                if response.content:
                    self.memory.add_message(Message.assistant_message(response.content))
                    return True
                return False

            # If no tools selected but response appears to be asking a question
            # Automatically convert it to an ask_user tool call
            if not self.tool_calls and response.content:
                try:
                    if self._is_asking_question(response.content):
                        logger.info(f"🔄 Converting question to ask_user tool call: {response.content}")
                        
                        # Use the safe method to create the tool call
                        self.tool_calls = self._create_ask_user_tool_call(response.content)
                        
                        # Only proceed if we successfully created the tool call
                        if self.tool_calls:
                            # Create and add the assistant message
                            assistant_msg = Message.from_tool_calls(
                                content=f"I need to get more information from you", 
                                tool_calls=self.tool_calls
                            )
                            self.memory.add_message(assistant_msg)
                            return True
                except Exception as e:
                    logger.error(f"Error converting question to ask_user tool call: {str(e)}")
                    # Fall through to normal processing

            # Create and add assistant message
            assistant_msg = (
                Message.from_tool_calls(
                    content=response.content, tool_calls=self.tool_calls
                )
                if self.tool_calls
                else Message.assistant_message(response.content)
            )
            self.memory.add_message(assistant_msg)

            if self.tool_choices == ToolChoice.REQUIRED and not self.tool_calls:
                return True  # Will be handled in act()

            # For 'auto' mode, continue with content if no commands but content exists
            if self.tool_choices == ToolChoice.AUTO and not self.tool_calls:
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

    async def act(self) -> Union[str, Dict[str, Any]]:
        """Execute tool calls and handle their results"""
        if not self.tool_calls:
            if self.tool_choices == ToolChoice.REQUIRED:
                raise ValueError(TOOL_CALL_REQUIRED)

            # Return last message content if no tool calls
            return self.messages[-1].content or "No content or commands to execute"

        results = []
        for command in self.tool_calls:
            result = await self.execute_tool(command)
            
            # Special handling for tools requiring user input
            if isinstance(result, dict) and result.get("requires_user_response", False):
                # Add tool response to memory
                tool_msg = Message.tool_message(
                    content=str(result), tool_call_id=command.id, name=command.function.name
                )
                self.memory.add_message(tool_msg)
                
                # Return the result directly to trigger user input
                return result

            if self.max_observe:
                result = result[: self.max_observe]

            logger.info(
                f"🎯 Tool '{command.function.name}' completed its mission! Result: {result}"
            )

            # Add tool response to memory
            tool_msg = Message.tool_message(
                content=result, tool_call_id=command.id, name=command.function.name
            )
            self.memory.add_message(tool_msg)
            results.append(result)

        return "\n\n".join(results)

    async def execute_tool(self, command: ToolCall) -> Union[str, Dict[str, Any]]:
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
            result = await self.available_tools.execute(name=name, tool_input=args)

            # If the tool result is a dictionary and contains requires_user_response flag,
            # return it directly to trigger user input handling
            if isinstance(result, dict) and result.get("requires_user_response", False):
                return result

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

        # Check for ask_user tool - this should not terminate execution
        if name.lower() == "ask_user":
            logger.info(f"✋ Special tool '{name}' is waiting for user input.")
            return

        # For other special tools like terminate
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

    def _is_asking_question(self, text: str) -> bool:
        """
        Detects if the given text is asking a question or requesting input from the user.
        
        Args:
            text: The text to analyze
            
        Returns:
            bool: True if the text appears to be asking for user input
        """
        # Skip status/information messages that just happen to contain question patterns
        if text.startswith("I successfully") or "sum of" in text.lower() or "sum is" in text.lower():
            return False
            
        # Check for question marks
        if "?" in text:
            return True
            
        # Common question patterns
        question_patterns = [
            r"(?i)would you like",
            r"(?i)do you want",
            r"(?i)can you",
            r"(?i)could you",
            r"(?i)please provide",
            r"(?i)please let me know",
            r"(?i)please specify",
            r"(?i)tell me",
            r"(?i)what.*(?:would|should|can|could)",
            r"(?i)how.*(?:would|should|can|could)",
            r"(?i)which.*(?:option|choice)",
            # Don't treat "if you need any further assistance, let me know" as a question
            # r"(?i)let me know",
            r"(?i)if you have",
            r"(?i)if you would like",
        ]
        
        for pattern in question_patterns:
            if re.search(pattern, text):
                # Don't treat closing statements as questions
                if pattern == r"(?i)please let me know" and ("if you need" in text.lower() or "further assistance" in text.lower()):
                    return False
                return True
                
        return False

    # Add this method to handle safe conversion to ask_user tool
    def _create_ask_user_tool_call(self, question_text: str) -> List[ToolCall]:
        """
        Safely create an ask_user tool call from a question text.
        
        Args:
            question_text: The text of the question
            
        Returns:
            List[ToolCall]: A list containing the ask_user tool call
        """
        try:
            # Trim question text if too long to prevent JSON serialization issues
            max_length = 500
            if len(question_text) > max_length:
                question_text = question_text[:max_length] + "..."
                
            # Sanitize question text for JSON 
            # Replace newlines with spaces and escape quotes for JSON safety
            question_text = question_text.replace('\n', ' ').replace('\r', ' ')
            
            # Create the arguments as a proper Python dictionary first
            args = {
                "question": question_text,
                "dangerous_action": False,
                "question_type": "follow-up"
            }
            
            # Convert to JSON with error handling
            try:
                args_json = json.dumps(args)
            except Exception as json_err:
                logger.error(f"JSON serialization error: {str(json_err)}, using simplified question")
                # Try with simpler text if JSON fails
                args = {
                    "question": "I need more information to proceed. Please provide details.",
                    "dangerous_action": False,
                    "question_type": "follow-up"
                }
                args_json = json.dumps(args)
                
            # Create the function object using the schema's Function class
            try:
                function_obj = Function(
                    name="ask_user",
                    arguments=args_json
                )
            except Exception as func_err:
                logger.error(f"Error creating Function object: {str(func_err)}, {type(func_err)}")
                return []
                
            # Create the full tool call
            try:
                ask_user_tool = ToolCall(
                    id="auto_ask_user",
                    type="function",
                    function=function_obj
                )
                return [ask_user_tool]
            except Exception as tool_err:
                logger.error(f"Error creating ToolCall object: {str(tool_err)}, {type(tool_err)}")
                return []
                
        except Exception as e:
            logger.error(f"Error creating ask_user tool call: {str(e)}, {type(e)}")
            logger.error(f"Question text causing error: '{question_text[:100]}...'")
            return []
