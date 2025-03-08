import asyncio

from app.agent.manus import Manus
from app.flow.base import FlowType
from app.flow.flow_factory import FlowFactory


async def run_flow():
    agent = Manus()

    while True:
        try:
            prompt = input("Enter your prompt (or 'exit' / 'q' to quit): ")
            if prompt.lower() == "exit" or prompt.lower() == "q":
                print("Goodbye!")
                break

            flow = FlowFactory.create_flow(
                flow_type=FlowType.PLANNING,
                agents=agent,
            )

            print("Processing your request...")
            result = await flow.execute(prompt)
            print(result)

        except KeyboardInterrupt:
            print("Goodbye!")
            break


if __name__ == "__main__":
    asyncio.run(run_flow())
