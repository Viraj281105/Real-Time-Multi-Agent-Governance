# services/execution/execution_engine.py
import asyncio
import json
import os
from loguru import logger
import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
EXEC_STREAM = "execution.actions"
AUDIT_STREAM = "audit.events"
LOGFILE = os.getenv("EXEC_LOG", "execution.log")

async def execution_loop():
    r = aioredis.from_url(REDIS_URL, decode_responses=False)
    last_id = "$"
    logger.info("Execution engine started, listening to {}", EXEC_STREAM)
    while True:
        try:
            resp = await r.xread(streams={EXEC_STREAM: last_id}, block=2000, count=10)
            if not resp:
                await asyncio.sleep(0.01)
                continue
            for stream_name, entries in resp:
                for entry_id, fields in entries:
                    if b"data" not in fields:
                        continue
                    raw = fields[b"data"].decode()
                    action = json.loads(raw)
                    # Apply action to local state (demo: append to log file)
                    with open(LOGFILE, "a", encoding="utf-8") as f:
                        f.write(json.dumps(action) + "\n")
                    await r.xadd(AUDIT_STREAM, {"data": json.dumps({"event": "action_executed", "action": action})})
                    logger.info("Executed action {}", action.get("action_id"))
                    last_id = entry_id
        except Exception as e:
            logger.exception("Execution loop error: {}", e)
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(execution_loop())
