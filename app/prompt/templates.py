"""
Prompt templates for different types of interactions.
These templates are used to wrap user prompts based on the context
of the interaction (standard websocket, file upload, etc.)
"""

from typing import List, Optional


def standard_prompt_template(prompt: str) -> str:
    """
    Template for standard prompts received via WebSocket.
    
    Args:
        prompt: The user's original prompt
        
    Returns:
        The wrapped prompt
    """
    return f"""

Help me with the following request:
{prompt}
Also make sure to store all the files in the ./tmp folder
"""


def file_upload_prompt_template(prompt: str, uploaded_files: List[str]) -> str:
    """
    Template for prompts accompanying file uploads.
    
    Args:
        prompt: The user's original prompt
        uploaded_files: List of uploaded file paths
        
    Returns:
        The wrapped prompt that includes file information
    """
    file_list = "\n".join([f"- {file}" for file in uploaded_files])
    
    return f"""
Help me with the following request which involves processing the following files:

{prompt}

The following files have been uploaded and are available for processing:
{file_list}

Any results should be stored in the ./tmp folder
""" 