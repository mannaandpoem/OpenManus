from typing import List, Dict, Any
import tomli
from pathlib import Path
from pydantic import Field

from app.tool.base import BaseTool
from app.tool.search.search_factory import SearchFactory
from app.tool.search.searxng_search import SearxNGSearch

class SearchTool(BaseTool):
    name: str = "search"
    description: str = """Get information by performing web searches and return a list of relevant links.
"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string", 
                "description": "(required) The search query content",
            },
            "num_results": {
                "type": "integer",
                "description": "(optional) Number of results to return, defaults to 10",
                "default": 10,
            },
        },
        "required": ["query"],
    }

    config: Dict[str, Any] = Field(default_factory=dict)
    search_engine: Any = Field(default=None)

    def __init__(self):
        super().__init__()
        self.config = self._load_config()
        search_config = self.config.get("search_engine", {})
        self.search_engine = SearchFactory.create_search_engine(
            search_config.get("type", "google")
        )
        if isinstance(self.search_engine, SearxNGSearch):
            self.search_engine.base_url = search_config.get("base_url", "http://127.0.0.1:8080")

    def _load_config(self) -> dict:
        config_path = Path("config/config.toml")
        if not config_path.exists():
            return {"search_engine": {"type": "google"}}
        
        with open(config_path, "rb") as f:
            return tomli.load(f)

    async def execute(self, query: str, num_results: int = 10) -> List[str]:
        """
        Execute search and return results
        
        Args:
            query (str): Search query
            num_results (int): Number of results to return
            
        Returns:
            List[str]: List of search result URLs
        """
        return await self.search_engine.search(query, num_results) 