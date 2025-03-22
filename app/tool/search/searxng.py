import requests
from app.tool.search.base import WebSearchEngine
URL='you searxng address'


class SearxngSearchEngine(WebSearchEngine):

    def perform_search(self,query: str,num_results: int = 10,*args, **kwargs):
        """Searxng search engine."""
        language = kwargs.get("language", "en-US")
        safesearch = kwargs.get("safesearch", "1")
        time_range = kwargs.get("time_range", "")
        categories = "".join(kwargs.get("categories", []))
        params = {
            "q": query,
            "format": "json",
            "pageno": 1,
            "safesearch": safesearch,
            "language": language,
            "time_range": time_range,
            "categories": categories,
            "theme": "simple",
            "image_proxy": 0,
        }
        response = requests.get(
            URL,
            headers={
                "User-Agent": "Open Manus (https://github.com/mannaandpoem/OpenManus)",
                "Accept": "text/html",
                "Accept-Encoding": "gzip, deflate",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Connection": "keep-alive",
            },
            params=params,
        )

        json_response = response.json()
        results = json_response.get("results", [])
        return results