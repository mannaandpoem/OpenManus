import os
import time
from pathlib import Path
import sys
from loguru import logger

# 获取项目根目录
project_root = Path(__file__).parent.parent

# 创建logs目录
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# 检查是否指定了日志文件
log_file = os.environ.get("OPENMANUS_LOG_FILE")

if not log_file:
    # 如果没有指定，检查是否有任务ID（从session或工作区目录名）
    task_id = os.environ.get("OPENMANUS_TASK_ID", "")
    
    # 使用任务ID作为日志文件名，而不是使用日期时间格式
    if task_id:
        # 确保任务ID以job_开头
        if not task_id.startswith("job_"):
            task_id = f"job_{task_id}"
        log_filename = f"{task_id}.log"
    else:
        # 如果没有任务ID，使用时间戳创建一个job_ID格式的日志文件名
        job_id = f"job_{int(time.time())}"
        log_filename = f"{job_id}.log"
    
    log_file = logs_dir / log_filename
else:
    # 使用指定的日志文件
    log_file = Path(log_file)

# 配置loguru日志
logger.remove()  # 移除默认的handler
# 添加控制台输出
logger.add(
    sys.stderr,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    level="INFO",
)
# 添加文件输出
logger.add(
    log_file,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    level="INFO",
    rotation="100 MB",
    retention="10 days",
)

# 导出配置好的logger
__all__ = ["logger"]

if __name__ == "__main__":
    logger.info("Starting application")
    logger.debug("Debug message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical message")

    try:
        raise ValueError("Test error")
    except Exception as e:
        logger.exception(f"An error occurred: {e}")
