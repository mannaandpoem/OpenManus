import json
from typing import Any, Dict, List

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.logger import logger
from app.schema import AgentState, Message, ToolCall
from app.tool import (
    ToolCollection,
)

class FixedToolCallAgent(ToolCallAgent):
    """
    Agent that executes a fixed sequence of tools, potentially terminating
    early if the validator tool indicates completion.
    """

    name: str = "fixed_toolcall"
    description: str = (
        "an agent that executes a fixed sequence of tools in predefined order, "
        "potentially terminating early based on validator feedback."
    )

    available_tools: ToolCollection = ToolCollection()

    fixed_tools: List[Dict[str, Any]] = []
    # Configurable names and phrase for termination logic
    terminate_tool_name: str = "terminate"
    validator_tool_name: str = "validator"
    validator_termination_phrase: str = "No further feedback."

    current_tool_index: int = Field(
        0, description="Index of the current tool in the sequence"
    )
    max_steps: int = 30
    current_step: int = 0

    async def cleanup(self):
        pass

    def set_fixed_tools(self, tools: List[Dict[str, Any]]):
        """Set the sequence of tools to execute"""
        self.fixed_tools = tools
        self.current_tool_index = 0
        self.current_step = 0

    async def think(self) -> bool:
        """
        Decide the next tool. Prioritize max_steps termination.
        Then, check if the last tool was the validator and indicated completion,
        if so, select the terminate tool. Otherwise, select the next
        tool in the fixed sequence.
        """
        # 1. Check step limit first (highest priority)
        # Note: We check current_step against max_steps *before* incrementing it for the potential next step.
        if self.current_step >= self.max_steps:
            logger.warning(f"🔧 Maximum number of steps ({self.max_steps}) reached at step {self.current_step}. Terminating.")
            self.state = AgentState.FINISHED
            return False # No further action

        # 2. Check the result of the last executed tool for termination condition
        last_message = self.memory.messages[-1] if self.memory.messages else None
        should_terminate_based_on_validation = False
        if last_message and last_message.role == "tool":
            # Basic parsing of the observation message format
            # Assumes format: "Observed output of cmd `tool_name` executed:\nResult..."
            content = last_message.content
            last_tool_name = None
            last_tool_result = ""
            if content.startswith("Observed output of cmd"):
                try:
                    # Extract tool name (between backticks)
                    parts = content.split("`", 2)
                    if len(parts) >= 2:
                        last_tool_name = parts[1]

                    # Extract result (after colon and newline)
                    # Using split(':\n', 1) might be fragile if format varies.
                    # Consider more robust parsing if necessary.
                    result_part = content.split(":\n", 1)
                    if len(result_part) > 1:
                        last_tool_result = result_part[1].strip()

                    # Check for termination condition
                    term_cond_name_match = (last_tool_name == self.validator_tool_name)
                    term_cond_phrase_match = (self.validator_termination_phrase in last_tool_result)
                    logger.info(f"Termination check: {term_cond_phrase_match}")

                    if term_cond_name_match and term_cond_phrase_match:
                        should_terminate_based_on_validation = True
                        logger.info(f"✅ Validator ({self.validator_tool_name}) indicates completion. Preparing termination.")
                    else:
                        # Explicitly log why termination is NOT happening, if validator was the last tool
                        if last_tool_name == self.validator_tool_name:
                             logger.info(f"ℹ️ Validator ({self.validator_tool_name}) ran, but did not meet termination criteria.")

                except Exception as e:
                    # Log error but proceed, as termination condition might not be met
                    logger.error(f"Error parsing last tool message content: {content}, error: {e}")


        # 3. If validator indicated termination, prepare the terminate tool call
        if should_terminate_based_on_validation:
            terminate_call = ToolCall(
                id=f"call_terminate_{self.current_step}", # ID reflects the step triggering termination
                function={
                    "name": self.terminate_tool_name,
                    "arguments": json.dumps({"status": "success"}) # Default success status
                }
            )
            self.tool_calls = [terminate_call]
            # Do NOT increment current_step here. It will be incremented after the tool execution.

            assistant_msg = Message.from_tool_calls(
                content=f"Terminating sequence based on {self.validator_tool_name} feedback.",
                tool_calls=self.tool_calls
            )
            self.memory.add_message(assistant_msg)
            # The Terminate tool itself should handle setting AgentState.FINISHED upon its execution
            return True # Indicate a tool call is ready

        # 4. --- Regular Logic: Proceed with the fixed sequence if not terminated ---
        if not self.fixed_tools:
            logger.warning("🔧 No fixed tools defined. Agent cannot proceed.")
            self.state = AgentState.FINISHED # No tools to run
            return False

        # Get the current tool from the sequence using the current index
        # Ensure index is valid before accessing
        if self.current_tool_index >= len(self.fixed_tools):
             logger.error(f"Error: current_tool_index ({self.current_tool_index}) is out of bounds for fixed_tools (len {len(self.fixed_tools)}). Resetting index to 0.")
             self.current_tool_index = 0 # Reset index as a safety measure

        current_tool_spec = self.fixed_tools[self.current_tool_index]

        # Create a ToolCall object for the selected tool
        tool_call = ToolCall(
            id=f"call_{self.current_step}_{self.current_tool_index}", # Unique ID per step/index
            function={
                "name": current_tool_spec["name"],
                "arguments": json.dumps(current_tool_spec.get("arguments", {}))
            }
        )

        # Set the tool call for execution
        self.tool_calls = [tool_call]

        # Do NOT increment current_step here. It will be incremented after the tool execution.
        # Instead, prepare the next index for the *next* think cycle
        next_index = (self.current_tool_index + 1) % len(self.fixed_tools)

        # Add assistant message to memory indicating the planned execution for the *current* step
        assistant_msg = Message.from_tool_calls(
            # Log the step number that *will* execute this tool
            content=f"Executing tool {current_tool_spec['name']} as step {self.current_step}",
            tool_calls=self.tool_calls
        )
        self.memory.add_message(assistant_msg)

        # Now update the index for the next iteration
        self.current_tool_index = next_index

        return True # Indicate a tool call is ready
