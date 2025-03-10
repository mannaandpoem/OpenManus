import asyncio
import aiohttp
from urllib.parse import quote
from typing import List
import json
import logging
from app.tool.search.base_search import BaseSearch

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class SearxNGSearch(BaseSearch):
    """SearxNG search engine implementation"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8080"):
        self.base_url = base_url.rstrip('/')
        
    async def search(self, query: str, num_results: int = 10) -> List[str]:
        """
        Perform search via SearxNG API and return list of URLs
        
        Args:
            query (str): Search query
            num_results (int): Number of results to return
            
        Returns:
            List[str]: List of search result URLs
        """
        encoded_query = quote(query)
        url = f"{self.base_url}/search?q={encoded_query}&format=json"
        logger.debug(f"Request URL: {url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    # logger.debug(f"Received raw data: {json.dumps(data, ensure_ascii=False, indent=2)}")
                    
                    results = [
                        result['url']
                        for result in data.get('results', [])[:num_results]
                        if 'url' in result
                    ]
                    logger.debug(f"Processed URL list: {results}")
                    return results
                else:
                    logger.error(f"Request failed with status code: {response.status}")
                    raise Exception(f"Search request failed: {response.status}")