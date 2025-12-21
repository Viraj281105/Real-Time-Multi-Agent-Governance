# services/common/__init__.py
"""
Common utilities and shared code for all services.
"""

from .db_client import (
    get_session,
    execute_query,
    execute_mutation,
    health_check,
    initialize_database,
    close_connections,
    insert_market_tick,
    insert_proposal,
    update_proposal_status,
    insert_vote,
    get_votes_for_proposal,
    insert_action,
    update_action_status,
    insert_audit_log,
    record_metric,
    get_agent_reputation,
    update_agent_reputation,
    get_agent_leaderboard,
    register_agent,
    refresh_materialized_views,
)

__all__ = [
    "get_session",
    "execute_query",
    "execute_mutation",
    "health_check",
    "initialize_database",
    "close_connections",
    "insert_market_tick",
    "insert_proposal",
    "update_proposal_status",
    "insert_vote",
    "get_votes_for_proposal",
    "insert_action",
    "update_action_status",
    "insert_audit_log",
    "record_metric",
    "get_agent_reputation",
    "update_agent_reputation",
    "get_agent_leaderboard",
    "register_agent",
    "refresh_materialized_views",
]