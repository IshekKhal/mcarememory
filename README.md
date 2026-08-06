# Milestone 1: 3-Node CockroachDB Cluster & Node-Kill Verification

This milestone establishes and verifies a local 3-node CockroachDB cluster using Docker Compose under WSL2/Docker.

## Architecture

- **Nodes**: 3 containers (`roach1`, `roach2`, `roach3`) attached to a shared Docker bridge network (`roachnet`).
- **SQL Port**: `26257` (exposed on host from `roach1`).
- **DB Console UI**: `http://localhost:8080` (exposed on host from `roach1`).
- **Storage**: Persistent Docker volumes (`roach1_data`, `roach2_data`, `roach3_data`) per node.
- **CockroachDB Image**: `cockroachdb/cockroach:v25.2.0`.

---

## Resource Requirements (WSL2 / Docker Desktop)

- **RAM**: Minimum **4 GB** dedicated to WSL2 / Docker daemon (Recommended: 6–8 GB). Each CockroachDB node consumes approximately 0.8 GB – 1.2 GB of RAM under light load.
- **CPU**: 2 or more CPU cores allocated to WSL2.
- **Disk Space**: At least 5 GB free disk space for Docker volumes and container images.

---

## Quickstart Instructions

### 1. Bring up the cluster
Start all 3 CockroachDB nodes in detached mode:
```bash
docker compose up -d
```

### 2. Initialize the cluster
Run the initialization script to bootstrap raft consensus across the 3 nodes:
```bash
bash init-cluster.sh
```
*Output will display cluster status and confirm the DB Console is available at `http://localhost:8080`.*

### 3. Run Node-Kill Fault Tolerance Verification
Execute the node-kill verification script:
```bash
bash verify-node-kill.sh
```

---

## Expected "Pass" Behavior

When `verify-node-kill.sh` runs successfully:
1. Database `survival_test` and table `cluster_verification` are created, and an initial record is inserted.
2. Container `roach2` is forcibly stopped using `docker kill roach2`.
3. Read and write SQL statements are executed against `roach1`. Because 2 out of 3 nodes (`roach1` & `roach3`) remain active, quorum (2/3 majority) is preserved. **The SQL INSERT and SELECT operations succeed instantly with zero downtime or data loss.**
4. Container `roach2` is restarted (`docker start roach2`), catch-up replication syncs missing data, and all 3 nodes report `is_live = true` in `cockroach node status`.
5. Script completes with output: `=== RESULT: PASS ===`.

---

## Resetting / Cleanup

To tear down the cluster and clean up all persistent data volumes:
```bash
docker compose down -v
```

---

# Milestone 2: Memory Schema (Relational + Vector)

Milestone 2 designs and implements the core memory layer for the autonomous agent in CockroachDB v25.2.0 (`agent_memory` database), combining relational conversation logs, persistent task state, and high-dimensional vector search.

## Schema Architecture & Table Descriptions

The agent's stateful memory system is structured across four primary tables:

- **`conversations`**: Acts as the top-level session ledger, pairing each conversation session with a unique UUID (`conversation_id`), the associated `agent_id`, and a timestamp to bound long-running interactive tasks.
- **`messages`**: Stores the full relational sequence of raw user and agent dialogue (`role`, `content`, `created_at`), maintaining chronological conversation context and establishing strict foreign key integrity back to `conversations`.
- **`task_state`**: Tracks in-flight multi-step agent execution state (`status`, `state` JSONB document), allowing an agent to preserve step state and resume execution seamlessly across node crashes or cluster failures without losing progress.
- **`memory_embeddings`**: Stores 1024-dimensional semantic vector embeddings (`VECTOR(1024)`) produced by Amazon Titan Text Embeddings V2, linking text content back to `conversations` and `messages`, backed by a native distributed C-SPANN vector index (`idx_memory_embeddings`) for high-performance Approximate Nearest Neighbor (ANN) similarity search.

## How to Apply the Schema & Migrations

Ensure the 3-node cluster is running, then apply the SQL schema file:

```bash
cat schema/001_agent_memory.sql | docker exec -i roach1 ./cockroach sql --insecure --host=roach1:26257
```

If migrating an existing cluster running Milestone 2 (1536 dimensions), apply the migration script:

```bash
cat schema/002_resize_embeddings_1024.sql | docker exec -i roach1 ./cockroach sql --insecure --host=roach1:26257
```

*Note: The migration automatically enables the v25.2 preview setting `feature.vector_index.enabled = true` and configures `sql_safe_updates = false` for vector index creation.*

## How to Run Schema & Vector Index Verification

To run full automated verification (schema migration, index inspection, relational seeding with 1024-dim vectors, cosine `<=>` similarity ordering, `EXPLAIN` vector index scan validation, and node-kill survival testing against `agent_memory`):

```bash
bash schema/verify_schema.sh
```

---

# Milestone 4: Caregiver Memory Semantic Recall & SageMaker Embedding Pivot

Milestone 4 connects the autonomous agent's memory store to a real vector embedding model, storing high-dimensional embeddings for caregiver notes in CockroachDB and performing semantic similarity recall using cosine distance (`<=>`).

## Architecture & SageMaker Embedding Model

To bypass Bedrock account quota defects, embedding generation is powered by a SageMaker JumpStart hosted **BAAI/bge-large-en-v1.5** model (`huggingface-sentencesimilarity-bge-large-en-v1-5`).

- **Vector Dimension**: 1024 float dimensions (exact match for CockroachDB `VECTOR(1024)` column).
- **Hosting**: SageMaker Endpoint on CPU instance (`ml.m5.xlarge`).
- **Endpoint State File**: The endpoint deployment script saves the active endpoint name to `sagemaker_endpoint.txt`, which `app/config.py` and `app/embeddings.py` automatically detect.

---

## ⚠️ CRITICAL WARNING: SAGEMAKER HOURLY BILLING

> [!WARNING]
> **SageMaker Endpoints Cost Money by the Hour**: Leaving a SageMaker endpoint running incurs ongoing hourly charges on your AWS account. **Always run `python scripts/teardown_embedding_endpoint.py` immediately when you finish testing or demoing.**

---

## Execution Order

Follow this exact sequence to run the demo:

### 1. Deploy SageMaker Embedding Endpoint
Deploy the `bge-large-en-v1.5` model to SageMaker JumpStart:
```bash
python scripts/deploy_embedding_endpoint.py
```
*Wait for the script to confirm the endpoint status is **InService**.*

### 2. Seed Caregiver Memory Data
Ingest 9 realistic caregiver notes for "Grandma Chen", compute their 1024-dim BGE embeddings via SageMaker, and persist them in CockroachDB:
```bash
python scripts/demo_seed.py
```

### 3. Run Semantic Query Recall Tests
Execute semantic vector search queries against CockroachDB:
```bash
# Run standard 3-question evaluation suite (medication, mood/anxiety, appointment)
python scripts/demo_query.py

# Or search with a custom query:
python scripts/demo_query.py "has Grandma Chen complained of physical pain?"
```

### 4. Teardown Endpoint (MANDATORY)
Delete the SageMaker endpoint and endpoint configuration to stop billing:
```bash
python scripts/teardown_embedding_endpoint.py
```
*Verify that `sagemaker_endpoint.txt` is removed and no endpoints remain active in SageMaker.*


