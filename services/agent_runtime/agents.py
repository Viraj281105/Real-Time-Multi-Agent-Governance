# services/agent_runtime/agents.py
import uuid
import json
import time
from loguru import logger
from .agent_interface import AgentInterface
import redis.asyncio as aioredis
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
PROPOSAL_STREAM = "agent.proposals"

class MarketAgent(AgentInterface):
    def __init__(self, agent_id="agent.market.1"):
        self.agent_id = agent_id
        self.r = aioredis.from_url(REDIS_URL, decode_responses=False)

    async def on_tick(self, tick):
        # very simple logic: if price falls too fast, propose BUY (demo)
        price = tick.get("price")
        symbol = tick.get("symbol")
        proposal = {
            "proposal_id": str(uuid.uuid4()),
            "agent_id": self.agent_id,
            "timestamp": int(time.time() * 1000),
            "type": "trade",
            "payload": {"symbol": symbol, "side": "buy", "size": 0.001, "price": price},
            "priority": 5
        }
        await self.r.xadd(PROPOSAL_STREAM, {"data": json.dumps(proposal)})
        logger.debug("MarketAgent proposed: {}", proposal)

    async def on_event(self, event):
        # ignore for now
        pass

class RiskAgent(AgentInterface):
    def __init__(self, agent_id="agent.risk.1"):
        self.agent_id = agent_id
        self.r = aioredis.from_url(REDIS_URL, decode_responses=False)

    async def on_tick(self, tick):
        # Sample: if price drops more than threshold, propose halt
        price = tick.get("price")
        symbol = tick.get("symbol")
        # dummy condition — extend later
        if price and price < 0:
            proposal = {
                "proposal_id": str(uuid.uuid4()),
                "agent_id": self.agent_id,
                "timestamp": int(time.time() * 1000),
                "type": "halt",
                "payload": {"reason": "price anomaly", "symbol": symbol},
                "priority": 10
            }
            await self.r.xadd(PROPOSAL_STREAM, {"data": json.dumps(proposal)})
            logger.debug("RiskAgent proposed: {}", proposal)

    async def on_event(self, event):
        # react to proposals if needed
        pass
