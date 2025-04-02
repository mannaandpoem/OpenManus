from app.tool.python_execute import PythonExecute
from app.config import config


class NormalPythonExecute(PythonExecute):
    """A tool for executing Python code with timeout and safety restrictions."""

    name: str = "python_execute"
    description: str = (
        """Execute Python code for in-depth data analysis / data report(task conclusion) / other normal task without direct visualization.
# Note
1. The code should generate a comprehensive text-based report containing dataset overview, column details, basic statistics, derived metrics, timeseries comparisons, outliers, and key insights.
2. Use print() for all outputs so the analysis (including sections like 'Dataset Overview' or 'Preprocessing Results') is clearly visible and save it also
3. Save any report / processed files / each analysis result in worksapce directory: {directory}
4. You can invode this tool step-by-step to do data analysis from summary to in-depth""".format(
            directory=config.workspace_root
        )
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "code_type": {
                "description": "code type, data process / data report / others",
                "type": "string",
                "default": "process",
                "enum": ["process", "report", "others"],
            },
            "code": {
                "type": "string",
            },
        },
        "required": ["code"],
    }

    async def execute(self, code: str, code_type: str | None = None, timeout=5):
        return await super().execute(code, timeout)
