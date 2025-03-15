"""Utility class for sandboxing file operations and command executions."""
import os
import shutil
from pathlib import Path
from typing import List, Optional, Union


class SandboxUtils:
    """Utility class for sandbox operations across different tools."""

    def __init__(self):
        """Initialize the SandboxUtils class."""
        self.sandbox_dir = self._create_sandbox_dir()
        self._ensure_sandbox_exists()

    def _create_sandbox_dir(self) -> Path:
        """Create the sandbox directory path."""
        # Using a directory in the project root for the sandbox
        return Path(os.getcwd()) / "sandbox"

    def _ensure_sandbox_exists(self) -> None:
        """Ensure the sandbox directory exists."""
        if not self.sandbox_dir.exists():
            self.sandbox_dir.mkdir(exist_ok=True)

    def clean_sandbox(self) -> None:
        """Clean the sandbox directory before operation."""
        if self.sandbox_dir.exists():
            # Remove all contents but keep the directory
            for item in self.sandbox_dir.glob("*"):
                if item.is_file():
                    item.unlink()
                elif item.is_dir() and item.name != ".git":  # Preserve git directory if exists
                    shutil.rmtree(item)

    def resolve_path(self, path: Union[str, Path], allow_external: bool = False) -> Path:
        """
        Resolve a path to ensure it's within the sandbox directory.
        
        Args:
            path: The original path requested
            allow_external: Whether to allow paths outside the sandbox
            
        Returns:
            Path: The resolved path (either original if allowed or redirected to sandbox)
        """
        # Convert to Path object if it's a string
        if isinstance(path, str):
            path_obj = Path(path)
        else:
            path_obj = path

        # Handle absolute paths
        if path_obj.is_absolute():
            if allow_external:
                return path_obj
            else:
                # Redirect to sandbox, preserving only the filename
                return self.sandbox_dir / path_obj.name
        
        # Handle relative paths
        if allow_external:
            return Path(os.getcwd()) / path_obj
        else:
            # Check for parent directory traversal
            if ".." in str(path_obj):
                # Replace with just the filename to keep in the sandbox
                path_parts = [part for part in path_obj.parts if part != ".."]
                if not path_parts:
                    return self.sandbox_dir
                return self.sandbox_dir / Path(*path_parts)
            else:
                return self.sandbox_dir / path_obj

    def is_potentially_harmful_command(self, command: str) -> bool:
        """
        Check if a command is potentially harmful.
        
        Args:
            command: The command to check
            
        Returns:
            bool: True if the command is potentially harmful
        """
        dangerous_patterns = [
            "rm -rf", "rm -r", "rmdir", 
            "mkfs", "dd if=", 
            "chmod 777", "chmod -R",
            "> /dev", "| dd of=",
            "wget", "curl",  # Download commands should be authorized
            ":(){:|:&};:",  # Fork bomb
            "sudo", "su ",  # Privilege escalation
            "mv /", "cp /", # Moving or copying from root
            "scp ", "rsync",  # File transfer commands
            "/etc/passwd", "/etc/shadow",  # Sensitive system files
            "> /etc/", ">> /etc/",  # Writing to system directories
            "shutdown", "reboot",  # System control
        ]
        
        for pattern in dangerous_patterns:
            if pattern in command:
                return True
                
        return False

    def sanitize_command(self, command: str, allow_external: bool = False) -> str:
        """
        Sanitize a command to run in the sandbox directory.
        
        Args:
            command: The command to sanitize
            allow_external: Whether to allow commands outside the sandbox
            
        Returns:
            str: The sanitized command
        """
        if not allow_external:
            # Prefix the command to change to the sandbox directory first
            return f"cd {self.sandbox_dir} && {command}"
        return command 