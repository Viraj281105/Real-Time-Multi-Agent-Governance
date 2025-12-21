# test_db.py
import asyncio
from services.common.db_client import (
    initialize_database,
    register_agent,
    get_agent_reputation,
    update_agent_reputation,
    insert_audit_log,
    get_agent_leaderboard,
    close_connections,
)

async def test_database():
    print("🔧 Initializing database...")
    await initialize_database()
    
    print("\n✅ Registering test agents...")
    await register_agent("test_agent_1", "market", {"strategy": "momentum"})
    await register_agent("test_agent_2", "risk", {"threshold": 0.1})
    await register_agent("test_agent_3", "compliance", {})
    
    print("\n📊 Checking initial reputation...")
    for agent_id in ["test_agent_1", "test_agent_2", "test_agent_3"]:
        rep = await get_agent_reputation(agent_id)
        print(f"  {agent_id}: Score = {rep['score']}")
    
    print("\n📈 Updating reputation scores...")
    await update_agent_reputation("test_agent_1", +10, "successful_proposal")
    await update_agent_reputation("test_agent_2", -5, "rejected_proposal")
    await update_agent_reputation("test_agent_3", +15, "compliance_check_passed")
    
    print("\n🏆 Agent leaderboard:")
    leaderboard = await get_agent_leaderboard(limit=5)
    for i, agent in enumerate(leaderboard, 1):
        print(f"  {i}. {agent['agent_id']}: {agent['reputation_score']} points")
    
    print("\n📝 Inserting audit log...")
    await insert_audit_log(
        event_type="test_event",
        event_source="test_script",
        event_data={"message": "Database test successful"},
        severity="info"
    )
    
    print("\n✅ All tests passed!")
    await close_connections()

if __name__ == "__main__":
    asyncio.run(test_database())