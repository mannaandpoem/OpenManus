from abc import ABC, abstractmethod
import json
import re
from typing import Optional, Union, Dict, Any, List

from pydantic import Field

from app.agent.base import BaseAgent
from app.llm import LLM
from app.logger import logger
from app.schema import AgentState, Memory, Message, ToolCall, Function


class ReActAgent(BaseAgent, ABC):
    name: str
    description: Optional[str] = None

    system_prompt: Optional[str] = None
    next_step_prompt: Optional[str] = None

    llm: Optional[LLM] = Field(default_factory=LLM)
    memory: Memory = Field(default_factory=Memory)
    state: AgentState = AgentState.IDLE

    max_steps: int = 10
    current_step: int = 0

    @abstractmethod
    async def think(self) -> bool:
        """Process current state and decide next action"""

    @abstractmethod
    async def act(self) -> Union[str, Dict[str, Any]]:
        """Execute decided actions"""

    async def step(self) -> Union[str, Dict[str, Any]]:
        """Execute a single step: think and act."""
        should_act = await self.think()
        if not should_act:
            # Check the last message to see if it's a question that needs user input
            try:
                if self.memory.messages and len(self.memory.messages) > 0:
                    last_message = self.memory.messages[-1]
                    if last_message.role == "assistant" and last_message.content:
                        if self._is_asking_question(last_message.content):
                            logger.info(f"🔄 Detected question in assistant response, converting to ask_user call: {last_message.content}")
                            
                            # Truncate and sanitize the message if it's too long
                            question_text = last_message.content
                            max_length = 300  # More conservative size
                            if len(question_text) > max_length:
                                question_text = question_text[:max_length] + "..."
                                
                            # Replace newlines with spaces for cleaner display
                            question_text = question_text.replace('\n', ' ').replace('\r', ' ')
                                
                            # Create a user input request with simpler content
                            return {
                                "observation": f"❓ FOLLOW-UP: {question_text}\n\nPlease reply directly to this message with your response:",
                                "success": True,
                                "requires_user_response": True
                            }
            except Exception as e:
                logger.error(f"Error checking for questions in assistant response: {str(e)}")
                # Continue with normal execution
            
            return "Thinking complete - no action needed"
        
        return await self.act()
        
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
            max_length = 300  # More conservative size
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
