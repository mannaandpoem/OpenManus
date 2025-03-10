from typing import Dict, Type
from app.tool.search.base_search import BaseSearch
from app.tool.search.google_search import GoogleSearch
from app.tool.search.searxng_search import SearxNGSearch

class SearchFactory:
    """Search Engine Factory Class"""
    
    _engines: Dict[str, Type[BaseSearch]] = {
        "google": GoogleSearch,
        "searxng": SearxNGSearch
    }
    
    @classmethod
    def create_search_engine(cls, engine_type: str) -> BaseSearch:
        """
        Create search engine instance
        
        Args:
            engine_type (str): Search engine type
            
        Returns:
            BaseSearch: Search engine instance
        """
        if engine_type not in cls._engines:
            raise ValueError(f"Unsupported search engine type: {engine_type}")
            
        engine_class = cls._engines[engine_type]
        if engine_type == "searxng":
            return engine_class()  # 可以从配置中读取base_url
        return engine_class() 