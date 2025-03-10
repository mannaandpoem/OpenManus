import sys
from datetime import datetime
from typing import Dict, Optional, Callable, Any

from loguru import logger as _logger

from app.config import PROJECT_ROOT


_print_level = "INFO"
_websocket_managers = {}


def register_websocket_manager(name: str, manager: Any) -> None:
    """Register a WebSocket manager to receive log messages."""
    global _websocket_managers
    _websocket_managers[name] = manager


def unregister_websocket_manager(name: str) -> None:
    """Unregister a WebSocket manager."""
    global _websocket_managers
    if name in _websocket_managers:
        del _websocket_managers[name]


async def websocket_sink(message) -> None:
    """A sink function that sends logs to all registered WebSocket managers."""
    global _websocket_managers
    
    # Extract log details - the format differs between loguru versions
    if isinstance(message, dict):
        # Use the record dict directly
        record = message
    else:
        # Message is a string, parse it
        record = message.record
    
    # Get the level and message
    if hasattr(record["level"], "name"):
        level = record["level"].name.lower()
    else:
        level = str(record["level"]).lower()
    
    log_message = record["message"]
    
    # Send to all registered managers
    for manager in _websocket_managers.values():
        if hasattr(manager, "broadcast") and isinstance(manager.broadcast, Callable):
            try:
                await manager.broadcast(log_message, level)
            except Exception as e:
                # Don't let WebSocket errors affect logging
                print(f"Error broadcasting log: {e}")
                pass


def define_log_level(print_level="INFO", logfile_level="DEBUG", name: str = None):
    """Adjust the log level to above level"""
    global _print_level
    _print_level = print_level

    current_date = datetime.now()
    formatted_date = current_date.strftime("%Y%m%d%H%M%S")
    log_name = (
        f"{name}_{formatted_date}" if name else formatted_date
    )  # name a log with prefix name

    _logger.remove()
    _logger.add(sys.stderr, level=print_level)
    _logger.add(PROJECT_ROOT / f"logs/{log_name}.log", level=logfile_level)
    # Only add websocket sink when an event loop is running
    # The websocket server will register this sink when it starts
    return _logger


logger = define_log_level()


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
