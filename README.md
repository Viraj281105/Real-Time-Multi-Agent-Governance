# ⚡ Real-Time Multi-Agent Governance Engine  
*A low-latency, event-driven governance system for real-time financial markets.*

## 📌 Overview
This project implements a **real-time multi-agent governance engine** where autonomous agents
consume **live crypto/stock market data**, generate proposals, negotiate through a governance layer,
and execute final decisions atomically.

The system is designed for **Level-B realtime (50–300ms latency)**, making it suitable for
research, simulation, and prototyping of trading governance systems.

## 🚀 Key Features
- **Live Market Feed (Binance WebSocket)** with fallback replay mode  
- **Event-driven Agent Runtime** using Python asyncio  
- **Redis Streams** as a durable real-time event bus  
- **Governance Layer**  
  - reputation-weighted voting  
  - arbitration for conflicting proposals  
  - rule enforcement engine  
- **Execution Engine** with atomic state updates  
- **PostgreSQL WAL-based event logging**  
- **Next.js Dashboard** with real-time WebSocket updates  
- **Full Docker Compose environment**

## 🧠 Architecture
```
 Market Data → Redis Streams → Agents → Governance → Execution → Postgres WAL → Dashboard
```

### Components:
- **Market Feed:** normalizes ticks and publishes to `market.ticks`
- **Agents:** strategy, risk, compliance, anomaly, and rule agents
- **Governance Engine:** votes, resolves conflicts, maintains rules
- **Execution Layer:** applies final actions atomically
- **Dashboard:** real-time visualization of system state

## 📂 Folder Structure (Planned)
```
/repo
├─ /services
│  ├─ /market_feed
│  ├─ /agent_runtime
│  ├─ /governance
│  ├─ /execution
│  └─ /api
├─ /frontend
├─ /db
├─ /infra
├─ /scripts
├─ /tests
└─ README.md
```

## 🐳 Running Locally
1. Install Docker & Docker Compose  
2. Run:  
```bash
docker-compose up -d
```
3. Start agents:
```bash
python -m services.agent_runtime.main
```
4. Start dashboard:
```bash
cd frontend
npm install
npm run dev
```

## 📉 Latency Targets
- Tick ingestion: **< 50 ms**
- Agent reaction: **< 100 ms**
- Governance resolution: **< 200 ms**
- End-to-end action: **50–300 ms**

## 🧪 Testing
- Integration tests for tick replay
- Governance consistency tests
- Latency profiling (p50/p95/p99)

## 📜 License
MIT License — see `LICENSE` for details.

---

## 👤 Author
**Viraj Jadhao**  
Real-time systems + AI engineering  
