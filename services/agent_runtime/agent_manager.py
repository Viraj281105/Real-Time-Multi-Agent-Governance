# services/agent_runtime/agent_manager.py
import asyncio
import json
from loguru import logger
import redis.asyncio as aioredis
import os
from .agents import MarketAgent, RiskAgent

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STREAM_NAME = "market.ticks"

async def start_manager():
    r = aioredis.from_url(REDIS_URL, decode_responses=False)
    logger.info("Agent manager started, listening to {}", STREAM_NAME)
    last_id = "$"
    agents = [MarketAgent(), RiskAgent()]

    while True:
        try:
            resp = await r.xread(streams={STREAM_NAME: last_id}, block=2000, count=10)
            if not resp:
                await asyncio.sleep(0.01)
                continue
            for stream_name, entries in resp:
                for entry_id, fields in entries:
                    # decode payload
                    raw = None
                    if b"data" in fields:
                        raw = fields[b"data"].decode()
                        try:
                            doc = json.loads(raw)
                        except Exception:
                            logger.warning("Bad tick JSON: {}", raw)
                            continue
                        # dispatch tick to all agents concurrently
                        await asyncio.gather(*[a.on_tick(doc) for a in agents])
                    last_id = entry_id
        except Exception as e:
            logger.exception("Agent manager error: {}", e)
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(start_manager())
