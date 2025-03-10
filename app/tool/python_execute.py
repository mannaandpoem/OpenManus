import threading
from typing import Dict

from app.tool.base import BaseTool


class PythonExecute(BaseTool):
    """A tool for executing Python code with timeout and safety restrictions."""

    name: str = "python_execute"
    description: str = "Executes Python code string. Note: Only print outputs are visible, function return values are not captured. Use print statements to see results."
    parameters: dict = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code to execute.",
            },
        },
        "required": ["code"],
    }

    async def execute(
        self,
        code: str,
        timeout: int = 5,
    ) -> Dict:
        """
        Executes the provided Python code with a timeout.

        Args:
            code (str): The Python code to execute.
            timeout (int): Execution timeout in seconds.

        Returns:
            Dict: Contains 'output' with execution output or error message and 'success' status.
        """
        result = {"observation": ""}

        def run_code():
            try:
                safe_globals = {"__builtins__": dict(__builtins__)}

                import sys
                from io import StringIO

                output_buffer = StringIO()
                sys.stdout = output_buffer

                exec(code, safe_globals, {})

                sys.stdout = sys.__stdout__
                result["observation"] = output_buffer.getvalue()

            except Exception as e:
                result["observation"] = str(e)
                result["success"] = False

        thread = threading.Thread(target=run_code)
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            return {
                "observation": f"Execution timeout after {timeout} seconds",
                "success": False,
            }

        return result
