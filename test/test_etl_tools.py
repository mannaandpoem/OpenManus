import sys
from pathlib import Path

from app.tool.etl_tool import ETLTool

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

import pytest
import pandas as pd
from datetime import datetime

from app.tool.etl.analyzer import DataAnalyzer
from app.tool.etl.cleaner import DataCleaner
from app.tool.etl.loader import DataLoader
from app.tool.etl.metadata import MetadataRecorder
from app.tool.etl.saver import DataSaver



# 修改测试数据fixture
# 新增智能测试数据生成器
def generate_test_data(size=1000):
    """生成包含各种数据类型的测试数据"""
    dates = pd.date_range('2020-01-01', periods=size)
    return pd.DataFrame({
        'numeric': np.random.normal(0, 1, size),
        'categorical': np.random.choice(['A','B','C'], size),
        'datetime': dates,
        'missing': np.where(np.random.random(size) > 0.8, np.nan, 1),
        'text': [f"text_{i}" for i in range(size)]
    })

# 修改现有fixture
@pytest.fixture
def sample_data():
    return generate_test_data()  # 替代原有简单测试数据

# 修改集成测试中的元数据调用
class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_full_etl_flow(self, tmp_path):
        # 创建模拟数据文件
        test_data = pd.DataFrame({'test': [1,2,3]})
        test_path = tmp_path / "test.csv"
        test_data.to_csv(test_path)

        # 修改数据加载调用
        loader = DataLoader()
        df = await loader.execute({
            "source_type": "file",
            "path": str(test_path)  # 使用真实存在的文件路径
        })

        # 2. 数据清洗
        cleaner = DataCleaner()
        cleaned_df = await cleaner.execute(df, {
            "missing_strategy": "model_fill",
            "outlier_sensitivity": 2.5
        })

        # 3. 数据分析
        analyzer = DataAnalyzer()
        report = await analyzer.execute(cleaned_df, {"analysis_level": 3})

        # 4. 数据存储
        saver = DataSaver()
        output_path = await saver.execute(cleaned_df, {
            "output_format": "parquet",
            "compression": "snappy"
        })

        # 5. 元数据记录
        metadata = MetadataRecorder()  # 需要确保MetadataRecorder类已正确定义必填字段
        success = await metadata.execute({
            "pipeline_id": "TEST_123",
            "data_source": str(test_path),  # 补充必要字段
            "steps": ["load", "clean", "analyze", "save"]
        })

        assert Path(output_path).exists()
        assert success is True


# 新增异常数据测试用例
@pytest.mark.parametrize("bad_data", [
    pd.DataFrame(),                  # 空数据
    pd.DataFrame({'col': [None]*10}), # 全空值
    "not_a_dataframe",                # 错误类型
])
def test_error_handling(bad_data):
    with pytest.raises((ValueError, TypeError)):
        ETLTool().execute(bad_data)

# 修改现有fixture
@pytest.fixture
def sample_data():
    return generate_test_data()  # 替代原有简单测试数据

# 修改集成测试中的元数据调用
class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_full_etl_flow(self, tmp_path):
        # 创建模拟数据文件
        test_data = pd.DataFrame({'test': [1,2,3]})
        test_path = tmp_path / "test.csv"
        test_data.to_csv(test_path)

        # 修改数据加载调用
        loader = DataLoader()
        df = await loader.execute({
            "source_type": "file",
            "path": str(test_path)  # 使用真实存在的文件路径
        })

        # 2. 数据清洗
        cleaner = DataCleaner()
        cleaned_df = await cleaner.execute(df, {
            "missing_strategy": "model_fill",
            "outlier_sensitivity": 2.5
        })

        # 3. 数据分析
        analyzer = DataAnalyzer()
        report = await analyzer.execute(cleaned_df, {"analysis_level": 3})

        # 4. 数据存储
        saver = DataSaver()
        output_path = await saver.execute(cleaned_df, {
            "output_format": "parquet",
            "compression": "snappy"
        })

        # 5. 元数据记录
        metadata = MetadataRecorder()  # 需要确保MetadataRecorder类已正确定义必填字段
        success = await metadata.execute({
            "pipeline_id": "TEST_123",
            "data_source": str(test_path),  # 补充必要字段
            "steps": ["load", "clean", "analyze", "save"]
        })

        assert Path(output_path).exists()
        assert success is True


# 新增性能测试装饰器
from pytest_benchmark.fixture import benchmark

# 新增验证工具类
class ETLValidator:
    @staticmethod
    def validate_report(report: dict):
        """验证分析报告完整性"""
        required_keys = {'basic', 'cleaned_path', 'data_shape'}
        assert required_keys.issubset(report.keys())

        # 验证基础统计
        assert isinstance(report['basic']['data_shape'], tuple)
        assert len(report['basic']['data_shape']) == 2

# 在测试用例中使用
def test_report_structure(result):
    ETLValidator.validate_report(result)

def test_etl_performance(benchmark, sample_large_data):
    """ETL流程性能基准测试"""
    result = benchmark(ETLTool().execute, sample_large_data)
    assert result["data_shape"][0] > 0