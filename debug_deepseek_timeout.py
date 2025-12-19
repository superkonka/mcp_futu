"""
Quick DeepSeek connectivity/timeout probe.

Usage:
  source venv/bin/activate
  python debug_deepseek_timeout.py

Reads DeepSeek config from .env via config.Settings. Prints latency and
whether content returned. Helps verify if current base_url/model hits
timeouts or 503.
"""
import asyncio
import time

from aiohttp import ClientTimeout

from config import settings
from services.deepseek_service import DeepSeekService


async def main() -> None:
    if not settings.deepseek_api_key:
        print("No DEEPSEEK_API_KEY configured in .env; abort.")
        return

    base_url = settings.deepseek_base_url or "https://api.deepseek.com/v1/chat/completions"
    model = settings.deepseek_model or "deepseek-chat"
    fundamental_model = settings.deepseek_fundamental_model or model
    reasoner = (
        settings.deepseek_reasoner_model
        or getattr(settings, "deepseek_reaspmer_model", None)
        or "deepseek-reasoner"
    )

    svc = DeepSeekService(
        settings.deepseek_api_key,
        base_url=base_url,
        model=model,
        fundamental_model=fundamental_model,
        reasoner_model=reasoner,
    )
    # Use a shorter timeout to expose latency/timeout quickly; adjust if needed.
    svc.timeout = ClientTimeout(total=20)

    system_prompt = "You are a test probe."
    user_prompt = "Reply with a short OK."

    start = time.perf_counter()
    content = await svc.chat(system_prompt, user_prompt, temperature=0.1)
    cost = time.perf_counter() - start

    print(f"Base URL: {svc.base_url}")
    print(f"Model: {model}")
    print(f"Took: {cost:.2f}s")
    if content:
        print("Result:")
        print(content[:400])
    else:
        print(f"FAILED. last_error={svc.last_error_message}")


if __name__ == "__main__":
    asyncio.run(main())
