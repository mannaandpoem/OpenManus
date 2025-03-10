import os
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp
from pydantic import Field

# Import BaseTool and ToolResult from the project's base tool module.
from app.tool.base import BaseTool, ToolResult

class DownloadFile(BaseTool):
    name: str = "download_file"
    description: str = (
        "Download a file from a given URL. Supports PDF and other file types. "
        "Downloads the file from the provided URL and saves it locally. "
        "If filename is not provided, the file name is derived from the URL."
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL of the file to download.",
            },
            "filename": {
                "type": "string",
                "description": "Optional: The filename to save the file as. "
                               "If not provided, the filename will be extracted from the URL.",
            },
        },
        "required": ["url"],
    }
    
    async def execute(self, **kwargs) -> ToolResult:
        url: Optional[str] = kwargs.get("url")
        if not url:
            return ToolResult(error="URL is required.")
        
        filename: Optional[str] = kwargs.get("filename")
        if not filename:
            # Try to extract the filename from the URL
            filename = os.path.basename(url)
            if not filename:
                filename = "downloaded_file"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return ToolResult(
                            error=f"Failed to download file. HTTP status code: {response.status}"
                        )
                    
                    # Read the content of the file
                    file_data = await response.read()
                    
                    # Optionally, you could inspect the 'Content-Type' header:
                    content_type = response.headers.get("Content-Type", "")
                    # For example, if you only want to allow PDF files, you could check:
                    # if "pdf" not in content_type.lower():
                    #     return ToolResult(error="The file is not a PDF.")
                    
                    # Save the file to the current directory
                    save_path = Path(filename)
                    with save_path.open("wb") as f:
                        f.write(file_data)
                    
                    return ToolResult(
                        output=f"File downloaded successfully and saved to {save_path.resolve()}."
                    )
        except Exception as e:
            return ToolResult(error=f"Error downloading file: {str(e)}")
