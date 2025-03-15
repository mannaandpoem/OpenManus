import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP


# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, current_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp-server")

# Import OpenManus tools
from app.tool.browser_use_tool import BrowserUseTool
from app.tool.file_saver import FileSaver
from app.tool.google_search import GoogleSearch
from app.tool.python_execute import PythonExecute
from app.tool.terminate import Terminate


# Initialize FastMCP server
openmanus = FastMCP("openmanus")

# Initialize tool instances
browser_tool = BrowserUseTool()
google_search_tool = GoogleSearch()
python_execute_tool = PythonExecute()
file_saver_tool = FileSaver()
terminate_tool = Terminate()


# Browser tool
@openmanus.tool()
async def browser_use(
    action: str,
    url: str = None,
    index: int = None,
    text: str = None,
    script: str = None,
    scroll_amount: int = None,
    tab_id: int = None,
) -> str:
    """Execute various browser operations.

    Args:
        action: The browser operation to execute, possible values include:
            - navigate: Navigate to specified URL
            - click: Click on an element on the page
            - input_text: Input text into a text field
            - screenshot: Take a screenshot of the current page
            - get_html: Get HTML of the current page
            - get_text: Get text content of the current page
            - execute_js: Execute JavaScript code
            - scroll: Scroll the page
            - switch_tab: Switch to specified tab
            - new_tab: Open new tab
            - close_tab: Close current tab
            - refresh: Refresh current page
        url: URL for 'navigate' or 'new_tab' operations
        index: Element index for 'click' or 'input_text' operations
        text: Text for 'input_text' operation
        script: JavaScript code for 'execute_js' operation
        scroll_amount: Scroll pixels for 'scroll' operation (positive for down, negative for up)
        tab_id: Tab ID for 'switch_tab' operation
    """
    logger.info(f"Executing browser operation: {action}")
    result = await browser_tool.execute(
        action=action,
        url=url,
        index=index,
        text=text,
        script=script,
        scroll_amount=scroll_amount,
        tab_id=tab_id,
    )
    return json.dumps(result.model_dump())


@openmanus.tool()
async def get_browser_state() -> str:
    """Get current browser state, including URL, title, tabs and interactive elements."""
    logger.info("Getting browser state")
    result = await browser_tool.get_current_state()
    return json.dumps(result.model_dump())


# Google search tool
@openmanus.tool()
async def google_search(query: str, num_results: int = 10) -> str:
    """Execute Google search and return list of relevant links.

    Args:
        query: Search query
        num_results: Number of results to return (default is 10)
    """
    logger.info(f"Executing Google search: {query}")
    results = await google_search_tool.execute(query=query, num_results=num_results)
    return json.dumps(results)


# Python execution tool
@openmanus.tool()
async def python_execute(code: str, timeout: int = 5) -> str:
    """Execute Python code and return results.

    Args:
        code: Python code to execute
        timeout: Execution timeout in seconds
    """
    logger.info("Executing Python code")
    result = await python_execute_tool.execute(code=code, timeout=timeout)
    return json.dumps(result)


# File saver tool
@openmanus.tool()
async def file_saver(content: str, file_path: str, mode: str = "w") -> str:
    """Save content to local file.

    Args:
        content: Content to save
        file_path: File path
        mode: File open mode (default is 'w')
    """
    logger.info(f"Saving file: {file_path}")
    result = await file_saver_tool.execute(
        content=content, file_path=file_path, mode=mode
    )
    return result


# Terminate tool
@openmanus.tool()
async def terminate(status: str) -> str:
    """Terminate program execution.

    Args:
        status: Termination status, can be 'success' or 'failure'
    """
    logger.info(f"Terminating execution: {status}")
    result = await terminate_tool.execute(status=status)
    return result


# Clean up resources
async def cleanup():
    """Clean up all tool resources"""
    logger.info("Cleaning up resources")
    await browser_tool.cleanup()


# Register cleanup function
import atexit


atexit.register(lambda: asyncio.run(cleanup()))


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="OpenManus MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio"],
        default="stdio",
        help="Communication method: stdio or http (default: stdio)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    logger.info("Starting OpenManus server (stdio mode)")
    openmanus.run(transport="stdio")
