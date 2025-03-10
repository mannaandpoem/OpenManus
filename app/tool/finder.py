import os
from typing import List, Dict
import glob
from pathlib import Path

from app.tool.base import BaseTool


class Finder(BaseTool):
    # use project root as default path
    _default_path = str(Path(__file__).parent.parent.parent)
    
    name: str = "finder"
    description: str = """Search for a file in a specified local directory by its name or partial name.
The tool searches for files whose names contain specific keywords and returns the matching files' paths.
"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "directory_path": {
                "type": "string",
                "description": f"(optional) The path of the directory to search files in. Defaults to '{_default_path}'.",
                "default": _default_path,
            },
            "file_name_keywords": {
                "type": "array",
                "description": "(required) A list of keywords to search for in the file names.",
                "items": {"type": "string"},
            },
            "file_extensions": {
                "type": "array",
                "description": "(optional) A list of file extensions to filter by. If not provided, all files will be searched.",
                "items": {"type": "string"},
                "default": [],
            },
        },
        "required": ["file_name_keywords"],
    }

    async def execute(
        self, directory_path: str = None, file_name_keywords: List[str] = [], file_extensions: List[str] = []
    ) -> Dict[str, str]:
        """
        Search for files in the specified directory whose name contains specific keywords.

        Args:
            directory_path (str): The path of the directory to search files in. Defaults to parent of parent directory.
            file_name_keywords (List[str]): A list of keywords to search for in the file names.
            file_extensions (List[str], optional): A list of file extensions to filter by. Default is all files.

        Returns:
            Dict[str, list]: A dictionary with list of found files,
                           or an error message.
        """
        try:
            # Use the class default path if directory_path is None
            if directory_path is None:
                directory_path = self._default_path
                
            print(f"Searching in directory: {directory_path}")
            # Ensure the directory exists
            if not os.path.exists(directory_path):
                return {"error": f"Directory '{directory_path}' does not exist."}

            # Prepare file extension pattern
            ext_pattern = ""
            if file_extensions:
                # Convert extensions to proper format (ensuring they start with a dot)
                formatted_exts = [ext if ext.startswith('.') else f'.{ext}' for ext in file_extensions]
                # Join extensions with comma for glob pattern
                ext_pattern = f"*{{{''.join(formatted_exts)}}}"
            else:
                ext_pattern = "*"  # Match all files
                
            # Get absolute path
            abs_directory_path = Path(directory_path).resolve()
            
            # Convert keywords to lowercase for case-insensitive matching
            lowercase_keywords = [keyword.lower() for keyword in file_name_keywords]
            
            # List to store matching files
            matching_files = []
            
            # Use glob to recursively find all files
            for file_path in glob.glob(f"{abs_directory_path}/**/{ext_pattern}", recursive=True):
                file_name = Path(file_path).name
                lowercase_filename = file_name.lower()
                
                # Check if file name contains any of the keywords (case-insensitive)
                if any(keyword in lowercase_filename for keyword in lowercase_keywords):
                    # Get file size
                    file_size_bytes = os.path.getsize(file_path)
                    file_size = self._format_file_size(file_size_bytes)
                    
                    # Add file information to the list
                    matching_files.append({
                        "file_name": file_name,
                        "file_path": str(file_path),
                        "file_size": file_size
                    })
            
            if matching_files:
                return {"files_found": matching_files}
            else:
                return {"message": "No matching files found."}
                
        except Exception as e:
            return {"error": f"Error searching files: {str(e)}"}
            
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in a human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0 or unit == 'TB':
                break
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} {unit}"