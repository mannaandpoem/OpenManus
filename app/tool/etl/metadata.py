from ..base import BaseTool
from pathlib import Path
import json
from datetime import datetime
from typing import Dict

# 新增导入
from ...logger import logger

class MetadataRecorder(BaseTool):
    """元数据记录器"""

    name: str = "etl_metadata"
    description: str = "记录ETL流程元数据信息"
    parameters: dict = {
        "type": "object",
        "properties": {
            "pipeline_id": {"type": "string"},
            "data_source": {"type": "string"},
            "steps": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["pipeline_id", "data_source"]
    }
    def _validate_metadata(self, meta: dict) -> Dict:
        """根据parameters定义进行验证"""
        # 从类属性获取必填字段
        required_fields = self.parameters.get("required", [])
        for field in required_fields:
            if field not in meta:
                raise ValueError(f"缺少必要字段: {field}")
        return meta

    # 增加数据血缘追踪
    async def execute(self, meta: dict) -> bool:
        """增强版元数据记录"""
        full_meta = {
            **meta,
            "lineage": self._trace_data_lineage(meta.get("input_path")),
            "data_quality": self._assess_data_quality(meta.get("df"))
        }
        return await self._save_metadata(full_meta)

    async def _save_metadata(self, meta: dict) -> bool:  # 补全核心方法
        """实现元数据存储逻辑"""
        meta_file = Path("workspace/metadata") / f"{meta['pipeline_id']}.json"
        meta_file.parent.mkdir(exist_ok=True)

        try:
            # 追加模式写入历史记录
            with meta_file.open("a") as f:
                f.write(json.dumps(meta) + "\n")
            return True
        except IOError as e:
            raise RuntimeError(f"文件写入失败: {str(e)}") from e