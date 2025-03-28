from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine
from ..base import BaseTool

class DataLoader(BaseTool):
    """智能数据加载器｜支持文件/数据库/API"""

    name: str = "etl_loader"
    description: str = "从多种数据源加载结构化数据"  # 必须补充该字段
    parameters: dict = {
        "type": "object",
        "properties": {
            "source_type": {
                "type": "string",
                "enum": ["file", "database", "api"],
                "description": "数据源类型",
                "default": "file"
            },
            "path": {
                "type": "string",
                "description": "数据文件路径"
            }
        },
        "required": ["source_type", "path"]  # 补充必须参数
    }

    async def execute(self, config: dict) -> pd.DataFrame:
        if config["source_type"] == "file":
            return self._load_file(config["path"])
        elif config["source_type"] == "database":
            return self._load_database(config["db_config"])
        elif config["source_type"] == "api":
            return await self._load_api(config["api_config"])  # 新增异步API加载

    async def _load_api(self, config: dict) -> pd.DataFrame:
        """带限流和重试的API加载"""
        async with aiohttp.ClientSession() as session:
            async with session.get(config["url"], params=config.get("params")) as resp:
                if resp.status == 200:
                    return pd.DataFrame(await resp.json())
                raise ValueError(f"API请求失败: {resp.status}")

    # 建议增加分块加载和内存优化
    async def _load_file(self, path: str) -> pd.DataFrame:
        file_path = Path(path)
        suffix = file_path.suffix.lower()

        # 增加分块加载支持
        if suffix == ".csv" and os.path.getsize(path) > 100_000_000:  # >100MB文件
            return pd.read_csv(path, chunksize=10_000)

        loaders = {
            ".csv": lambda: pd.read_csv(path, low_memory=False),  # 优化内存使用
            ".xlsx": lambda: pd.read_excel(path),
            ".parquet": lambda: pd.read_parquet(path),
            ".json": lambda: pd.read_json(path, lines=True)  # 支持JSON行格式
        }

        if suffix in loaders:
            return loaders[suffix]()
        raise ValueError(f"不支持的文件格式: {suffix}")

    def _load_database(self, config: dict) -> pd.DataFrame:
        engine = create_engine(config["conn_str"])
        if "query" in config:
            return pd.read_sql(config["query"], engine)
        return pd.read_sql_table(config["table_name"], engine)