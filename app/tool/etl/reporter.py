from ..base import BaseTool
import pandas as pd
import plotly.express as px
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import os
from ...logger import logger

class ReportGenerator(BaseTool):
    """ETL可视化报告生成器｜生成交互式分析报告"""

    name: str = "etl_reporter"
    description: str = "生成包含可视化图表的HTML格式ETL分析报告"
    parameters: dict = {
        "type": "object",
        "properties": {
            "output_dir": {
                "type": "string",
                "default": "./reports",
                "description": "报告输出目录"
            },
            "template_name": {
                "type": "string",
                "default": "default_report.html",
                "description": "Jinja2模板名称"
            }
        }
    }

    async def execute(self, analysis_report: dict, data_path: str, config: dict) -> str:
        """生成可视化报告"""
        try:
            # 创建输出目录
            output_dir = Path(config.get("output_dir", "./reports"))
            output_dir.mkdir(parents=True, exist_ok=True)

            # 生成可视化图表
            visuals = await self._generate_visuals(analysis_report, data_path)

            # 渲染HTML模板
            env = Environment(loader=FileSystemLoader("templates/etl"))
            template = env.get_template(config.get("template_name", "default_report.html"))

            html_content = template.render(
                report=analysis_report,
                visuals=visuals,
                data_source=Path(data_path).name
            )

            # 保存报告
            report_path = output_dir / f"report_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}.html"
            with open(report_path, "w") as f:
                f.write(html_content)

            return str(report_path)

        except Exception as e:
            logger.error(f"报告生成失败: {str(e)}")
            raise

    async def _generate_visuals(self, report: dict, data_path: str) -> dict:
        """生成Plotly可视化图表"""
        df = pd.read_parquet(data_path) if data_path.endswith(".parquet") else pd.read_csv(data_path)

        visuals = {}

        # 1. 数据分布可视化
        if "basic" in report:
            for col in df.select_dtypes(include='number'):
                fig = px.histogram(df, x=col, title=f"{col}分布直方图")
                visuals[f"{col}_dist"] = fig.to_html(full_html=False)

        # 2. 相关性矩阵
        if "advanced" in report:
            fig = px.imshow(
                pd.DataFrame(report["advanced"]["correlation_matrix"]),
                labels=dict(x="特征", y="特征", color="相关性"),
                title="特征相关性热力图"
            )
            visuals["correlation_heatmap"] = fig.to_html(full_html=False)

        # 3. 特征重要性
        if "predictive" in report and "feature_importance" in report["predictive"]:
            importance_df = pd.DataFrame({
                "feature": report["predictive"]["feature_importance"].keys(),
                "importance": report["predictive"]["feature_importance"].values()
            })
            fig = px.bar(importance_df, x='feature', y='importance', title="特征重要性排序")
            visuals["feature_importance"] = fig.to_html(full_html=False)

        return visuals
