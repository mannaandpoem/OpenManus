from typing import Dict, Any

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from app.tool.base import BaseTool
from app.logger import logger
from app.tool.python_execute import PythonExecute

# # 使用预设算法
# python run_mcp.py -p "分析数据：/Users/bob/Documents/code/OpenManus/workspace/ttemperature_regulation_smart_manufacturing.csv，算法类型xgboost，参数max_depth=5"
#
# # 使用自定义代码建模
# python run_mcp.py -p "分析数据：data.csv，自定义代码：'from lightgbm import LGBMClassifier...'"
# 在data_analysis.py前使用ETL
# etl_result = await ETLTool().execute(data_path)
# analysis_result = await DataAnalysisTool().execute(etl_result["cleaned_path"])
class DataAnalysisTool(BaseTool):
    """基础数据分析建模工具"""

    name: str = "data_analysis"
    description: str = "动态算法选择的数据分析工具"

    parameters: dict = {
        "type": "object",
        "properties": {
            "data_path": {"type": "string"},
            "algorithm": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["random_forest", "svm", "xgboost"]},
                    "params": {"type": "object"}
                },
                "required": ["type"]
            },
            "custom_code": {"type": "string"}
        },
        "required": ["data_path"]
    }

    async def execute(self, data_path: str, algorithm: dict = None, custom_code: str = None) -> Dict:
        """执行数据分析全流程"""
        try:
            # 1. 数据加载
            df = await self._load_data(data_path)

            # 2. 基础清洗
            cleaned_df = self._basic_clean(df)

            # 动态选择建模方式
            if custom_code:
                return await self._dynamic_modeling(cleaned_df, custom_code)
            return await self._train_model(cleaned_df, algorithm)

        except Exception as e:
            logger.error(f"数据分析失败: {str(e)}")
            return {"error": str(e)}

    async def _load_data(self, path: str) -> pd.DataFrame:
        """支持CSV/Excel数据加载"""
        if path.endswith('.csv'):
            return pd.read_csv(path)
        elif path.endswith(('.xls', '.xlsx')):
            return pd.read_excel(path)
        raise ValueError("不支持的文件格式")

    def _basic_clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """增强型数据清洗"""
        # 保留原始数据副本
        cleaned = df.copy()

        # 1. 自动识别日期列并转换为时间戳
        for col in cleaned.columns:
            if cleaned[col].dtype == 'object':
                try:
                    cleaned[col] = pd.to_datetime(cleaned[col], errors='raise')
                    cleaned[col] = cleaned[col].astype(np.int64)  # 转换为时间戳数值
                    logger.info(f"已转换日期列: {col}")
                except:
                    pass

        # 2. 处理分类数据
        cleaned = pd.get_dummies(cleaned, dummy_na=True)

        # 3. 过滤无效值（保留原有逻辑）
        cleaned = cleaned.dropna()
        return cleaned[(cleaned != np.inf).all(1)]

    async def _train_model(self, df: pd.DataFrame, algorithm: dict) -> Dict:
        # 确保所有数据为数值类型
        if not np.issubdtype(df.values.dtype, np.number):
            raise ValueError("存在非数值类型数据，请检查数据预处理流程")
        """支持多种预设算法"""
        X = df.iloc[:, :-1]
        y = df.iloc[:, -1]
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

        # 动态加载算法
        model = self._get_model(algorithm)
        model.fit(X_train, y_train)

        return {
            "algorithm": algorithm.get("type"),
            "accuracy": model.score(X_test, y_test),
            "features": X.columns.tolist()
        }
    async def _dynamic_modeling(self, df: pd.DataFrame, code: str) -> Dict:
        """使用PythonExecute执行动态建模代码"""
        template = f"""
import pandas as pd
from sklearn.model_selection import train_test_split

# 内置变量
df = pd.DataFrame({df.to_dict()})
X = df.iloc[:, :-1]
y = df.iloc[:, -1]

# 用户自定义代码
{code}

# 要求最后输出字典包含模型和评估结果
        """
        result = await PythonExecute().execute(code=template)
        return result.get("output", {})

    def _get_model(self, algorithm: dict):
        """获取算法实例"""
        algo_type = algorithm.get("type", "random_forest")
        params = algorithm.get("params", {})

        if algo_type == "random_forest":
            from sklearn.ensemble import RandomForestClassifier
            return RandomForestClassifier(**params)
        elif algo_type == "svm":
            from sklearn.svm import SVC
            return SVC(**params)
        elif algo_type == "xgboost":
            try:
                # 添加xgboost导入
                from xgboost import XGBClassifier
                return XGBClassifier(**params)
            except ImportError:
                raise ImportError("请先安装xgboost库: pip install xgboost")
        raise ValueError(f"未知算法类型: {algo_type}")