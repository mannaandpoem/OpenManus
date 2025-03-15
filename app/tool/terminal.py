import asyncio
import os
import shlex
import subprocess
from typing import Dict, Optional, Union

from pydantic import Field

from app.tool.base import BaseTool, CLIResult
from app.tool.sandbox_utils import SandboxUtils


class Terminal(BaseTool):
    """A tool for executing commands in a sandboxed environment with enhanced security."""

    name: str = "execute_command"
    description: str = """Request to execute a CLI command in the sandbox directory.
Use this when you need to perform system operations or run specific commands to accomplish any step in the user's task.
By default, all commands run in the sandbox directory for security.
To run commands with access to the entire filesystem, you must specify allow_external_access=True.
Note: You MUST append a `sleep 0.05` to the end of the command for commands that will complete in under 50ms, as this will circumvent a known issue with the terminal tool where it will sometimes not return the output when the command completes too quickly.
"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "(required) The CLI command to execute. This should be valid for the current operating system. Ensure the command is properly formatted and does not contain any harmful instructions.",
            },
            "allow_external_access": {
                "type": "boolean",
                "description": "Whether to allow the command to access resources outside the sandbox directory. "
                "This requires explicit user permission.",
                "default": False,
            },
            "cwd": {
                "type": "string",
                "description": "(optional) The working directory for command execution. "
                "Defaults to sandbox directory.",
            },
        },
        "required": ["command"],
    }

    # Add sandbox and current_path as proper fields
    sandbox: SandboxUtils = Field(default_factory=SandboxUtils)
    current_path: str = Field(default="")

    def __init__(self):
        super().__init__()
        # Set current_path to sandbox directory
        self.current_path = str(self.sandbox.sandbox_dir)

    async def execute(
        self, 
        command: str, 
        allow_external_access: bool = False, 
        cwd: Optional[str] = None
    ) -> CLIResult:
        """
        Execute a terminal command in the sandbox directory unless explicitly allowed elsewhere.

        Args:
            command (str): The command to execute.
            allow_external_access (bool): Whether to allow execution outside the sandbox.
            cwd (str, optional): The working directory for command execution.

        Returns:
            CLIResult: The output, error, and status of the command execution.
        """
        try:
            # First, ensure the sandbox exists
            self.sandbox._ensure_sandbox_exists()
            
            # If no cwd specified, use sandbox directory
            if not cwd:
                cwd = str(self.sandbox.sandbox_dir)
            else:
                # Resolve the cwd path to ensure it's within sandbox (unless explicitly allowed)
                cwd = str(self.sandbox.resolve_path(cwd, allow_external_access))

            # Check if this is a potentially harmful command
            if self.sandbox.is_potentially_harmful_command(command) and not allow_external_access:
                return CLIResult(
                    output="",
                    error=(
                        f"⚠️ The command '{command}' appears to be potentially harmful. "
                        f"To execute this command, use allow_external_access=True "
                        f"and acknowledge the security implications."
                    ),
                    exit_code=1
                )

            # Execute the command
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                text=True
            )
            stdout, stderr = process.communicate()

            # Add notice about sandbox execution
            if process.returncode == 0:
                if allow_external_access:
                    prefix = "📁 Command executed with external access enabled\n\n"
                else:
                    prefix = f"📁 Command executed in sandbox directory: {self.sandbox.sandbox_dir}\n\n"
                stdout = prefix + stdout

            return CLIResult(
                output=stdout,
                error=stderr,
                exit_code=process.returncode
            )

        except Exception as e:
            return CLIResult(
                output="",
                error=f"Error executing command: {str(e)}",
                exit_code=1
            )

    async def _handle_cd_command(self, command: str) -> CLIResult:
        # Implementation of _handle_cd_command method
        pass

    async def _sanitize_command(self, command: str) -> str:
        # Implementation of _sanitize_command method
        pass

    async def _execute_command(self, command: str) -> CLIResult:
        # Implementation of _execute_command method
        pass 