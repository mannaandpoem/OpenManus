import asyncio
import json
import os
import requests
from typing import List
from app.tool.base import BaseTool
from app.config import config


class WebSearch(BaseTool):
    name: str = "web_search"
    description: str = """Perform a web search to retrieve relevant links and content summaries.
                              The search leverages an external search engine to fetch web pages based on a 
                              given query and returns details such as the page's URL, title, a snippet of the 
                              content, a summary of the article, and the website name.

                              This tool is useful for retrieving up-to-date and real-world information,
                              supporting searches on a variety of topics by providing direct links to 
                              the sources."""

    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to submit.",
            },
            "num_results": {
                "type": "integer",
                "description": "Number of search results to return. Default is 10.",
                "default": 10,
            },
        },
        "required": ["query"],
    }

    def bocha_search(self, query: str, num_results: int = None) -> List[dict]:
        """Perform a web search using BochaAI API"""

        # 正确获取 API 配置
        api_url = os.getenv("WEB_SEARCH_API_URL", config.web_search.api_url)
        api_key = os.getenv("WEB_SEARCH_API_KEY", config.web_search.api_key)
        num_results = num_results or int(os.getenv("WEB_SEARCH_NUM_RESULTS", config.web_search.num_results))

        if not api_url or not api_key:
            raise ValueError("Missing web search API URL or API Key. Please check environment variables or config.")

        payload = json.dumps({
            "query": query,
            "summary": True,
            "count": num_results,
            "page": 1
        })

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.post(api_url, headers=headers, data=payload)
            response.raise_for_status()
            response_json = response.json()
            web_pages = response_json.get("data", {}).get("webPages", {}).get("value", [])
            # Format the result to keep only selected fields
            return self.format(web_pages)
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Web search API request failed: {e}")

    def format(self, web_pages):
        formatted_web_pages = []
        for page in web_pages:
            formatted_page = {
                'url': page.get('url'),
                'name': page.get('name'),
                'snippet': page.get('snippet'),
                'summary': page.get('summary'),
                'siteName': page.get('siteName')
            }
            formatted_web_pages.append(formatted_page)
        return formatted_web_pages

    async def execute(self, query: str, num_results: int = 10) -> List[dict]:
        """异步执行搜索"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.bocha_search, query, num_results)


if __name__=="__main__":
    print(config.web_search.open_web_search)
    web_search = WebSearch()
    results = web_search.bocha_search("什么是RAG？", 2)
    print(results)