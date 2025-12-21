-- db/init.sql
-- PostgreSQL initialization script for Real-Time Multi-Agent Governance Engine

-- Enable UUID extension for generating unique IDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- MARKET DATA TABLES
-- ============================================================================

-- Market ticks table - stores all incoming market data
CREATE TABLE market_ticks (
    id BIGSERIAL PRIMARY KEY,
    stream_id UUID NOT NULL,
    timestamp BIGINT NOT NULL,  -- Unix timestamp in milliseconds
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    size DECIMAL(20, 8) NOT NULL,
    side VARCHAR(10) NOT NULL,  -- 'buy', 'sell', 'unknown'
    source VARCHAR(50) NOT NULL,  -- 'binance', 'replay', etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_side CHECK (side IN ('buy', 'sell', 'unknown'))
);

-- Index for fast time-series queries
CREATE INDEX idx_market_ticks_timestamp ON market_ticks(timestamp DESC);
CREATE INDEX idx_market_ticks_symbol ON market_ticks(symbol, timestamp DESC);

-- ============================================================================
-- AGENT TABLES
-- ============================================================================

-- Agent registry - tracks all agents in the system
CREATE TABLE agents (
    agent_id VARCHAR(100) PRIMARY KEY,
    agent_type VARCHAR(50) NOT NULL,  -- 'market', 'risk', 'compliance', etc.
    status VARCHAR(20) DEFAULT 'active',  -- 'active', 'inactive', 'suspended'
    config JSONB,  -- Agent-specific configuration
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_status CHECK (status IN ('active', 'inactive', 'suspended'))
);

-- Agent reputation tracking
CREATE TABLE agent_reputation (
    agent_id VARCHAR(100) PRIMARY KEY REFERENCES agents(agent_id) ON DELETE CASCADE,
    score DECIMAL(10, 2) DEFAULT 100.0,  -- Initial score: 100
    total_proposals INTEGER DEFAULT 0,
    approved_proposals INTEGER DEFAULT 0,
    rejected_proposals INTEGER DEFAULT 0,
    successful_actions INTEGER DEFAULT 0,
    failed_actions INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT positive_score CHECK (score >= 0)
);

-- Reputation history for tracking changes over time
CREATE TABLE reputation_history (
    id BIGSERIAL PRIMARY KEY,
    agent_id VARCHAR(100) REFERENCES agents(agent_id) ON DELETE CASCADE,
    old_score DECIMAL(10, 2),
    new_score DECIMAL(10, 2),
    delta DECIMAL(10, 2),
    reason VARCHAR(255),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- GOVERNANCE TABLES
-- ============================================================================

-- Proposals submitted by agents
CREATE TABLE proposals (
    proposal_id UUID PRIMARY KEY,
    agent_id VARCHAR(100) REFERENCES agents(agent_id),
    timestamp BIGINT NOT NULL,
    type VARCHAR(50) NOT NULL,  -- 'trade', 'halt', 'parameter_change', etc.
    payload JSONB NOT NULL,
    priority INTEGER DEFAULT 5,
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'voting', 'approved', 'rejected', 'executed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_proposal_status CHECK (status IN ('pending', 'voting', 'approved', 'rejected', 'executed', 'failed'))
);

CREATE INDEX idx_proposals_status ON proposals(status, created_at DESC);
CREATE INDEX idx_proposals_agent ON proposals(agent_id, created_at DESC);
CREATE INDEX idx_proposals_timestamp ON proposals(timestamp DESC);

-- Votes on proposals
CREATE TABLE votes (
    id BIGSERIAL PRIMARY KEY,
    proposal_id UUID REFERENCES proposals(proposal_id) ON DELETE CASCADE,
    agent_id VARCHAR(100) REFERENCES agents(agent_id),
    vote VARCHAR(10) NOT NULL,  -- 'approve', 'reject', 'abstain'
    weight DECIMAL(10, 2) DEFAULT 1.0,  -- Vote weight based on reputation
    reason TEXT,
    timestamp BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_vote CHECK (vote IN ('approve', 'reject', 'abstain')),
    UNIQUE(proposal_id, agent_id)  -- One vote per agent per proposal
);

CREATE INDEX idx_votes_proposal ON votes(proposal_id);
CREATE INDEX idx_votes_agent ON votes(agent_id, created_at DESC);

-- Governance rules and policies
CREATE TABLE governance_rules (
    rule_id VARCHAR(100) PRIMARY KEY,
    rule_type VARCHAR(50) NOT NULL,  -- 'voting_threshold', 'conflict_resolution', 'timeout', etc.
    rule_data JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Conflicts detected between proposals
CREATE TABLE proposal_conflicts (
    id BIGSERIAL PRIMARY KEY,
    proposal_id_1 UUID REFERENCES proposals(proposal_id),
    proposal_id_2 UUID REFERENCES proposals(proposal_id),
    conflict_type VARCHAR(50) NOT NULL,  -- 'opposite_trades', 'duplicate', 'resource_conflict'
    resolution VARCHAR(50),  -- 'priority', 'vote', 'reject_both', 'reject_later'
    resolved BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE INDEX idx_conflicts_unresolved ON proposal_conflicts(resolved, created_at) WHERE resolved = false;

-- ============================================================================
-- EXECUTION TABLES
-- ============================================================================

-- Actions executed by the system
CREATE TABLE actions (
    action_id UUID PRIMARY KEY,
    proposal_id UUID REFERENCES proposals(proposal_id),
    timestamp BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL,  -- 'pending', 'applied', 'failed', 'rolled_back'
    result JSONB,
    error_message TEXT,
    execution_time_ms INTEGER,  -- Time taken to execute in milliseconds
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    CONSTRAINT valid_action_status CHECK (status IN ('pending', 'applied', 'failed', 'rolled_back'))
);

CREATE INDEX idx_actions_status ON actions(status, created_at DESC);
CREATE INDEX idx_actions_proposal ON actions(proposal_id);
CREATE INDEX idx_actions_timestamp ON actions(timestamp DESC);

-- State snapshots for rollback capability
CREATE TABLE state_snapshots (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id UUID NOT NULL UNIQUE,
    action_id UUID REFERENCES actions(action_id),
    state_data JSONB NOT NULL,  -- Complete system state at this point
    timestamp BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_snapshots_timestamp ON state_snapshots(timestamp DESC);

-- ============================================================================
-- AUDIT & LOGGING TABLES
-- ============================================================================

-- Complete audit log of all system events
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL,
    event_source VARCHAR(100),  -- 'agent_runtime', 'governance', 'execution', 'api'
    event_data JSONB NOT NULL,
    severity VARCHAR(20) DEFAULT 'info',  -- 'debug', 'info', 'warning', 'error', 'critical'
    timestamp BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_severity CHECK (severity IN ('debug', 'info', 'warning', 'error', 'critical'))
);

CREATE INDEX idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_log_event_type ON audit_log(event_type, timestamp DESC);
CREATE INDEX idx_audit_log_severity ON audit_log(severity, timestamp DESC) WHERE severity IN ('error', 'critical');

-- System metrics for monitoring
CREATE TABLE system_metrics (
    id BIGSERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(20, 4),
    metric_unit VARCHAR(20),  -- 'ms', 'count', 'percent', etc.
    tags JSONB,  -- Additional metadata (e.g., {"component": "agent_runtime"})
    timestamp BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_metrics_name_timestamp ON system_metrics(metric_name, timestamp DESC);
CREATE INDEX idx_metrics_timestamp ON system_metrics(timestamp DESC);

-- ============================================================================
-- MATERIALIZED VIEWS FOR PERFORMANCE
-- ============================================================================

-- Agent performance summary
CREATE MATERIALIZED VIEW agent_performance_summary AS
SELECT 
    a.agent_id,
    a.agent_type,
    a.status,
    ar.score as reputation_score,
    ar.total_proposals,
    ar.approved_proposals,
    ar.rejected_proposals,
    CASE 
        WHEN ar.total_proposals > 0 
        THEN ROUND((ar.approved_proposals::DECIMAL / ar.total_proposals * 100), 2)
        ELSE 0 
    END as approval_rate,
    ar.successful_actions,
    ar.failed_actions,
    CASE 
        WHEN (ar.successful_actions + ar.failed_actions) > 0 
        THEN ROUND((ar.successful_actions::DECIMAL / (ar.successful_actions + ar.failed_actions) * 100), 2)
        ELSE 0 
    END as success_rate,
    ar.last_updated
FROM agents a
LEFT JOIN agent_reputation ar ON a.agent_id = ar.agent_id
ORDER BY ar.score DESC NULLS LAST;

CREATE UNIQUE INDEX idx_agent_perf_summary_id ON agent_performance_summary(agent_id);

-- Recent proposal statistics
CREATE MATERIALIZED VIEW recent_proposal_stats AS
SELECT 
    DATE_TRUNC('minute', created_at) as minute,
    status,
    type,
    COUNT(*) as count
FROM proposals
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY DATE_TRUNC('minute', created_at), status, type
ORDER BY minute DESC;

-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for proposals
CREATE TRIGGER update_proposals_updated_at BEFORE UPDATE ON proposals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger for governance_rules
CREATE TRIGGER update_rules_updated_at BEFORE UPDATE ON governance_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to refresh materialized views (call this periodically)
CREATE OR REPLACE FUNCTION refresh_all_materialized_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY agent_performance_summary;
    REFRESH MATERIALIZED VIEW recent_proposal_stats;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Insert default governance rules
INSERT INTO governance_rules (rule_id, rule_type, rule_data) VALUES
('voting_quorum', 'voting_threshold', '{"min_votes": 2, "approval_threshold": 0.51}'),
('proposal_timeout', 'timeout', '{"timeout_ms": 100}'),
('conflict_resolution', 'conflict_resolution', '{"strategy": "priority_based", "tie_breaker": "timestamp"}');

-- Insert system agent (for internal operations)
INSERT INTO agents (agent_id, agent_type, status) VALUES
('system', 'system', 'active');

INSERT INTO agent_reputation (agent_id, score) VALUES
('system', 1000.0);

-- ============================================================================
-- HELPFUL QUERIES (commented out)
-- ============================================================================

-- Get agent leaderboard:
-- SELECT * FROM agent_performance_summary ORDER BY reputation_score DESC LIMIT 10;

-- Get recent proposals:
-- SELECT * FROM proposals ORDER BY created_at DESC LIMIT 20;

-- Get voting statistics for a proposal:
-- SELECT p.proposal_id, p.type, 
--        COUNT(v.id) as total_votes,
--        SUM(CASE WHEN v.vote = 'approve' THEN 1 ELSE 0 END) as approve_count,
--        SUM(CASE WHEN v.vote = 'reject' THEN 1 ELSE 0 END) as reject_count
-- FROM proposals p
-- LEFT JOIN votes v ON p.proposal_id = v.proposal_id
-- GROUP BY p.proposal_id, p.type;

-- Get system latency metrics:
-- SELECT metric_name, AVG(metric_value) as avg_latency, MAX(metric_value) as max_latency
-- FROM system_metrics
-- WHERE metric_name LIKE '%_latency_ms' AND timestamp > EXTRACT(EPOCH FROM NOW() - INTERVAL '1 hour') * 1000
-- GROUP BY metric_name;