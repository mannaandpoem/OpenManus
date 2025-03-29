from app.tool.base import BaseTool


_TERMINATE_DESCRIPTION = """Terminate the interaction when the request is met.
When you have finished all the tasks, call this tool to end the work."""


class ValiTerminate(BaseTool):
    name: str = "valiterminate"
    description: str = _TERMINATE_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "The finish status of the interaction.",
                "enum": ["success"],
            }
        },
        "required": ["status"],
    }

    async def execute(self, status: str) -> str:
        """Finish the current execution"""
        return f"The interaction has been completed with status: {status}"
