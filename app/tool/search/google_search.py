import asyncio
from googlesearch import search
from app.tool.search.base_search import BaseSearch

class GoogleSearch(BaseSearch):
    """Google search implementation"""
    
    async def search(self, query: str, num_results: int = 10) -> list[str]:
        loop = asyncio.get_event_loop()
        links = await loop.run_in_executor(
            None, lambda: list(search(query, num_results=num_results))
        )
        return links 