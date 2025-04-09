import asyncio

from app.agent.ppt import PPTAgent
from app.logger import logger


async def main():
    agent = PPTAgent()
    try:
        prompt = '''generate a python hello world program
'''
        if not prompt.strip():
            logger.warning("Empty prompt provided.")
            return

        logger.warning("Processing your request...")
        await agent.run(prompt)
        logger.info("Request processing completed.")
    except KeyboardInterrupt:
        logger.warning("Operation interrupted.")
    finally:
        # Ensure agent resources are cleaned up before exiting
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
