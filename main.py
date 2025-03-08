import asyncio

from app.agent.manus import Manus
from app.logger import logger


async def main():
    agent = Manus()
    while True:
        try:
            prompt = input("Enter your prompt (or 'exit' / 'q' to quit): ")
            if prompt.lower() == "exit" or prompt.lower() == "q":
                logger.info("Goodbye!")
                break
            logger.warning("Processing your request...")
            await agent.run(prompt)
        except KeyboardInterrupt:
            logger.warning("Goodbye!")
            break


if __name__ == "__main__":
    asyncio.run(main())
