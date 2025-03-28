from functools import lru_cache

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from ..base import BaseTool

# 在文件顶部新增导入
from sklearn.exceptions import NotFittedError
from ...logger import logger


class DataAnalyzer(BaseTool):
    """多维数据分析器｜生成深度分析报告"""

    name: str = "etl_analyzer"
    description: str = "执行数据探索性分析（EDA），生成统计报告及预测模型"
    parameters: dict = {
        "type": "object",
        "properties": {
            "analysis_level": {
                "type": "integer",
                "minimum": 1,
                "maximum": 3,
                "description": "分析深度级别（1-基础统计 2-高级分析 3-预测建模）",
                "default": 2
            }
        },
        "required": []
    }

    async def execute(self, df: pd.DataFrame, config: dict) -> dict:
        report = {"basic": self.basic_analysis(df)}

        if config.get("analysis_level", 2) >= 2:
            report["advanced"] = self.advanced_analysis(df)

        if config.get("analysis_level", 2) >= 3:
            report["predictive"] = self.predictive_analysis(df)

        return report

    @lru_cache(maxsize=128)
    def basic_analysis(self, df: pd.DataFrame) -> dict:
        """带缓存的基础分析
        参数:
            df: 输入数据框，将根据其内存地址进行缓存
        返回:
            包含基础统计信息的字典
        """
        # 生成数据指纹用于缓存键
        data_fingerprint = (
            df.shape,
            tuple(df.columns),
            tuple(df.dtypes.astype(str))
        )

        # 实际计算逻辑
        return {
            "data_shape": df.shape,
            "dtypes": df.dtypes.astype(str).to_dict(),
            "missing_values": df.isna().sum().to_dict(),
            "unique_counts": df.nunique().to_dict(),
            "_cache_key": hash(data_fingerprint)  # 调试用缓存键
        }

    # 2. 增量分析支持（代码中有注释但未实现）
    async def execute(self, df: pd.DataFrame, config: dict) -> dict:
        if "last_report" in config:
            return self._incremental_analysis(df, config["last_report"])

    def advanced_analysis(self, df: pd.DataFrame) -> dict:
        numeric_df = df.select_dtypes(include=np.number)

        # 修复1：添加缺失的分类统计代码
        categorical_stats = {
            col: {
                "value_counts": df[col].value_counts().to_dict(),
                "top_value": df[col].mode()[0] if not df[col].mode().empty else None
            } for col in df.select_dtypes(exclude=np.number).columns
        }

        # 修复2：添加时间序列分析结果
        time_analysis = self._temporal_analysis(df)

        return {
            "correlation_matrix": numeric_df.corr().to_dict(),
            "skewness": numeric_df.skew().to_dict(),
            "kurtosis": numeric_df.kurtosis().to_dict(),
            "categorical_stats": categorical_stats,
            "temporal_analysis": time_analysis
        }  # 结束advanced_analysis方法

    # 将方法移动到类的主体层级
    def _detect_target(self, df: pd.DataFrame) -> str:
        """更智能的目标列检测"""
        # 1. 优先检查列名包含'target'/'label'的列
        target_candidates = [col for col in df.columns if 'target' in col.lower() or 'label' in col.lower()]
        if target_candidates:
            return target_candidates[0]

        # 2. 原有逻辑作为fallback
        numeric_cols = df.select_dtypes(include=np.number).columns
        if len(numeric_cols) > 0:
            return numeric_cols[-1]  # 通常最后一列是目标列

        return df.columns[0]  # 默认返回第一列

    def _temporal_analysis(self, df: pd.DataFrame) -> dict:
        """增强时间序列分析"""
        time_cols = [col for col in df.columns if pd.api.types.is_datetime64_any_dtype(df[col])]
        if not time_cols:
            return {}

        return {
            col: {
                "min_date": df[col].min().isoformat(),
                "max_date": df[col].max().isoformat(),
                "time_interval": (df[col].max() - df[col].min()).days,
                "seasonality": self._check_seasonality(df[col]),  # 新增季节性检测
                "trend": self._detect_trend(df[col])  # 新增趋势分析
            } for col in time_cols
        }

    def predictive_analysis(self, df: pd.DataFrame) -> dict:
        try:
            # 过滤非数值列（包括时间戳）
            numeric_df = df.select_dtypes(include=[np.number])
            if numeric_df.empty:
                return {"error": "无可用数值型列进行建模"}

            # 只使用数值列进行分析
            target = self._detect_target(numeric_df)
            X = numeric_df.drop(columns=[target])
            y = df[target]

            if pd.api.types.is_numeric_dtype(y):
                model = RandomForestRegressor()
            else:
                model = RandomForestClassifier()
                y = LabelEncoder().fit_transform(y)

            model.fit(X, y)
            return {
                "target": target,
                "feature_importance": dict(zip(X.columns, model.feature_importances_))
            }
        except Exception as e:
            logger.error(f"预测分析异常: {str(e)}")
            return {"error": str(e)}
