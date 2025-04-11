import json
import time
from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import Field

from app.agent.base import BaseAgent
from app.flow.base import BaseFlow
from app.llm import LLM
from app.logger import logger
from app.schema import AgentState, Message, ToolChoice
from app.tool import PlanningTool
from app.tool.base import ToolResult
from app.tool.ask_human import HumanInterventionRequired

# Define a constant signal for human interaction
HUMAN_INTERACTION_SIGNAL = "__HUMAN_INTERACTION_OCCURRED__"


class PlanStepStatus(str, Enum):
    """Enum class defining possible statuses of a plan step"""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"

    @classmethod
    def get_all_statuses(cls) -> list[str]:
        """Return a list of all possible step status values"""
        return [status.value for status in cls]

    @classmethod
    def get_active_statuses(cls) -> list[str]:
        """Return a list of values representing active statuses (not started or in progress)"""
        return [cls.NOT_STARTED.value, cls.IN_PROGRESS.value]

    @classmethod
    def get_status_marks(cls) -> Dict[str, str]:
        """Return a mapping of statuses to their marker symbols"""
        return {
            cls.COMPLETED.value: "[✓]",
            cls.IN_PROGRESS.value: "[→]",
            cls.BLOCKED.value: "[!]",
            cls.NOT_STARTED.value: "[ ]",
        }


class PlanningFlow(BaseFlow):
    """A flow that manages planning and execution of tasks using agents."""

    llm: LLM = Field(default_factory=lambda: LLM())
    planning_tool: PlanningTool = Field(default_factory=PlanningTool)
    executor_keys: List[str] = Field(default_factory=list)
    active_plan_id: str = Field(default_factory=lambda: f"plan_{int(time.time())}")
    current_step_index: Optional[int] = None

    def __init__(
        self, agents: Union[BaseAgent, List[BaseAgent], Dict[str, BaseAgent]], **data
    ):
        # Set executor keys before super().__init__
        if "executors" in data:
            data["executor_keys"] = data.pop("executors")

        # Set plan ID if provided
        if "plan_id" in data:
            data["active_plan_id"] = data.pop("plan_id")

        # Initialize the planning tool if not provided
        if "planning_tool" not in data:
            planning_tool = PlanningTool()
            data["planning_tool"] = planning_tool

        # Call parent's init with the processed data
        super().__init__(agents, **data)

        # Set executor_keys to all agent keys if not specified
        if not self.executor_keys:
            self.executor_keys = list(self.agents.keys())

    def get_executor(self, step_type: Optional[str] = None) -> BaseAgent:
        """
        Get an appropriate executor agent for the current step.
        Can be extended to select agents based on step type/requirements.
        """
        # If step type is provided and matches an agent key, use that agent
        if step_type and step_type in self.agents:
            return self.agents[step_type]

        # Otherwise use the first available executor or fall back to primary agent
        for key in self.executor_keys:
            if key in self.agents:
                return self.agents[key]

        # Fallback to primary agent
        return self.primary_agent

    async def execute(self, input_text: str) -> str:
        """Execute the planning flow with agents."""
        try:
            if not self.primary_agent:
                raise ValueError("No primary agent available")

            # Create initial plan if input provided
            if input_text:
                await self._create_initial_plan(input_text)

                # Verify plan was created successfully
                if self.active_plan_id not in self.planning_tool.plans:
                    logger.error(
                        f"Plan creation failed. Plan ID {self.active_plan_id} not found in planning tool."
                    )
                    return f"Failed to create plan for: {input_text}"

            result = ""
            max_retries_per_step = 3 # Add a limit to avoid infinite loops on a step
            current_step_retries = 0
            last_step_index = -1

            while True:
                # Get current step to execute
                current_step_index_before_get = self.current_step_index
                self.current_step_index, step_info = await self._get_current_step_info()

                # Reset retry counter if we moved to a new step
                if self.current_step_index != last_step_index:
                     current_step_retries = 0
                     last_step_index = self.current_step_index
                else:
                     # We are on the same step, likely after human interaction or an error retry
                     current_step_retries += 1

                # Exit if no more steps or plan completed
                if self.current_step_index is None:
                    result += await self._finalize_plan()
                    break

                # Check for excessive retries on the same step
                if current_step_retries >= max_retries_per_step:
                     logger.error(f"Maximum retries ({max_retries_per_step}) exceeded for step {self.current_step_index}. Aborting.")
                     await self._mark_step_status(PlanStepStatus.BLOCKED.value, "Max retries exceeded")
                     result += "\nExecution aborted: Maximum retries exceeded for a step."
                     break

                # Execute current step with appropriate agent
                step_type = step_info.get("type") if step_info else None
                executor = self.get_executor(step_type)

                logger.info(f"Executing step {self.current_step_index} (Retry: {current_step_retries})")
                step_result = await self._execute_step(executor, step_info)

                # Check if human interaction occurred
                if step_result == HUMAN_INTERACTION_SIGNAL:
                    logger.info(f"Human interaction occurred for step {self.current_step_index}. Retrying step.")
                    # Don't add result, just continue to retry the same step
                    continue

                # Append the actual result if it wasn't just the interaction signal
                result += step_result + "\n"

                # Check if agent wants to terminate (This might need review - does it stop the whole flow?)
                if hasattr(executor, "state") and executor.state == AgentState.FINISHED:
                    logger.warning(f"Executor {executor.name} entered FINISHED state. Stopping flow.")
                    break

            return result
        except Exception as e:
            logger.error(f"Error in PlanningFlow: {str(e)}")
            return f"Execution failed: {str(e)}"

    async def _create_initial_plan(self, request: str) -> None:
        """Create an initial plan based on the request using the flow's LLM and PlanningTool."""
        logger.info(f"Creating initial plan with ID: {self.active_plan_id}")

        # Create a system message for plan creation (Updated based on Manus Gists)
        new_system_message_content = """
You are an expert planning assistant. Your goal is to create a detailed, step-by-step plan to accomplish a given task using available tools.

<planning_approach>
1.  **Decomposition:** Break down the main task into smaller, logically ordered, actionable steps. Each step should represent a clear, manageable unit of work. Avoid overly broad or vague steps.
2.  **Tool Awareness (Implicit):** Although you don't need to specify exact tool calls in the plan, formulate steps in a way that they likely correspond to actions achievable with tools like web search, browsing, code execution, or file manipulation. (For example, "Search for reviews of product X", "Extract key features from webpage Y", "Write a Python script to analyze data Z").
3.  **Clarity and Order:** Ensure the steps are in a logical sequence. The output of one step might be needed for the next.
4.  **Completeness:** The plan should cover all necessary stages from start to finish to fully address the user's request.
5.  **Conciseness:** While detailed, avoid unnecessary verbosity in step descriptions.
</planning_approach>

<output_format>
- You MUST call the 'planning' tool to submit the generated plan.
- Provide the plan as a list of strings in the 'steps' parameter of the tool call.
- Provide a concise 'title' for the plan.
</output_format>

Analyze the user's request carefully and generate the plan by calling the 'planning' tool.
"""
        system_message = Message.system_message(new_system_message_content)

        # Create a user message with the request (Updated)
        user_message = Message.user_message(
            f"Create a detailed, step-by-step plan to accomplish the task: {request}"
        )

        # Call LLM with PlanningTool (Consider adding low temperature)
        response = await self.llm.ask_tool(
            messages=[user_message],
            system_msgs=[system_message],
            tools=[self.planning_tool.to_param()],
            tool_choice=ToolChoice.AUTO,
            temperature=0.2, # Explicitly set a low temperature for planning
        )

        # Process tool calls if present
        if response.tool_calls:
            for tool_call in response.tool_calls:
                if tool_call.function.name == "planning":
                    # Parse the arguments
                    args = tool_call.function.arguments
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse tool arguments: {args}")
                            continue

                    # Ensure plan_id is set correctly and execute the tool
                    args["plan_id"] = self.active_plan_id

                    # Execute the tool via ToolCollection instead of directly
                    result = await self.planning_tool.execute(**args)

                    logger.info(f"Plan creation result: {str(result)}")
                    return

        # If execution reached here, create a default plan
        logger.warning("Creating default plan")

        # Create default plan using the ToolCollection
        await self.planning_tool.execute(
            **{
                "command": "create",
                "plan_id": self.active_plan_id,
                "title": f"Plan for: {request[:50]}{'...' if len(request) > 50 else ''}",
                "steps": ["Analyze request", "Execute task", "Verify results"],
            }
        )

    async def _get_current_step_info(self) -> tuple[Optional[int], Optional[dict]]:
        """
        Parse the current plan to identify the first non-completed step's index and info.
        Returns (None, None) if no active step is found.
        """
        if (
            not self.active_plan_id
            or self.active_plan_id not in self.planning_tool.plans
        ):
            logger.error(f"Plan with ID {self.active_plan_id} not found")
            return None, None

        try:
            # Direct access to plan data from planning tool storage
            plan_data = self.planning_tool.plans[self.active_plan_id]
            steps = plan_data.get("steps", [])
            step_statuses = plan_data.get("step_statuses", [])

            # Find first non-completed step
            for i, step in enumerate(steps):
                if i >= len(step_statuses):
                    status = PlanStepStatus.NOT_STARTED.value
                else:
                    status = step_statuses[i]

                if status in PlanStepStatus.get_active_statuses():
                    # Extract step type/category if available
                    step_info = {"text": step}

                    # Try to extract step type from the text (e.g., [SEARCH] or [CODE])
                    import re

                    type_match = re.search(r"\[([A-Z_]+)\]", step)
                    if type_match:
                        step_info["type"] = type_match.group(1).lower()

                    # Mark current step as in_progress
                    try:
                        await self.planning_tool.execute(
                            command="mark_step",
                            plan_id=self.active_plan_id,
                            step_index=i,
                            step_status=PlanStepStatus.IN_PROGRESS.value,
                        )
                    except Exception as e:
                        logger.warning(f"Error marking step as in_progress: {e}")
                        # Update step status directly if needed
                        if i < len(step_statuses):
                            step_statuses[i] = PlanStepStatus.IN_PROGRESS.value
                        else:
                            while len(step_statuses) < i:
                                step_statuses.append(PlanStepStatus.NOT_STARTED.value)
                            step_statuses.append(PlanStepStatus.IN_PROGRESS.value)

                        plan_data["step_statuses"] = step_statuses

                    return i, step_info

            return None, None  # No active step found

        except Exception as e:
            logger.warning(f"Error finding current step index: {e}")
            return None, None

    async def _execute_step(self, executor: BaseAgent, step_info: dict) -> str:
        """Execute the current step with the specified agent using agent.run()."""
        # Prepare context for the agent with current plan status
        plan_status = await self._get_plan_text()
        step_text = step_info.get("text", f"Step {self.current_step_index}")

        # Create a prompt for the agent to execute the current step
        step_prompt = f"""
        CURRENT PLAN STATUS:
        {plan_status}

        YOUR CURRENT TASK:
        You are now working on step {self.current_step_index}: "{step_text}"

        YOUR OBJECTIVE:
        1. Execute the current step using the appropriate tools.
        2. **Analyze recent messages (especially user responses).** If information from the user indicates that any **FUTURE** steps in the plan (check CURRENT PLAN STATUS) are already completed or irrelevant, you MUST use the 'planning' tool to update their status BEFORE proceeding with the current step's main action.
           - Use command 'mark_step' with the correct 'step_index' for each future step that needs updating.
           - Set 'status' to 'completed' or 'blocked'.
           - Add a brief explanation in 'step_notes' (e.g., 'User confirmed completion', 'Made irrelevant by user input').
        3. If you get stuck on the current step (e.g., after 2-3 failed attempts), need information you cannot find, or require a user decision, use the 'ask_human' tool.
        4. When you are finished with this step (either successfully, by updating future steps, or by asking the human), provide a summary of what you accomplished or why you need help.
        """

        try:
            # We expect executor.run() to either return a string (success/error string from agent)
            # or raise HumanInterventionRequired if ask_human was used.
            step_result_str = await executor.run(step_prompt)

            # If no exception was raised, the step completed (or agent handled error internally)
            await self._mark_step_completed()
            return step_result_str

        except HumanInterventionRequired as hir:
            # Catch the exception raised by AskHuman (and re-raised by the agent)
            logger.info(f"Agent requested human input for tool_call_id: {hir.tool_call_id}")
            logger.info(f"   Question: {hir.question}")

            # --- Add Tool Result Message ---
            # Create a placeholder message indicating the tool was interrupted for human input
            interrupted_tool_content = f"Tool execution interrupted to ask user: {hir.question}"
            tool_result_message = Message.tool_message(
                content=interrupted_tool_content,
                tool_call_id=hir.tool_call_id,
                name="ask_human"
            )
            # Add the tool result message to memory *first*
            executor.update_memory(
                role="tool",
                content=interrupted_tool_content,
                tool_call_id=hir.tool_call_id,
                name="ask_human"
            )
            logger.info(f"Added interrupted tool result message to agent memory for ID {hir.tool_call_id}.")
            # -----------------------------

            # Now interact with the user
            print(f'\n🤖 Agent needs help with step {self.current_step_index} ("{step_text}"):')
            print(f'   Question: {hir.question}')

            try:
                user_response = input("👤 Your answer: ")
            except EOFError:
                logger.warning("EOF received, assuming no input.")
                user_response = "(No input provided)"

            logger.info(f"User provided response: {user_response}")

            # Inject user response back into agent memory using update_memory
            response_content = f'Regarding your question "{hir.question}": {user_response}'
            executor.update_memory(role="user", content=response_content)
            logger.info("User response injected into agent memory.")

            # Return the special signal for the main loop to retry the step
            return HUMAN_INTERACTION_SIGNAL

        except Exception as e:
            # Catch any other unexpected errors during executor.run()
            logger.error(f"Unexpected error during agent execution for step {self.current_step_index}: {e}")
            await self._mark_step_status(PlanStepStatus.BLOCKED.value, f"Agent execution error: {str(e)}")
            return f"Error during agent execution for step {self.current_step_index}: {str(e)}"

    async def _mark_step_completed(self) -> None:
        """Mark the current step as completed."""
        # Use the new helper function
        await self._mark_step_status(PlanStepStatus.COMPLETED.value)

    async def _get_plan_text(self) -> str:
        """Get the current plan as formatted text."""
        try:
            result = await self.planning_tool.execute(
                command="get", plan_id=self.active_plan_id
            )
            return result.output if hasattr(result, "output") else str(result)
        except Exception as e:
            logger.error(f"Error getting plan: {e}")
            return self._generate_plan_text_from_storage()

    def _generate_plan_text_from_storage(self) -> str:
        """Generate plan text directly from storage if the planning tool fails."""
        try:
            if self.active_plan_id not in self.planning_tool.plans:
                return f"Error: Plan with ID {self.active_plan_id} not found"

            plan_data = self.planning_tool.plans[self.active_plan_id]
            title = plan_data.get("title", "Untitled Plan")
            steps = plan_data.get("steps", [])
            step_statuses = plan_data.get("step_statuses", [])
            step_notes = plan_data.get("step_notes", [])

            # Ensure step_statuses and step_notes match the number of steps
            while len(step_statuses) < len(steps):
                step_statuses.append(PlanStepStatus.NOT_STARTED.value)
            while len(step_notes) < len(steps):
                step_notes.append("")

            # Count steps by status
            status_counts = {status: 0 for status in PlanStepStatus.get_all_statuses()}

            for status in step_statuses:
                if status in status_counts:
                    status_counts[status] += 1

            completed = status_counts[PlanStepStatus.COMPLETED.value]
            total = len(steps)
            progress = (completed / total) * 100 if total > 0 else 0

            plan_text = f"Plan: {title} (ID: {self.active_plan_id})\n"
            plan_text += "=" * len(plan_text) + "\n\n"

            plan_text += (
                f"Progress: {completed}/{total} steps completed ({progress:.1f}%)\n"
            )
            plan_text += f"Status: {status_counts[PlanStepStatus.COMPLETED.value]} completed, {status_counts[PlanStepStatus.IN_PROGRESS.value]} in progress, "
            plan_text += f"{status_counts[PlanStepStatus.BLOCKED.value]} blocked, {status_counts[PlanStepStatus.NOT_STARTED.value]} not started\n\n"
            plan_text += "Steps:\n"

            status_marks = PlanStepStatus.get_status_marks()

            for i, (step, status, notes) in enumerate(
                zip(steps, step_statuses, step_notes)
            ):
                # Use status marks to indicate step status
                status_mark = status_marks.get(
                    status, status_marks[PlanStepStatus.NOT_STARTED.value]
                )

                plan_text += f"{i}. {status_mark} {step}\n"
                if notes:
                    plan_text += f"   Notes: {notes}\n"

            return plan_text
        except Exception as e:
            logger.error(f"Error generating plan text from storage: {e}")
            return f"Error: Unable to retrieve plan with ID {self.active_plan_id}"

    async def _finalize_plan(self) -> str:
        """Finalize the plan and provide a summary using the flow's LLM directly."""
        plan_text = await self._get_plan_text()

        # Create a summary using the flow's LLM directly
        try:
            system_message = Message.system_message(
                "You are a planning assistant. Your task is to summarize the completed plan."
            )

            user_message = Message.user_message(
                f"The plan has been completed. Here is the final plan status:\n\n{plan_text}\n\nPlease provide a summary of what was accomplished and any final thoughts."
            )

            response = await self.llm.ask(
                messages=[user_message], system_msgs=[system_message]
            )

            return f"Plan completed:\n\n{response}"
        except Exception as e:
            logger.error(f"Error finalizing plan with LLM: {e}")

            # Fallback to using an agent for the summary
            try:
                agent = self.primary_agent
                summary_prompt = f"""
                The plan has been completed. Here is the final plan status:

                {plan_text}

                Please provide a summary of what was accomplished and any final thoughts.
                """
                summary = await agent.run(summary_prompt)
                return f"Plan completed:\n\n{summary}"
            except Exception as e2:
                logger.error(f"Error finalizing plan with agent: {e2}")
                return "Plan completed. Error generating summary."

    # Add the helper function to mark step with any status
    async def _mark_step_status(self, status: str, notes: Optional[str] = None) -> None:
        """Mark the current step with a specific status and optional notes."""
        if self.current_step_index is None:
            return
        try:
            await self.planning_tool.execute(
                command="mark_step",
                plan_id=self.active_plan_id,
                step_index=self.current_step_index,
                step_status=status,
                step_notes=notes
            )
            logger.info(f"Marked step {self.current_step_index} as {status} in plan {self.active_plan_id}")
        except Exception as e:
            logger.warning(f"Failed to update plan status to {status}: {e}")
            # Attempt direct update as fallback (consider implications if storage changes)
            if self.active_plan_id in self.planning_tool.plans:
                 plan_data = self.planning_tool.plans[self.active_plan_id]
                 step_statuses = plan_data.get("step_statuses", [])
                 step_notes_list = plan_data.get("step_notes", [])

                 while len(step_statuses) <= self.current_step_index:
                     step_statuses.append(PlanStepStatus.NOT_STARTED.value)
                 while len(step_notes_list) <= self.current_step_index:
                     step_notes_list.append("")

                 step_statuses[self.current_step_index] = status
                 if notes:
                     step_notes_list[self.current_step_index] = notes

                 plan_data["step_statuses"] = step_statuses
                 plan_data["step_notes"] = step_notes_list
