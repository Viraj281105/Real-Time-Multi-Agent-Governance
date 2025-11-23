# services/api/main.py
import asyncio
import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from loguru import logger
from services.api.redis_client import get_redis

app = FastAPI(title="Real-Time Governance API")

SUBSCRIBE_STREAMS = ["market.ticks", "agent.proposals", "governance.votes", "execution.actions", "audit.events"]

class ConnectionManager:
    def __init__(self):
        self.active: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast(self, message: str):
        to_remove = []
        for ws in list(self.active):
            try:
                await ws.send_text(message)
            except Exception:
                to_remove.append(ws)
        for ws in to_remove:
            self.disconnect(ws)

manager = ConnectionManager()

@app.on_event("startup")
async def startup():
    logger.info("API startup: launching redis listener")
    asyncio.create_task(redis_listener())

@app.get("/")
def index():
    return {"status": "ok"}

@app.websocket("/ws/stream")
async def websocket_stream(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await asyncio.sleep(3600)  # keep alive; actual pushes come from redis_listener
    except WebSocketDisconnect:
        manager.disconnect(ws)

async def redis_listener():
    r = get_redis()
    # We'll use XREAD to read new events using a blocking read.
    last_ids = {s: "$" for s in SUBSCRIBE_STREAMS}  # start at new entries
    while True:
        try:
            # block for 2000 ms if no events
            resp = await r.xread(streams=last_ids, block=2000, count=10)
            if not resp:
                await asyncio.sleep(0.01)
                continue
            # resp is list of (stream_name, [(id, {b'field': b'value'})])
            for stream_name, entries in resp:
                for entry_id, fields in entries:
                    # Redis streams typically store a map; here we expect a single 'data' field with JSON bytes
                    payload = None
                    if b"data" in fields:
                        payload = fields[b"data"]
                        try:
                            # decode bytes to str
                            payload = payload.decode()
                        except Exception:
                            payload = str(payload)
                    else:
                        # fallback: show raw map
                        payload = {k.decode(): v.decode() if isinstance(v, bytes) else v for k, v in fields.items()}
                    doc = {"stream": stream_name.decode() if isinstance(stream_name, bytes) else stream_name, "id": entry_id, "data": payload}
                    # send to all websockets
                    await manager.broadcast(json.dumps(doc))
                    last_ids[stream_name] = entry_id
        except Exception as e:
            logger.exception("Redis listener error: {}", e)
            await asyncio.sleep(1)
