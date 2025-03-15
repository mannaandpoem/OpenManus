import os
from pathlib import Path
from typing import Dict, Optional

import aiofiles
from pydantic import Field

from app.tool.base import BaseTool
from app.tool.sandbox_utils import SandboxUtils


class FileSaver(BaseTool):
    """A tool for saving files in a sandboxed environment with enhanced security."""

    name: str = "file_saver"
    description: str = """Save content to a local file in the sandbox directory.
Use this tool when you need to save text, code, or generated content to a file.
By default, all files are saved to the sandbox directory for security.
To save files outside the sandbox, you must specify allow_external_access=True.
"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "(required) The content to save to the file.",
            },
            "file_path": {
                "type": "string",
                "description": "(required) The path where the file should be saved, relative to the sandbox directory.",
            },
            "mode": {
                "type": "string",
                "description": "(optional) The file opening mode. Default is 'w' for write. Use 'a' for append.",
                "enum": ["w", "a"],
                "default": "w",
            },
            "allow_external_access": {
                "type": "boolean",
                "description": "Whether to allow saving to locations outside the sandbox directory. "
                "This requires explicit user permission.",
                "default": False,
            },
        },
        "required": ["content", "file_path"],
    }

    # Add sandbox as a proper field
    sandbox: SandboxUtils = Field(default_factory=SandboxUtils)

    async def execute(
        self, 
        content: str, 
        file_path: str, 
        mode: str = "w", 
        allow_external_access: bool = False
    ) -> Dict:
        """
        Save content to a file in the sandbox directory unless explicitly allowed to save elsewhere.

        Args:
            content (str): The content to save to the file.
            file_path (str): The path where the file should be saved.
            mode (str, optional): The file opening mode. Default is 'w' for write. Use 'a' for append.
            allow_external_access (bool): Whether to allow saving outside the sandbox.

        Returns:
            Dict: Contains 'observation' with success message or error and 'success' status.
        """
        try:
            # First, ensure the sandbox exists
            self.sandbox._ensure_sandbox_exists()
            
            # Convert input path to Path object
            input_path = Path(file_path)
            
            # If the path is absolute and we don't have external access, reject it
            if input_path.is_absolute() and not allow_external_access:
                return {
                    "observation": (
                        f"⚠️ Cannot write to absolute path '{file_path}' without explicit permission. "
                        f"Use allow_external_access=True to write to absolute paths."
                    ),
                    "success": False,
                }
            
            # Resolve the path to ensure it's within the sandbox (unless explicitly allowed)
            resolved_path = self.sandbox.resolve_path(file_path, allow_external_access)
            
            # Check if this is a potentially suspicious path (trying to escape sandbox)
            if not allow_external_access and not str(resolved_path).startswith(str(self.sandbox.sandbox_dir)):
                return {
                    "observation": (
                        f"⚠️ The requested file path '{file_path}' would write outside the sandbox. "
                        f"To write outside the sandbox, use allow_external_access=True "
                        f"and acknowledge the security implications."
                    ),
                    "success": False,
                }

            # Ensure the directory exists
            directory = os.path.dirname(str(resolved_path))
            if directory:
                os.makedirs(directory, exist_ok=True)

            # Write directly to the file
            async with aiofiles.open(str(resolved_path), mode, encoding="utf-8") as file:
                await file.write(content)

            if allow_external_access:
                return {
                    "observation": f"Content successfully saved to {resolved_path} (with external access)",
                    "success": True
                }
            else:
                return {
                    "observation": f"Content successfully saved to {resolved_path} (in sandbox)",
                    "success": True
                }
        except Exception as e:
            return {
                "observation": f"Error saving file: {str(e)}",
                "success": False
            } 