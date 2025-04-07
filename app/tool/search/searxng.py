import requests
from app.tool.search.base import WebSearchEngine
from app.config import config


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
        
        try:
            response = requests.get(
                config.search_config.searxng_url,
                headers={
                    "User-Agent": "Open Manus (https://github.com/mannaandpoem/OpenManus)",
                    "Accept": "text/html",
                    "Accept-Encoding": "gzip, deflate",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Connection": "keep-alive",
                },
                params=params,
                timeout=10  # Added timeout
            )
            response.raise_for_status()  # Raises HTTPError for 4XX/5XX responses
            
            try:
                json_response = response.json()
                results = json_response.get("results", [])
                return results
            except ValueError as e:
                raise ValueError(f"Failed to parse JSON response: {str(e)}")
                
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Search request failed: {str(e)}")


if __name__ == "__main__":
    # 测试搜索功能
    search_engine = SearxngSearchEngine()
    try:
        results = search_engine.perform_search("Python", num_results=5)
        print(f"搜索成功，获取到 {len(results)} 条结果:")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result.get('title', '无标题')}")
            print(f"   URL: {result.get('url', '无URL')}")
            print(f"   {result.get('content', '无内容摘要')[:100]}...")
    except Exception as e:
        print(f"搜索出错: {str(e)}")