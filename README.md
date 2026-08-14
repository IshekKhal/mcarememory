# Grandma Chen Care Coordinator: Multi-Caregiver Memory & Conflict-Aware Agent

A distributed memory and coordination platform for families and professional caregivers managing care for an aging relative.

When multiple caregivers (family members, home nurses, visiting physicians) care for an individual, critical observations and medication updates are logged asynchronously across different shifts. Notes get lost, dosage changes cause confusion, and conflicting records create safety risks.

This platform provides a centralized, conflict-aware memory store. It records caregiver updates, indexes them with 1024-dimensional semantic vectors, and uses an AI coordinator agent to answer caregiver questions. When caregiver notes contradict one another, the agent flags the discrepancy with named attribution and timestamps rather than silently averaging or guessing the truth.

---

## Live Dataset & Current Scale

The production database is populated with an active care dataset:

- **Active Conversation ID**: `327dff0c-19f4-49db-b1c0-01aa51fc7594`
- **Unique Caregiver Notes**: 3,348 notes
- **Semantic Vector Embeddings**: 3,448 embeddings
- **Vector Search Performance**: Sub-15ms query latency on CockroachDB Cloud using distributed C-SPANN vector indexing

---

## Architecture Overview

```
 Caregivers & Family (Web UI / API)
                │
                ▼
      Flask / Gunicorn App
      (Chat History, Memory Stream, Live Simulation)
         │                       │
         ▼ (Embeddings)          ▼ (Reasoning & Synthesis)
 AWS SageMaker Serverless    Anthropic Claude Haiku 4.5
 (BAAI/bge-large-en-v1.5)    (Conflict Detection & Clinical Guardrails)
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
           CockroachDB Cloud
     (Relational Logs + 1024-dim C-SPANN Vector Index)
                     │
             (Optional Tooling)
     CockroachDB Cloud MCP Server (JSON-RPC)
```

### Core Components

1. **CockroachDB Cloud (Distributed Relational & Vector Store)**
   - Stores structured caregiver logs (`conversations`, `messages`, `task_state`, `memory_embeddings`).
   - Uses native `VECTOR(1024)` data types with C-SPANN approximate nearest neighbor indexes (`idx_memory_embeddings`).
   - Supports cosine distance ordering (`<=>`) for hybrid semantic and relational filtering.
   - Includes local 3-node Docker Compose setup with Raft consensus for offline development and fault tolerance testing.

2. **AWS SageMaker Serverless Inference (Embedding Pipeline)**
   - Hosts `BAAI/bge-large-en-v1.5` generating 1024-dimensional dense float vectors.
   - Configured for serverless inference (4096 MB memory, concurrency limit 10), scaling to zero when idle ($0/hr idle cost).

3. **Claude Haiku Coordinator Agent (Reasoning Layer)**
   - Retrieves top-k semantically relevant notes based on question context.
   - Cross-references caregiver observations to detect contradictory statements (such as conflicting medication dosages or missed schedules).
   - Formats answers with human-readable timestamps and caregiver names.
   - Enforces medical safety guardrails: refuses to diagnose conditions or modify treatment plans without physician direction.

4. **CockroachDB Cloud Model Context Protocol (MCP) Server**
   - Integrates with `https://cockroachlabs.cloud/mcp` for standardized tool discovery and SQL execution over JSON-RPC.

---

## Technology Stack

| Layer | Technology | Details |
| :--- | :--- | :--- |
| **Database** | CockroachDB Cloud (Serverless) | PostgreSQL-compatible, distributed SQL, C-SPANN vector index |
| **Embeddings** | AWS SageMaker Serverless | BAAI/bge-large-en-v1.5 (1024 dimensions) |
| **LLM Reasoning** | Anthropic Claude Haiku | `claude-haiku-4-5-20251001` with structured system prompt |
| **MCP Integration** | CockroachDB Cloud MCP Server | Model Context Protocol SSE / JSON-RPC endpoint |
| **Web Service** | Python, Flask, Gunicorn | Lightweight web UI with live chat and caregiver event feed |
| **Deployment** | Render & Docker Compose | Cloud hosting with `/healthz` endpoint, local 3-node cluster |

---

## Repository Structure

```
.
├── app/
│   ├── __init__.py                   # Package initialization
│   ├── config.py                     # Central environment variable configuration
│   ├── coordinator_agent.py          # Claude Haiku reasoning layer & prompt logic
│   ├── embeddings.py                 # SageMaker BGE embedding client
│   ├── mcp_client.py                 # CockroachDB Cloud MCP JSON-RPC client
│   ├── memory_store.py               # SQL queries, vector search & deduplication gateway
│   └── web_server.py                 # Flask application routes and API endpoints
├── docs/
│   ├── C1-command-reference.md       # Comprehensive milestone command cheat sheet
│   ├── ENV_VARS_GUIDE.md             # Plain-language environment variables guide
│   └── ENV_VARS_AUDIT.md             # Repository-wide environment variable audit
├── schema/
│   ├── 001_agent_memory.sql          # Base relational and vector schema
│   ├── 002_resize_embeddings_1024.sql # Vector dimension resize migration
│   ├── 003_add_caregiver_note_metadata.sql # Caregiver metadata columns migration
│   ├── 004_add_conflict_resolution.sql # Schema migration for resolution tracking
│   └── verify_schema.sh              # Automated schema verification script
├── scripts/
│   ├── __init__.py                   # Package initialization
│   ├── auto_safety_timer.py          # Auto-teardown safety timer for real-time endpoints
│   ├── consolidate_dataset.py        # Dataset consolidation across conversation IDs
│   ├── deduplicate_dataset.py        # Dataset audit and duplicate removal tool
│   ├── demo_ask.py                   # Interactive CLI Q&A coordinator demo
│   ├── demo_concurrent_writes.py     # Concurrent multi-caregiver write simulation
│   ├── demo_query.py                 # Semantic vector search query demo
│   ├── demo_resolve_conflict.py      # Conflict resolution workflow demo
│   ├── demo_scale_test.py            # Scale performance and latency benchmarking
│   ├── demo_seed.py                  # Database seeder with baseline caregiver notes
│   ├── demo_seed_conflict.py         # Seeds conflicting caregiver notes for testing
│   ├── deploy_embedding_endpoint.py  # Deploys real-time SageMaker BGE endpoint
│   ├── deploy_serverless_embedding_endpoint.py # Deploys SageMaker serverless BGE endpoint
│   ├── migrate_to_cloud.py           # Migration tool from local cluster to CockroachDB Cloud
│   ├── reconcile_dataset_counts.py   # Reconciles note and embedding counts
│   ├── teardown_embedding_endpoint.py # AWS resource cleanup utility
│   ├── test_mcp_discovery.py         # MCP protocol tool discovery test
│   ├── verify_cloud_explain.py       # EXPLAIN query validator for C-SPANN index
│   ├── verify_cloud_mcp.py           # Full 6-question benchmark test via Cloud MCP
│   └── verify_node_kill_live.py      # Live cluster node kill verification script
├── static/
│   ├── index.html                    # Web interface layout
│   └── app.js                        # Chat stream and memory feed controller
├── docker-compose.yml                # Local 3-node CockroachDB cluster configuration
├── init-cluster.sh                   # Raft cluster bootstrap script
├── verify-node-kill.sh               # Node-kill fault tolerance verification script
├── render.yaml                       # Infrastructure-as-code for Render deployment
└── requirements.txt                  # Python dependencies
```

---

## Setup & Run Instructions

### Prerequisites

- Python 3.10+
- Git
- AWS Account with SageMaker permissions (for embedding endpoint)
- CockroachDB Cloud account or local Docker Desktop installed
- Anthropic API Key

### 1. Clone Repository & Create Virtual Environment

```bash
git clone https://github.com/IshekKhal/mcarememory.git
cd mcarememory

python -m venv .venv
# On Windows (Git Bash / PowerShell):
source .venv/Scripts/activate
# On Linux / macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your credentials (for details on each variable, see [docs/ENV_VARS_GUIDE.md](docs/ENV_VARS_GUIDE.md) and [docs/ENV_VARS_AUDIT.md](docs/ENV_VARS_AUDIT.md)):

```bash
cp .env.example .env
```

Key configuration variables:

```ini
# AWS Credentials & Region
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=ap-south-1

# CockroachDB Cloud Connection
COCKROACH_CLOUD_URL=postgresql://user:password@host:26257/defaultdb?sslmode=verify-full
DB_MODE=cloud

# SageMaker Embedding Endpoint
EMBEDDING_MODE=sagemaker
SAGEMAKER_ENDPOINT_NAME=caregiver-bge-embeddings

# Anthropic Claude API
ANTHROPIC_API_KEY=your_anthropic_api_key
ANTHROPIC_MODEL=claude-haiku-4-5-20251001

# Active Session
ACTIVE_CONVERSATION_ID=327dff0c-19f4-49db-b1c0-01aa51fc7594
```

### 3. Deploy SageMaker Serverless Endpoint (One-Time Setup)

To deploy the persistent serverless embedding endpoint:

```bash
python scripts/deploy_serverless_embedding_endpoint.py
```

*The serverless endpoint scales to zero when idle.*

### 4. Run the Web Application

Start the local web server:

```bash
python app/web_server.py
```

Open `http://localhost:5000` in your browser to interact with the care coordinator, submit caregiver notes, and run live activity simulations.

---

## Running Verification Tests

For milestone-by-milestone terminal commands and full execution history, see [docs/C1-command-reference.md](docs/C1-command-reference.md).

### Test Vector Index Execution (`EXPLAIN`)

Verify that queries use the native CockroachDB C-SPANN index scan:

```bash
python scripts/verify_cloud_explain.py
```

### Run Full Coordinator Benchmark Suite

Run the 6-question benchmark evaluating conflict detection, mood synthesis, appointment recall, and medical safety guardrails:

```bash
python scripts/verify_cloud_mcp.py
```

### Local Offline Mode (Docker 3-Node Cluster)

To run entirely locally without CockroachDB Cloud:

1. Start the 3-node cluster:
   ```bash
   docker compose up -d
   bash init-cluster.sh
   ```

2. Apply the schema:
   ```bash
   cat schema/001_agent_memory.sql | docker exec -i roach1 ./cockroach sql --insecure --host=roach1:26257
   ```

3. Run node-kill fault tolerance verification:
   ```bash
   bash verify-node-kill.sh
   ```

---

## Key Features & Safety Mechanisms

- **Conflict Detection**: Detects mismatches in medication dosages, timing, and caregiver instructions across shifts.
- **Attribution & Timestamps**: Every synthesized answer cites the specific caregiver name and recorded time.
- **Medical Refusal Guardrail**: If asked for diagnosis or dosage changes, the agent directs caregivers to contact the prescribing physician.
- **Resilience**: Data persists across database node restarts and network interruptions via CockroachDB distributed consensus.
