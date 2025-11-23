# services/market_feed/replay_player.py
import argparse
import asyncio
import pandas as pd
import time
import json
import uuid
from loguru import logger
import redis.asyncio as aioredis
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STREAM_NAME = "market.ticks"

async def publish_tick(r, tick):
    data = {
        "stream_id": str(uuid.uuid4()),
        "timestamp": int(tick["timestamp"]),
        "symbol": tick["symbol"],
        "price": float(tick["price"]),
        "size": float(tick.get("size", 0)),
        "side": tick.get("side", "unknown"),
        "source": "replay",
    }
    # store JSON bytes under field 'data'
    await r.xadd(STREAM_NAME, {"data": json.dumps(data)})

async def run_player(file_path, speed=1.0, realtime=False):
    r = aioredis.from_url(REDIS_URL, decode_responses=False)
    logger.info("Loading ticks from {}", file_path)
    if file_path.endswith(".parquet"):
        df = pd.read_parquet(file_path)
    else:
        df = pd.read_csv(file_path)
    df = df.sort_values("timestamp")
    logger.info("Loaded {} ticks", len(df))
    if realtime:
        # publish as fast as coming (based on timestamp delta)
        prev_ts = None
        for _, row in df.iterrows():
            ts = int(row["timestamp"])
            if prev_ts is not None:
                delta = (ts - prev_ts) / 1000.0
                await asyncio.sleep(delta / speed)
            await publish_tick(r, row)
            prev_ts = ts
    else:
        # publish at fixed interval scaled by speed
        interval = max(0.001, 1.0 / speed)
        for _, row in df.iterrows():
            await publish_tick(r, row)
            await asyncio.sleep(interval)
    logger.info("Replay finished")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", "-f", required=True, help="CSV or parquet file with ticks (timestamp,symbol,price,size,side)")
    parser.add_argument("--speed", "-s", type=float, default=1.0, help="Speed multiplier (1.0 = 1 tick/sec default for non-realtime)")
    parser.add_argument("--realtime", action="store_true", help="Replay using timestamp gaps")
    args = parser.parse_args()
    asyncio.run(run_player(args.file, speed=args.speed, realtime=args.realtime))
