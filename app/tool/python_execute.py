import multiprocessing
import os
import sys
from io import StringIO
from typing import Dict, Optional
import re

from pydantic import Field

from app.tool.base import BaseTool
from app.tool.sandbox_utils import SandboxUtils


class PythonExecute(BaseTool):
    """A tool for executing Python code in a sandboxed environment with enhanced security."""

    name: str = "python_execute"
    description: str = (
        "Executes Python code string in a sandboxed environment. "
        "Note: Only print outputs are visible, function return values are not captured. "
        "Use print statements to see results."
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code to execute.",
            },
            "allow_external_access": {
                "type": "boolean",
                "description": "Whether to allow access to resources outside the sandbox directory. "
                "This requires explicit user permission.",
                "default": False,
            },
        },
        "required": ["code"],
    }

    # Add sandbox as a proper field
    sandbox: SandboxUtils = Field(default_factory=SandboxUtils)
    allow_external_access: bool = Field(default=False)

    def _is_potentially_harmful(self, code: str) -> bool:
        """Check if the code contains potentially harmful operations."""
        dangerous_patterns = [
            "os.remove", "os.unlink", "shutil.rmtree", 
            "os.rmdir", "shutil.move", "os.rename",
            "import subprocess", "subprocess.run", "subprocess.Popen",
            "exec(", "eval(", "__import__",
            # Add more patterns as needed
        ]
        
        # Check for access to parent directories
        if ".." in code or "../" in code:
            return True
            
        # Check for dangerous operations
        for pattern in dangerous_patterns:
            if pattern in code:
                return True
        
        # If external access is not allowed, check file operations
        if not self.allow_external_access:
            # Look for file operations
            file_ops = re.finditer(r'(?:open|with\s+open)\s*\(\s*[\'"]([^\'"]+)[\'"]', code)
            for match in file_ops:
                file_path = match.group(1)
                # If the path is absolute or tries to access parent directory, it's harmful
                if os.path.isabs(file_path) or '..' in file_path:
                    return True
                # Otherwise, it's safe as it will be relative to the sandbox directory
                
        return False

    def _run_code_sandboxed(self, code: str, result_dict: dict, sandbox_dir: str) -> None:
        """Run code in a sandboxed environment."""
        # Import required modules in the child process
        import os
        import sys
        from io import StringIO
        
        original_stdout = sys.stdout
        original_cwd = os.getcwd()
        
        try:
            # Change to sandbox directory
            os.chdir(sandbox_dir)
            
            # Redirect stdout
            output_buffer = StringIO()
            sys.stdout = output_buffer
            
            # Create safe globals
            safe_globals = {
                'print': print,
                '__builtins__': __builtins__,
                'os': os,
                'sys': sys,
                '__file__': os.path.join(sandbox_dir, "sandbox_script.py"),
                '__name__': "__sandbox__",
            }
            
            # Execute the code
            exec(code, safe_globals, safe_globals)
            
            result_dict["observation"] = output_buffer.getvalue()
            result_dict["success"] = True
            
        except Exception as e:
            result_dict["observation"] = str(e)
            result_dict["success"] = False
            
        finally:
            # Restore original environment
            sys.stdout = original_stdout
            os.chdir(original_cwd)

    async def execute(
        self,
        code: str,
        timeout: int = 5,
        allow_external_access: bool = False,
    ) -> Dict:
        """
        Execute Python code in a sandboxed environment.

        Args:
            code (str): The Python code to execute.
            timeout (int, optional): Maximum execution time in seconds. Defaults to 5.
            allow_external_access (bool, optional): Whether to allow access outside sandbox. Defaults to False.

        Returns:
            Dict: Contains 'observation' with output or error and 'success' status.
        """
        # Update allow_external_access field
        self.allow_external_access = allow_external_access
        
        # First, ensure the sandbox exists
        self.sandbox._ensure_sandbox_exists()

        # Check if code is potentially harmful
        if self._is_potentially_harmful(code) and not allow_external_access:
            return {
                "observation": (
                    "⚠️ This code contains potentially harmful operations that require explicit permission. "
                    "Please use allow_external_access=True if you need to perform these operations and "
                    "acknowledge the security implications."
                ),
                "success": False
            }

        # Create a dictionary to store results that can be shared between processes
        manager = multiprocessing.Manager()
        result_dict = manager.dict()
        result_dict["observation"] = ""
        result_dict["success"] = False

        try:
            # Run the code in a separate process with a timeout
            process = multiprocessing.Process(
                target=self._run_code_sandboxed,
                args=(code, result_dict, str(self.sandbox.sandbox_dir))
            )
            process.start()
            process.join(timeout=timeout)

            if process.is_alive():
                process.terminate()
                process.join()
                return {
                    "observation": f"Execution timed out after {timeout} seconds",
                    "success": False
                }

            # Add notice about sandbox execution
            if result_dict["success"]:
                if allow_external_access:
                    prefix = "📁 Code executed with external access enabled\n\n"
                else:
                    prefix = f"📁 Code executed in sandbox directory: {self.sandbox.sandbox_dir}\n\n"
                result_dict["observation"] = prefix + result_dict["observation"]

            return dict(result_dict)

        except Exception as e:
            return {
                "observation": f"Error during execution: {str(e)}",
                "success": False
            } 