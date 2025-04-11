# app/tool/ask_human.py
from typing import Literal

from app.tool.base import BaseTool, ToolResult

# Специальное исключение для сигнализации Flow
class HumanInterventionRequired(Exception):
    """Custom exception to signal that human input is needed."""
    def __init__(self, question: str, tool_call_id: str):
        self.question = question
        self.tool_call_id = tool_call_id # Store the tool_call_id
        super().__init__(question)

class AskHuman(BaseTool):
    """
    A tool that allows the agent to pause execution and ask the human user for input,
    clarification, or a decision when blocked or needing guidance.
    """

    name: str = "ask_human"
    description: str = (
        "Asks the human user for input, clarification, or a decision. "
        "Use this when you are blocked (e.g., after 2-3 failed attempts on a step), need information you cannot find, "
        "or require a decision that only the user can make (e.g., ambiguous instructions, choice between options)."
        "Formulate a clear and specific question for the user."
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "question": {
                "description": "The specific question to ask the human user.",
                "type": "string",
            }
        },
        "required": ["question"],
    }

    # Этот инструмент сам по себе ничего не делает, кроме как сигнализирует.
    # Он выбрасывает исключение, которое должен поймать PlanningFlow.
    async def execute(self, *, question: str, **kwargs) -> ToolResult:
        """
        Signals that human intervention is required by raising a specific exception.
        The PlanningFlow should catch this exception and handle the user interaction.
        """
        # We need the tool_call_id, but it's not directly passed to execute.
        # The agent (ToolCallAgent) needs to catch this exception and add the id.
        # So, we raise it initially without the id.
        # The agent will catch, add the id, and re-raise.
        raise HumanInterventionRequired(question=question, tool_call_id="UNKNOWN") # Raise with a placeholder ID

