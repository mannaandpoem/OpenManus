from typing import Dict

from pydantic import Field

from app.tool.base import BaseTool


class AskUser(BaseTool):
    """A tool for asking the user for input or confirmation during an interaction."""

    name: str = "ask_user"
    description: str = """
    Use this tool to request input from the user during an interaction.
    This should be used in THREE common scenarios:
    
    1. CONFIRMATION: When asking the user to confirm potentially harmful operations like:
       - Deleting or modifying important files
       - Executing system commands that might affect the user's environment
       - Performing any action that has security implications
       - Making any irreversible changes
    
    2. CLARIFICATION: When you need clarification about the user's intent or more details about the request.
       
    3. FOLLOW-UP: When you're presenting options and waiting for the user to choose one or when you need
       additional input to proceed with the task.
    
    IMPORTANT: You should ALWAYS use this tool when you need a response from the user, rather than just
    adding questions in your thoughts. Without using this tool, the user cannot respond to your questions.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "(required) The question to ask the user. Be clear about what you're asking.",
            },
            "dangerous_action": {
                "type": "boolean",
                "description": "Whether this is a particularly dangerous action that requires extra caution.",
                "default": False,
            },
            "question_type": {
                "type": "string",
                "description": "The type of question being asked (confirmation, clarification, or follow-up).",
                "default": "confirmation",
                "enum": ["confirmation", "clarification", "follow-up"],
            },
        },
        "required": ["question"],
    }

    async def execute(
        self, 
        question: str, 
        dangerous_action: bool = False, 
        question_type: str = "confirmation"
    ) -> Dict:
        """
        Ask the user for input during an interaction.

        Args:
            question (str): The question to ask the user.
            dangerous_action (bool): Whether this is a particularly dangerous action.
            question_type (str): The type of question being asked.

        Returns:
            Dict: Contains the user's response.
        """
        # Set prefix based on question type and danger level
        if dangerous_action:
            prefix = "⚠️ CAUTION: "
        elif question_type == "confirmation":
            prefix = "🔹 CONFIRMATION: "
        elif question_type == "clarification":
            prefix = "❓ CLARIFICATION: "
        else:  # follow-up
            prefix = "📝 FOLLOW-UP: "
        
        # Return the formatted question to be shown to the user
        return {
            "observation": f"{prefix}{question}\n\nPlease reply directly to this message with your response:",
            "success": True,
            "requires_user_response": True
        } 