"""Text-based Pupster Agent — console input/output, no audio.

Usage:
    uv run python -m text_agent
    uv run python -m text_agent --llm-model glm-5-turbo
"""

import argparse
import asyncio
import json
import logging
import os
import sys

from dotenv import load_dotenv
from openai import AsyncOpenAI

from agent.config import ZMQ_CMD_ADDR
from text_agent.agent import TextPupsterAgent, load_system_prompt

load_dotenv(".env.local")
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pupster.text")


async def chat_loop(agent: TextPupsterAgent, client: AsyncOpenAI, model: str) -> None:
    messages = [
        {"role": "system", "content": load_system_prompt()},
        {"role": "assistant", "content": "Hi! I'm Pupster! 🐾 Tell me what to do!"},
    ]

    print("\nPupster: Hi! I'm Pupster! Tell me what to do!")
    print("  (type 'quit' or Ctrl+C to exit)\n")

    loop = asyncio.get_event_loop()

    while True:
        try:
            user_input = await loop.run_in_executor(None, lambda: input("You: "))
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        user_input = user_input.strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break

        messages.append({"role": "user", "content": user_input})

        # Call LLM with tools, loop until no more tool_calls
        while True:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=agent.tools,
            )

            choice = response.choices[0]
            msg = choice.message

            # Handle tool calls
            if msg.tool_calls:
                messages.append(msg.model_dump())
                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    fn_args = json.loads(tc.function.arguments)
                    logger.info(f"[tool_call] {fn_name}({fn_args})")

                    result = agent.call_tool(fn_name, fn_args)
                    logger.info(f"[tool_result] {result}")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
                # Continue loop to let LLM respond after tool results
                continue

            # Text response — print it
            if msg.content:
                print(f"\nPupster: {msg.content}\n")
                messages.append(msg.model_dump())

            break


def main():
    parser = argparse.ArgumentParser(description="Pupster Text Agent — console control for MuJoCo simulation")
    parser.add_argument(
        "--llm-provider",
        choices=["openai", "glm"],
        default=os.getenv("LLM_PROVIDER", "glm"),
    )
    parser.add_argument(
        "--llm-model",
        default=os.getenv("LLM_MODEL", "glm-5-turbo"),
    )
    args = parser.parse_args()

    if args.llm_provider == "glm":
        base_url = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/coding/paas/v4")
        api_key = os.getenv("GLM_API_KEY")
        if not api_key:
            print("Error: GLM_API_KEY env var is required", file=sys.stderr)
            sys.exit(1)
    else:
        base_url = None
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY env var is required", file=sys.stderr)
            sys.exit(1)

    logger.info(f"LLM: {args.llm_provider} ({args.llm_model})")
    if base_url:
        logger.info(f"Base URL: {base_url}")

    agent = TextPupsterAgent()
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    asyncio.run(chat_loop(agent, client, args.llm_model))


if __name__ == "__main__":
    main()
