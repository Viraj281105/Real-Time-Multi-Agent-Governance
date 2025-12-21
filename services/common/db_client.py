# services/common/db_client.py
"""
PostgreSQL database client with connection pooling and async support.
"""
import os
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool
from sqlalchemy import text, MetaData
from loguru import logger

# Database configuration from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://governance_user:governance_pass@127.0.0.1:5432/governance_db"
)

# Connection pool settings
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))

# Global engine and session factory
_engine = None
_session_factory = None


def get_engine():
    """Get or create the SQLAlchemy async engine."""
    global _engine
    if _engine is None:
        logger.info(f"Creating database engine: {DATABASE_URL.split('@')[1]}")  # Don't log password
        _engine = create_async_engine(
            DATABASE_URL,
            pool_size=POOL_SIZE,
            max_overflow=MAX_OVERFLOW,
            pool_timeout=POOL_TIMEOUT,
            pool_recycle=POOL_RECYCLE,
            echo=os.getenv("DB_ECHO", "false").lower() == "true",  # SQL logging
            pool_pre_ping=True,  # Verify connections before using
        )
    return _engine


def get_session_factory():
    """Get or create the session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session():
    """
    Get a database session as an async context manager.
    
    Usage:
        async with get_session() as session:
            result = await session.execute(text("SELECT * FROM agents"))
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        await session.close()


async def execute_query(query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Execute a raw SQL query and return results as list of dicts.
    
    Args:
        query: SQL query string
        params: Optional parameters for the query
        
    Returns:
        List of row dicts
    """
    async with get_session() as session:
        result = await session.execute(text(query), params or {})
        if result.returns_rows:
            rows = result.fetchall()
            # Convert Row objects to dicts
            return [dict(row._mapping) for row in rows]
        return []


async def execute_mutation(query: str, params: Optional[Dict[str, Any]] = None) -> int:
    """
    Execute an INSERT, UPDATE, or DELETE query.
    
    Args:
        query: SQL query string
        params: Optional parameters for the query
        
    Returns:
        Number of affected rows
    """
    async with get_session() as session:
        result = await session.execute(text(query), params or {})
        await session.commit()
        return result.rowcount


async def health_check() -> bool:
    """
    Check if database connection is healthy.
    
    Returns:
        True if connection is working, False otherwise
    """
    try:
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


async def close_connections():
    """Close all database connections. Call this on shutdown."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database connections closed")


# ============================================================================
# CONVENIENCE FUNCTIONS FOR COMMON OPERATIONS
# ============================================================================

async def insert_market_tick(
    stream_id: str,
    timestamp: int,
    symbol: str,
    price: float,
    size: float,
    side: str,
    source: str = "unknown"
) -> int:
    """Insert a market tick into the database."""
    import json
    query = """
        INSERT INTO market_ticks (stream_id, timestamp, symbol, price, size, side, source)
        VALUES (CAST(:stream_id AS uuid), :timestamp, :symbol, :price, :size, :side, :source)
        RETURNING id
    """
    async with get_session() as session:
        result = await session.execute(
            text(query),
            {"stream_id": stream_id, "timestamp": timestamp, "symbol": symbol, 
             "price": price, "size": size, "side": side, "source": source}
        )
        row = result.fetchone()
        return row[0] if row else None


async def insert_proposal(
    proposal_id: str,
    agent_id: str,
    timestamp: int,
    prop_type: str,
    payload: Dict[str, Any],
    priority: int = 5
) -> None:
    """Insert a proposal into the database."""
    import json
    query = """
        INSERT INTO proposals (proposal_id, agent_id, timestamp, type, payload, priority)
        VALUES (CAST(:proposal_id AS uuid), :agent_id, :timestamp, :prop_type, CAST(:payload AS jsonb), :priority)
    """
    async with get_session() as session:
        await session.execute(
            text(query),
            {"proposal_id": proposal_id, "agent_id": agent_id, "timestamp": timestamp, 
             "prop_type": prop_type, "payload": json.dumps(payload), "priority": priority}
        )


async def update_proposal_status(proposal_id: str, status: str) -> None:
    """Update a proposal's status."""
    query = """
        UPDATE proposals 
        SET status = :status, updated_at = CURRENT_TIMESTAMP
        WHERE proposal_id = CAST(:proposal_id AS uuid)
    """
    async with get_session() as session:
        await session.execute(text(query), {"status": status, "proposal_id": proposal_id})


async def insert_vote(
    proposal_id: str,
    agent_id: str,
    vote: str,
    weight: float,
    timestamp: int,
    reason: Optional[str] = None
) -> None:
    """Insert a vote on a proposal."""
    query = """
        INSERT INTO votes (proposal_id, agent_id, vote, weight, timestamp, reason)
        VALUES (CAST(:proposal_id AS uuid), :agent_id, :vote, :weight, :timestamp, :reason)
        ON CONFLICT (proposal_id, agent_id) DO UPDATE
        SET vote = EXCLUDED.vote, weight = EXCLUDED.weight, reason = EXCLUDED.reason
    """
    async with get_session() as session:
        await session.execute(
            text(query),
            {"proposal_id": proposal_id, "agent_id": agent_id, "vote": vote, 
             "weight": weight, "timestamp": timestamp, "reason": reason}
        )


async def get_votes_for_proposal(proposal_id: str) -> List[Dict[str, Any]]:
    """Get all votes for a proposal."""
    query = """
        SELECT * FROM votes 
        WHERE proposal_id = CAST(:proposal_id AS uuid)
        ORDER BY created_at ASC
    """
    async with get_session() as session:
        result = await session.execute(text(query), {"proposal_id": proposal_id})
        return [dict(row._mapping) for row in result.fetchall()]


async def insert_action(
    action_id: str,
    proposal_id: str,
    timestamp: int,
    status: str,
    result: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    execution_time_ms: Optional[int] = None
) -> None:
    """Insert an execution action."""
    import json
    query = """
        INSERT INTO actions (action_id, proposal_id, timestamp, status, result, error_message, execution_time_ms)
        VALUES (CAST(:action_id AS uuid), CAST(:proposal_id AS uuid), :timestamp, :status, CAST(:result AS jsonb), :error_message, :execution_time_ms)
    """
    async with get_session() as session:
        await session.execute(
            text(query),
            {"action_id": action_id, "proposal_id": proposal_id, "timestamp": timestamp, 
             "status": status, "result": json.dumps(result) if result else None, 
             "error_message": error_message, "execution_time_ms": execution_time_ms}
        )


async def update_action_status(
    action_id: str,
    status: str,
    result: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None
) -> None:
    """Update an action's status and result."""
    import json
    query = """
        UPDATE actions 
        SET status = :status, 
            result = CAST(:result AS jsonb), 
            error_message = :error_message,
            completed_at = CURRENT_TIMESTAMP
        WHERE action_id = CAST(:action_id AS uuid)
    """
    async with get_session() as session:
        await session.execute(
            text(query),
            {"status": status, "result": json.dumps(result) if result else None, 
             "error_message": error_message, "action_id": action_id}
        )


async def insert_audit_log(
    event_type: str,
    event_source: str,
    event_data: Dict[str, Any],
    severity: str = "info",
    timestamp: Optional[int] = None
) -> None:
    """Insert an audit log entry."""
    import time
    import json
    if timestamp is None:
        timestamp = int(time.time() * 1000)
    
    query = """
        INSERT INTO audit_log (event_type, event_source, event_data, severity, timestamp)
        VALUES (:event_type, :event_source, CAST(:event_data AS jsonb), :severity, :timestamp)
    """
    async with get_session() as session:
        await session.execute(
            text(query),
            {"event_type": event_type, "event_source": event_source, 
             "event_data": json.dumps(event_data), "severity": severity, "timestamp": timestamp}
        )


async def record_metric(
    metric_name: str,
    metric_value: float,
    metric_unit: str = "count",
    tags: Optional[Dict[str, Any]] = None,
    timestamp: Optional[int] = None
) -> None:
    """Record a system metric."""
    import time
    import json
    if timestamp is None:
        timestamp = int(time.time() * 1000)
    
    query = """
        INSERT INTO system_metrics (metric_name, metric_value, metric_unit, tags, timestamp)
        VALUES (:metric_name, :metric_value, :metric_unit, CAST(:tags AS jsonb), :timestamp)
    """
    async with get_session() as session:
        await session.execute(
            text(query),
            {"metric_name": metric_name, "metric_value": metric_value, "metric_unit": metric_unit,
             "tags": json.dumps(tags) if tags else None, "timestamp": timestamp}
        )


async def get_agent_reputation(agent_id: str) -> Optional[Dict[str, Any]]:
    """Get reputation for a specific agent."""
    query = """
        SELECT * FROM agent_reputation
        WHERE agent_id = :agent_id
    """
    async with get_session() as session:
        result = await session.execute(text(query), {"agent_id": agent_id})
        row = result.fetchone()
        return dict(row._mapping) if row else None


async def update_agent_reputation(
    agent_id: str,
    score_delta: float,
    reason: str
) -> None:
    """Update agent reputation score."""
    # First, get current score
    current = await get_agent_reputation(agent_id)
    if not current:
        # Initialize reputation if doesn't exist
        query = """
            INSERT INTO agent_reputation (agent_id, score)
            VALUES (:agent_id, 100.0)
        """
        async with get_session() as session:
            await session.execute(text(query), {"agent_id": agent_id})
        current = {"score": 100.0}
    
    old_score = float(current["score"])
    new_score = max(0, old_score + score_delta)  # Don't go below 0
    
    # Update reputation
    query = """
        UPDATE agent_reputation
        SET score = :new_score, last_updated = CURRENT_TIMESTAMP
        WHERE agent_id = :agent_id
    """
    async with get_session() as session:
        await session.execute(text(query), {"new_score": new_score, "agent_id": agent_id})
    
    # Log history
    history_query = """
        INSERT INTO reputation_history (agent_id, old_score, new_score, delta, reason)
        VALUES (:agent_id, :old_score, :new_score, :delta, :reason)
    """
    async with get_session() as session:
        await session.execute(
            text(history_query),
            {"agent_id": agent_id, "old_score": old_score, "new_score": new_score, 
             "delta": score_delta, "reason": reason}
        )


async def get_agent_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Get top agents by reputation score."""
    query = """
        SELECT * FROM agent_performance_summary
        ORDER BY reputation_score DESC
        LIMIT :limit
    """
    async with get_session() as session:
        result = await session.execute(text(query), {"limit": limit})
        return [dict(row._mapping) for row in result.fetchall()]


async def register_agent(agent_id: str, agent_type: str, config: Optional[Dict[str, Any]] = None) -> None:
    """Register a new agent in the system."""
    import json
    
    # Use CAST instead of :: for type casting to avoid parameter binding issues
    query = """
        INSERT INTO agents (agent_id, agent_type, config)
        VALUES (:agent_id, :agent_type, CAST(:config AS jsonb))
        ON CONFLICT (agent_id) DO UPDATE
        SET last_seen = CURRENT_TIMESTAMP, status = 'active'
    """
    async with get_session() as session:
        await session.execute(
            text(query),
            {"agent_id": agent_id, "agent_type": agent_type, "config": json.dumps(config) if config else None}
        )
    
    # Initialize reputation if new agent
    rep = await get_agent_reputation(agent_id)
    if not rep:
        init_query = """
            INSERT INTO agent_reputation (agent_id, score)
            VALUES (:agent_id, 100.0)
        """
        async with get_session() as session:
            await session.execute(text(init_query), {"agent_id": agent_id})


async def refresh_materialized_views() -> None:
    """Refresh all materialized views for updated statistics."""
    query = "SELECT refresh_all_materialized_views()"
    await execute_query(query)
    logger.info("Materialized views refreshed")


# ============================================================================
# INITIALIZATION
# ============================================================================

async def initialize_database():
    """Initialize database connection and verify schema."""
    logger.info("Initializing database connection...")
    
    # Test connection
    if not await health_check():
        raise RuntimeError("Failed to connect to database")
    
    logger.info("Database connection established successfully")
    
    # Refresh materialized views
    try:
        await refresh_materialized_views()
    except Exception as e:
        logger.warning(f"Could not refresh materialized views (expected on first run): {e}")


if __name__ == "__main__":
    # Test the database client
    import asyncio
    
    async def test():
        await initialize_database()
        
        # Test health check
        healthy = await health_check()
        print(f"Database healthy: {healthy}")
        
        # Test agent registration
        await register_agent("test_agent_1", "market")
        print("Agent registered")
        
        # Test reputation query
        rep = await get_agent_reputation("test_agent_1")
        print(f"Agent reputation: {rep}")
        
        await close_connections()
    
    asyncio.run(test())