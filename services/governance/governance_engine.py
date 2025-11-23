# services/governance/governance_engine.py
import asyncio
import json
import redis.asyncio as aioredis
import os
from loguru import logger

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
PROPOSAL_STREAM = "agent.proposals"
EXEC_STREAM = "execution.actions"
AUDIT_STREAM = "audit.events"

async def governance_loop():
    r = aioredis.from_url(REDIS_URL, decode_responses=False)
    last_id = "$"
    logger.info("Governance engine started, listening to {}", PROPOSAL_STREAM)
    while True:
        try:
            resp = await r.xread(streams={PROPOSAL_STREAM: last_id}, block=2000, count=10)
            if not resp:
                await asyncio.sleep(0.01)
                continue
            for stream_name, entries in resp:
                for entry_id, fields in entries:
                    if b"data" not in fields:
                        continue
                    raw = fields[b"data"].decode()
                    proposal = json.loads(raw)
                    # SIMPLE POLICY: auto-approve trade proposals with low priority
                    if proposal.get("type") == "trade":
                        action = {
                            "action_id": proposal["proposal_id"],
                            "proposal_id": proposal["proposal_id"],
                            "timestamp": proposal["timestamp"],
                            "status": "applied",
                            "result": {"executed": True, "info": "auto-approved demo"}
                        }
                        await r.xadd(EXEC_STREAM, {"data": json.dumps(action)})
                        await r.xadd(AUDIT_STREAM, {"data": json.dumps({"event": "proposal_approved", "proposal": proposal})})
                        logger.info("Governance approved proposal {}", proposal["proposal_id"])
                    else:
                        # For simplicity, reject others (expand later)
                        action = {
                            "action_id": proposal["proposal_id"],
                            "proposal_id": proposal["proposal_id"],
                            "timestamp": proposal["timestamp"],
                            "status": "rejected",
                            "result": {"reason": "unsupported proposal type in demo"}
                        }
                        await r.xadd(EXEC_STREAM, {"data": json.dumps(action)})
                        await r.xadd(AUDIT_STREAM, {"data": json.dumps({"event": "proposal_rejected", "proposal": proposal})})
                    last_id = entry_id
        except Exception as e:
            logger.exception("Governance loop error: {}", e)
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(governance_loop())
