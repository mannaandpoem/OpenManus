import asyncio
from typing import List
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup
from app.tool.base import BaseTool

class BingSearch(BaseTool):
    name: str = "bing_search"
    description: str = """执行必应搜索并返回相关链接列表。
当需要获取国际信息或英文内容时建议使用此工具。
工具返回与搜索查询匹配的URL列表。"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "(必填) 提交给必应的搜索关键词"
            },
            "num_results": {
                "type": "integer",
                "description": "(可选) 返回的搜索结果数量，默认10",
                "default": 10
            }
        },
        "required": ["query"]
    }

    async def execute(self, query: str, num_results: int = 10) -> List[str]:
        """
        执行必应搜索并返回URL列表

        Args:
            query: 搜索关键词
            num_results: 返回结果数量

        Returns:
            匹配搜索结果的URL列表
        """

        def sync_search():
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept-Language': 'en-US,en;q=0.9'
            }
            url = f'https://www.cn.bing.com/search?q={quote(query)}'
            links = []

            for page in range(0, num_results // 10 + 1):
                resp = requests.get(
                    f'{url}&first={page * 10}',
                    headers=headers,
                    timeout=10
                )
                soup = BeautifulSoup(resp.text, 'html.parser')

                for result in soup.select('.b_algo'):
                    link = result.find('a', href=True)
                    if link and 'href' in link.attrs:
                        links.append(link['href'])
                        if len(links) >= num_results:
                            return links
            rst = links[:num_results]
            return rst

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_search)