from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine
from ..base import BaseTool

class DataSaver(BaseTool):
    """智能数据存储器｜多格式输出支持"""

    name: str = "etl_saver"
    description: str = "将处理后的数据保存至本地文件或数据库"
    parameters: dict = {
        "type": "object",
        "properties": {
            "output_format": {
                "type": "string",
                "enum": ["csv", "parquet", "database"],
                "description": "输出格式选择（csv/parquet/数据库）",
                "default": "csv"
            },
            "compression": {
                "type": "string",
                "enum": ["none", "gzip", "snappy"],
                "description": "文件压缩格式（仅parquet有效）",
                "default": "none"
            }
        },
        "required": []
    }

    async def execute(self, df: pd.DataFrame, config: dict) -> str:
        output_format = config.get("output_format", "csv")

        if output_format == "csv":
            return self._save_csv(df)
        elif output_format == "parquet":
            return self._save_parquet(df)
        elif output_format == "database":
            return self._save_database(df, config["db_config"])
        raise ValueError("不支持的输出格式")

    def _save_csv(self, df: pd.DataFrame) -> str:
        output_dir = Path("workspace/cleaned_data")
        output_dir.mkdir(exist_ok=True)
        path = output_dir / f"cleaned_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}.csv"
        df.to_csv(path, index=False)
        return str(path)

    def _save_parquet(self, df: pd.DataFrame) -> str:
        output_dir = Path("workspace/cleaned_data")
        output_dir.mkdir(exist_ok=True)
        path = output_dir / f"cleaned_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}.parquet"
        df.to_parquet(path)
        return str(path)

    async def _save_database(self, df: pd.DataFrame, config: dict) -> str:
        async with self.engine.begin() as conn:  # 添加事务支持
            await conn.run_sync(lambda sync_conn:
                df.to_sql(config["table_name"], engine, if_exists="append", index=False)
            )
        return f"{config['table_name']} in database"