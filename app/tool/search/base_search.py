from abc import ABC, abstractmethod
from typing import List

class BaseSearch(ABC):
    """Abstract base class for search engines"""
    
    @abstractmethod
    async def search(self, query: str, num_results: int = 10) -> List[str]:
        """
        Perform search and return list of result URLs
        
        Args:
            query (str): Search query
            num_results (int): Number of results to return
            
        Returns:
            List[str]: List of search result URLs
        """
        pass 