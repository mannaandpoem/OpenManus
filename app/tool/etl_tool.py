import pandas as pd

from tenacity import retry, stop_after_attempt, wait_exponential
from . import BaseTool
from .etl.loader import DataLoader
from .etl.cleaner import DataCleaner
from .etl.analyzer import DataAnalyzer
from .etl.saver import DataSaver
from ..logger import logger
from pathlib import Path


# 在顶部导入新增工具
from .etl.validator import DataValidator
from .etl.metadata import MetadataRecorder
from .etl.reporter import ReportGenerator

class ETLTool(BaseTool):
    """数据ETL与探索分析工具｜集成数据加载、清洗、分析、存储全流程"""

    name: str = "etl_tool"
    description: str = "执行数据探索、清洗和转换的ETL工具"
    parameters: dict = {
        "type": "object",
        "properties": {
            "data_path": {
                "type": "string",
                "description": "数据文件路径（支持csv/xlsx/parquet）"
            },
            "clean_config": {
                "type": "object",
                "properties": {
                    "handle_missing": {
                        "type": "string",
                        "enum": ["drop", "fill"],
                        "default": "drop",
                        "description": "缺失值处理策略：drop-删除缺失值 fill-填充缺失值"
                    },
                    "outlier_method": {
                        "type": "string",
                        "enum": ["zscore", "iqr"],
                        "default": "iqr",
                        "description": "异常值检测方法：zscore-Z分数法 iqr-四分位距法"
                    }
                }
            },
            "explore_depth": {
                "type": "integer",
                "description": "数据探索深度级别（1-基础分析 2-高级分析 3-预测分析）",
                "default": 2,
                "minimum": 1,
                "maximum": 3
            }
        },
        "required": ["data_path"]
    }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before=lambda _: logger.info("ETL流程重试中...")
    )
    # 增加流程监控和断点续传
    async def execute(self, data_path: str, clean_config: dict = None, explore_depth: int = 2) -> dict:
        # 增加状态记录
        state = {
            "current_step": "loading",
            "progress": 0
        }

        try:
            # 每个步骤更新状态
            state.update({"current_step": "loading", "progress": 10})
            df = await self._load_data(data_path)

            state.update({"current_step": "cleaning", "progress": 40})
            cleaned_df = self._clean_data(df, clean_config or {})

            # 初始化所有工具组件
            tools = {
                "loader": DataLoader(),
                "cleaner": DataCleaner(),
                "validator": DataValidator(),  # 新增验证器
                "analyzer": DataAnalyzer(),
                "saver": DataSaver(),
                "metadata": MetadataRecorder()  # 新增元数据记录
            }

            # 数据加载
            df = await self._safe_execute(tools["loader"], {"path": data_path})
            await tools["metadata"].execute({"step": "load", "status": "success"})

            # 数据清洗
            cleaned_df = await self._safe_execute(tools["cleaner"], df, clean_config or {})
            await tools["metadata"].execute({"step": "clean", "status": "success"})

            # 数据验证（新增步骤）
            validation_report = await self._safe_execute(
                tools["validator"],
                cleaned_df,
                {"schema": self._infer_schema(cleaned_df)}
            )
            if validation_report.get("error_count", 0) > 0:
                logger.warning(f"数据质量问题：{validation_report}")

            # 数据探索
            analyzer = DataAnalyzer()
            report = await analyzer.execute(
                cleaned_df,
                {
                    "analysis_level": explore_depth,
                    "algorithm": "xgboost"  # 新增算法配置
                }
            )
            explore_report = await self._safe_execute(tools["analyzer"], cleaned_df, {"depth": explore_depth})

            # 数据存储
            output_path = await self._safe_execute(tools["saver"], cleaned_df, {"format": "csv"})

            # 记录完整元数据
            await tools["metadata"].execute({
                "pipeline_id": self._generate_pipeline_id(),
                "steps": ["load", "clean", "validate", "analyze", "save"],
                "final_status": "completed"
            })

            # 新增报告生成
            reporter = ReportGenerator()
            report_path = await reporter.execute(
                analysis_report=explore_report,
                data_path=str(output_path),
                config={"output_dir": "./analysis_reports"}
            )

            return {
                **explore_report,
                "report_path": report_path,
                "cleaned_data_path": str(output_path)
            }
        except Exception as e:
            await tools["metadata"].execute({"step": "error", "error": str(e)})
            logger.error(f"ETL流程失败: {str(e)}")
            raise

    def _infer_schema(self, df: pd.DataFrame) -> dict:
        """自动推断数据schema"""
        return {
            "columns": {
                col: str(dtype) for col, dtype in df.dtypes.items()
            },
            "constraints": {
                col: {"nullable": False} for col in df.columns if not df[col].isnull().any()
            }
        }

    def _generate_pipeline_id(self) -> str:
        """生成唯一流程ID"""
        return f"ETL_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}"

    def _detect_source_type(self, path: str) -> str:
        """智能识别数据源类型"""
        if path.startswith(("mysql://", "postgresql://")):
            return "database"
        if path.startswith("http"):
            return "api"
        return "file"

    def _detect_output_format(self, input_path: str) -> str:
        """根据输入路径推断输出格式"""
        return Path(input_path).suffix.lstrip('.').lower() or 'csv'

    async def _safe_execute(self, tool: BaseTool, *args) -> any:
        """带错误处理的工具执行方法"""
        try:
            return await tool.execute(*args)
        except Exception as e:
            logger.error(f"工具执行失败 [{tool.__class__.__name__}]: {str(e)}")
            raise