import asyncio
import os
import sys

from app.agent.manus import Manus
from app.logger import logger


async def main():
    agent = Manus()
    try:
        prompt = input("Enter your prompt: ")
        if not prompt.strip():
            logger.warning("Empty prompt provided.")
            return

        logger.warning("Processing your request...")
        await agent.run(prompt)
        logger.info("Request processing completed.")
    except KeyboardInterrupt:
        logger.warning("Operation interrupted.")


if __name__ == "__main__":
    # Fix for Windows asyncio pipe issues
    if sys.platform == 'win32':
        # Use the Proactor event loop policy on Windows to avoid pipe errors
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    finally:
        # Ensure all pending tasks are done and event loop is properly closed
        if sys.platform == 'win32' and hasattr(asyncio, '_get_running_loop'):
            try:
                loop = asyncio._get_running_loop()
                if loop is not None:
                    loop.close()
            except RuntimeError:
                pass
