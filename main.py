import asyncio

# Import the Manus agent and logger for handling user prompts and logging
from app.agent.manus import Manus
from app.logger import logger

# Define an asynchronous main function
async def main():
    agent = Manus()  # Initialize the Manus agent

    while True:
        try:
            # Get user input for the prompt
            prompt = input("Enter your prompt (or 'exit'/'quit' to quit): ")
            prompt_lower = prompt.lower()  # Convert to lowercase for easy comparison

            # Check if the user wants to exit
            if prompt_lower in ["exit", "quit"]:
                logger.info("Goodbye!")  # Log exit message
                break  # Exit the loop

            # Skip empty inputs
            if not prompt.strip():
                logger.warning("Skipping empty prompt.")
                continue

            logger.warning("Processing your request...")  # Notify user that the request is being processed

            # Run the Manus agent asynchronously with the provided prompt
            await agent.run(prompt)

        # Handle user interruption (Ctrl + C)
        except KeyboardInterrupt:
            logger.warning("Goodbye!")
            break  # Exit the loop gracefully

# Run the asynchronous main function when the script is executed
if __name__ == "__main__":
    asyncio.run(main())
