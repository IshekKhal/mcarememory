# Command Reference

All commands below are specified for **Git Bash** terminal on Windows.

---

## Milestone 1: 3-Node CockroachDB Cluster & Node-Kill

### Bring up 3-node cluster
```bash
docker compose up -d
```

### Initialize Raft consensus cluster
```bash
bash init-cluster.sh
```

### Run Node-Kill Fault Tolerance Verification
```bash
bash verify-node-kill.sh
```

### Tear down cluster and remove data volumes
```bash
docker compose down -v
```

---

## Milestone 2: Memory Schema & Migrations

### Apply fresh SQL schema (1024-dim vectors)
```bash
cat schema/001_agent_memory.sql | docker exec -i roach1 ./cockroach sql --insecure --host=roach1:26257
```

### Apply migration from 1536 to 1024 dimensions
```bash
cat schema/002_resize_embeddings_1024.sql | docker exec -i roach1 ./cockroach sql --insecure --host=roach1:26257
```

### Run Schema & Vector Index Automated Verification
```bash
bash schema/verify_schema.sh
```

---

## Milestone 4: Caregiver Memory Semantic Recall (SageMaker BGE)

### Deploy SageMaker BGE-large-en-v1.5 Embedding Endpoint (Auto-Safety-Timer Enabled)
```bash
# Standard deploy (Auto-starts safety timer with 60-minute default teardown)
python scripts/deploy_embedding_endpoint.py

# Deploy with custom safety timer duration (e.g. 90 minutes auto-teardown)
SAFETY_TIMER_MINUTES=90 python scripts/deploy_embedding_endpoint.py

# Short-duration test deploy (e.g. 0.2 minutes / 12 seconds auto-teardown test)
SAFETY_TIMER_MINUTES=0.2 python scripts/deploy_embedding_endpoint.py
```

### Standalone Safety Countdown Timer (Manual Mode)
```bash
# Launch safety timer manually for active endpoint (default 60 minutes or via env var)
python scripts/auto_safety_timer.py

# Launch safety timer with explicit duration
python scripts/auto_safety_timer.py --minutes 30
```

### Seed Caregiver Memory Notes
```bash
python scripts/demo_seed.py
```

### Run Raw Vector Semantic Recall Query
```bash
# Standard 3-question evaluation suite
python scripts/demo_query.py

# Custom query
python scripts/demo_query.py "has Grandma Chen complained of physical pain?"
```

### Teardown SageMaker Embedding Endpoint (MANDATORY)
```bash
python scripts/teardown_embedding_endpoint.py
```


---

## Milestone 5: Coordinator Agent Reasoning Layer (Claude Haiku 4.5)

### Set Anthropic API Key (Environment variable or `.env`)
```bash
export ANTHROPIC_API_KEY="your_api_key_here"
```

### Run Synthesized Coordinator Agent Q&A
```bash
# Standard 5-question verification suite (mood, medication, appointment, no-match, medical advice)
python scripts/demo_ask.py

# Custom question synthesis
python scripts/demo_ask.py "has she seemed confused or anxious lately?"
```

---

## Milestone 6: Concurrent Multi-Caregiver Write Simulation

### Run Concurrent Multi-Caregiver Write Simulation
```bash
python scripts/demo_concurrent_writes.py
```
*Expected Output*: Resets care record to 9 base notes, fires 3 caregiver writes concurrently on separate threads with millisecond timestamps showing overlapping execution, and verifies all 12 notes are stored with 0 errors.

### Verify Multi-Caregiver Synthesis across Concurrent Writes
```bash
python scripts/demo_ask.py "what updates were logged by her caregivers this afternoon regarding her left knee and physical therapy?"
```
*Expected Output*: Synthesizes a response combining notes written concurrently by Nurse Sarah (topical pain cream), Maria (physical therapy appointment), and David (resting on porch).

---

## Milestone 7: Conflict-Aware Coordinator Agent

### Seed Care Record with Conflicting Caregiver Notes
```bash
python scripts/demo_seed_conflict.py
```
*Expected Output*: Resets care record memory to 9 baseline notes and inserts 2 conflicting caregiver notes regarding Grandma Chen's afternoon blood pressure medication (11 total notes in database with embeddings).

### Run Conflict-Aware Agent Question Synthesis (Conflict Query)
```bash
python scripts/demo_ask.py "was her afternoon blood pressure medication given today?"
```
*Expected Output*: Agent detects the contradiction between Maria's 2:00 PM note (medication given) and Nurse Sarah's 2:30 PM note (medication missed), explicitly surfacing the discrepancy, caregiver names, and reported times instead of blending them or silently choosing one.

### Run Verification Suite (Conflict + Non-Conflict Queries)
```bash
python scripts/demo_ask.py
```
*Expected Output*: Executes the full 6-question suite demonstrating explicit discrepancy flagging on conflict queries alongside normal synthesized answers for non-conflicting queries (mood, appointments, zero-hallucination, medical advice guardrail).

---

## Milestone 8: Warmer Conflict Wording, Readable Timestamps, and Conflict Resolution

### 1. Apply Migration for Conflict Resolution Linkage
```bash
cat schema/004_add_conflict_resolution.sql | docker exec -i roach1 ./cockroach sql --insecure --host=roach1:26257
```
*Expected Output*: Adds `resolves_note_ids TEXT[]` column to `messages` table in CockroachDB.

### 2. Seed Care Record with Conflicting Caregiver Notes
```bash
python scripts/demo_seed_conflict.py
```
*Expected Output*: Resets care record memory to 9 baseline notes and inserts 2 conflicting caregiver notes regarding Grandma Chen's afternoon blood pressure medication.

### 3. Verify Warm Conflict-Aware Synthesis & Readable Timestamps (Unresolved Conflict)
```bash
python scripts/demo_ask.py "was her afternoon blood pressure medication given today?"
```
*Expected Output*: Agent outputs a warm, gentle heads-up ("Quick heads-up, there's a mismatch here...") detailing Maria's 2:00 PM note and Nurse Sarah's 2:30 PM note with human-readable timestamps (`2:00 PM`, `2:30 PM`), without raw ISO strings or alarming alert syntax.

### 4. Record Conflict Resolution Note
```bash
python scripts/demo_resolve_conflict.py
```
*Expected Output*: Ingests resolution note into memory store linked to conflicting note IDs and confirms message insertion.

### 5. Verify Resolved Conflict Synthesis
```bash
python scripts/demo_ask.py "was her afternoon blood pressure medication given today?"
```
*Expected Output*: Agent states confirmed outcome plainly (that the 2:00 PM dose was given) and references that it was resolved after an initial mix-up, without re-flagging it as an open conflict.

### 6. Run Verification Suite (Resolved + Baseline Queries)
```bash
python scripts/demo_ask.py
```
*Expected Output*: Executes standard verification suite demonstrating clean resolution synthesis alongside baseline queries (mood, appointments, zero-hallucination, medical advice guardrail).

---

## Milestone 9: Web Demo UI (Single-Page Care Coordinator Interface)

### 1. Launch Web Server
```bash
python app/web_server.py
```
*Expected Output*: Starts Flask web server listening at `http://localhost:5000` with active conversation ID loaded.

### 2. Open Local Web Interface in Browser
Open `http://localhost:5000` in your web browser.
*Expected Output*: Displays clean Care Coordinator dashboard with active conversation status, live auto-refreshing memory stream on the right, and interactive "Ask Coordinator Assistant" + "Log Caregiver Note" panels on the left.

### 3. Verify Live Memory Stream & Conflict Synthesis in UI
- Click any quick question chip (e.g., `"was her afternoon blood pressure medication given today?"`) or type a question and click **Synthesize Answer**.
- *Expected Output*: Synthesizes a conflict-aware response directly in the UI with warm heads-up / discrepancy styling when mismatches exist.

### 4. Log New Caregiver Note via UI Form
- Fill in Caregiver Name (e.g. `Maria (Caregiver)`), Category (e.g. `Observation`), and Note Content.
- Click **Log Caregiver Note**.
- *Expected Output*: Real 1024-dim SageMaker vector embedding is computed and persisted to CockroachDB. The live memory stream updates within seconds via background polling.

---

## Milestone 10: UI Polish, Git Catch-Up, and Scale Verification (250 Notes)

### 1. Launch Polished Web UI
```bash
python app/web_server.py
```
*Expected Output*: Starts Flask web server at `http://localhost:5000`. Browser displays polished 3-section caregiver dashboard with `marked.js` formatted answers, non-technical caregiver wording, collapsible Developer Info drawer, and healthcare visual theme.

### 2. Run Scale Verification Benchmark (250 Notes)
```bash
python scripts/demo_scale_test.py
```
*Expected Output*: Creates a separate scale test conversation ID, seeds 250 realistic caregiver notes with 1024-dim embeddings, executes 4 benchmark queries, and verifies sub-15ms pgvector query latency and 100% recall quality.

### 3. Teardown SageMaker Embedding Endpoint (MANDATORY after testing)
```bash
python scripts/teardown_embedding_endpoint.py
```
*Expected Output*: Deletes SageMaker endpoint and endpoint config to prevent incurring AWS charges.

---

## Milestone 11: CockroachDB Cloud Migration, Dataset Consolidation & MCP Integration

### 1. Consolidate Local Dataset Across Scale Runs
```bash
python scripts/consolidate_dataset.py
```
*Expected Output*: Merges local scale run data into a consolidated dataset (5,884 messages, 5,984 embeddings) with zero duplicate records.

### 2. Migrate Schema and Data to CockroachDB Cloud (`cdbaws`)
```bash
python scripts/migrate_to_cloud.py
```
*Expected Output*: Creates tables and vector indexes on CockroachDB Cloud cluster (`cdbaws`) and streams all messages and embeddings.

### 3. Reconcile Cloud Dataset Row Counts
```bash
python scripts/reconcile_dataset_counts.py
```
*Expected Output*: Verifies 100% row count match between local database and CockroachDB Cloud.

### 4. Verify C-SPANN Vector Index Usage (`EXPLAIN`)
```bash
python scripts/verify_cloud_explain.py
```
*Expected Output*: Displays EXPLAIN output confirming C-SPANN index scan (`memory_embeddings_embedding_idx`) on CockroachDB Cloud.

### 5. Test CockroachDB Cloud MCP Tool Discovery & SQL Execution
```bash
python scripts/test_mcp_discovery.py
```
*Expected Output*: Discovers 12 MCP tools, auto-resolves cluster UUID (`a60f9d0e-5826-4029-98d2-6d8fb0f92e94`), and executes test query.

### 6. Run Full Coordinator Agent Q&A Suite via Cloud MCP (`DB_MODE=cloud-mcp`)
```bash
python scripts/verify_cloud_mcp.py
```
*Expected Output*: Executes 6 caregiver questions through `CockroachCloudMCPClient` using `https://cockroachlabs.cloud/mcp` with CTE vector formatting (query length ~9.1KB, safely under the 16,384 character limit). Auto-resolves cluster UUID via JSON-RPC, confirming conflict detection, resolution retrieval, synthesized answers, and medical safety guardrails.

### 7. Deploy BGE-large-en-v1.5 to SageMaker Serverless Inference (Persistent / No Auto-Teardown)
```bash
python scripts/deploy_serverless_embedding_endpoint.py
```
*Expected Output*: Deploys BGE-large-en-v1.5 to SageMaker Serverless Inference via raw `boto3` (`CreateModel`, `CreateEndpointConfig`, `CreateEndpoint`) with 4096MB memory and max concurrency 10. Scales to 0 when idle ($0/hr idle cost). The auto-safety-timer has been removed from this script so the serverless endpoint remains persistently live for the hackathon judging window.

### 8. Dataset Identity & Humanized Coordinator Agent Verification
```bash
# Verify CockroachDB Cloud conversation dataset identity (Target ID: 327dff0c-19f4-49db-b1c0-01aa51fc7594 with 5,884 notes)
python -c "import os; os.environ['DB_MODE']='cloud'; from scripts.reconcile_dataset_counts import reconcile_dataset_counts; reconcile_dataset_counts()"

# Execute humanized 6-question suite via Cloud MCP (verifying direct tone, specific named attribution, no em dashes, no repetitive tics)
python scripts/verify_cloud_mcp.py
```
*Expected Output*: Confirms 1 active conversation on Cloud (`327dff0c-19f4-49db-b1c0-01aa51fc7594` with 5,884 notes and 5,984 embeddings) and verifies synthesized natural-language responses without robotic phrasing tics.

---

## Milestone 12: Web UI Chat Revamp, Live Simulation, & Render Hosting

### 1. Run Local Web App with Revamped Chat Interface
```bash
python app/web_server.py
```
*Expected Output*: Starts Flask web server at `http://localhost:5000`. Browser displays scrolling back-and-forth chat history (`#chat-history`) with user and assistant bubbles, markdown synthesis, preset chips, live activity simulation button, and live caregiver memory feed.

### 2. Verify Health Check Endpoint
```bash
curl http://localhost:5000/healthz
```
*Expected Output*: Instant HTTP 200 response `{"status": "ok"}` with zero database or AI calls.

### 3. Run Live Simulation & Conflict Detection Verification
- Open `http://localhost:5000` in browser.
- Click **⚡ Simulate Live Activity** button in the app header (or run `curl -X POST http://localhost:5000/api/simulate`).
- *Expected Output*: Inserts 4 new realistic caregiver notes (including a conflicting pair: Dr. Vance's order for Lisinopril 20mg vs Caregiver Mark's administration of Lisinopril 10mg) into CockroachDB. Notes immediately appear in the **Live Care Record** feed.
- Ask the chat: *"Was there any blood pressure medication discrepancy today?"*
- *Expected Output*: Coordinator agent detects the conflict in real time and highlights the mismatch between Dr. Vance's 20mg order and Caregiver Mark's 10mg administration with an amber discrepancy banner.

### 4. Deploying to Render (Free Tier)
1. Log into your Render account at [dashboard.render.com](https://dashboard.render.com).
2. Click **New +** -> **Web Service**.
3. Connect your GitHub repository (`IshekKhal/mcarememory`).
4. Render will automatically detect `render.yaml`, or you can manually set:
   - **Name**: `grandma-chen-care-coordinator`
   - **Runtime**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app.web_server:app`
   - **Health Check Path**: `/healthz`
5. Configure Environment Variables in Render Dashboard under **Environment**:
   - `COCKROACH_CLOUD_URL` (CockroachDB Cloud connection string, e.g. `postgresql://user:pass@host:26257/defaultdb?sslmode=verify-full`)
   - `ANTHROPIC_API_KEY` (Your Anthropic Claude API key)
   - `AWS_REGION` (`ap-south-1`)
   - `AWS_ACCESS_KEY_ID` (AWS Access Key for SageMaker Serverless endpoint)
   - `AWS_SECRET_ACCESS_KEY` (AWS Secret Key)
   - `ACTIVE_CONVERSATION_ID` (`327dff0c-19f4-49db-b1c0-01aa51fc7594` or default active conversation ID)
   - `DB_MODE` (`cloud` or `local`)
6. Click **Deploy Web Service**.

### 5. Keep-Alive Uptime Monitor Setup (UptimeRobot)
Render free instances sleep after 15 minutes of inactivity. Keep your instance permanently active with a free uptime monitor:
1. Create a free account at [uptimerobot.com](https://uptimerobot.com).
2. Click **Add New Monitor**.
3. Configure settings:
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `Grandma Chen Care Coordinator Health`
   - **URL / IP**: `https://your-render-app-name.onrender.com/healthz`
   - **Monitoring Interval**: `Every 10 minutes` (or 5 minutes)
4. Click **Create Monitor**. UptimeRobot will ping `/healthz` every 10 minutes, preventing Render from sleeping without incurring database/AI costs.

---

## Milestone 13: Region Fix Verification, Production-Scale Simulation, & Fact Re-Check

### 1. Verify AWS Region Configuration across Repo
```bash
# Ensure no hardcoded us-east-1 remains in application or config files
grep -rn "us-east-1" app/ render.yaml C1-command-reference.md
```
*Expected Output*: Zero matches. All AWS region defaults configured to `ap-south-1`.

### 2. Run Production-Scale Simulation & Fact Re-Check Script
```bash
# Verifies /api/simulate against 5,884+ note active conversation and executes direct SQL fact queries
python scripts/verify_step2_step3.py
```
*Expected Output*:
- Captures note & embedding count before and after `/api/simulate` (+4 delta on 5,884+ notes).
- Synthesizes conflict-aware answer via `/api/ask`.
- Executes direct SQL queries against `messages` table for Jennifer Lisinopril entries and David vegetable soup entries.

### 3. Direct SQL Fact Audit Queries (CockroachDB CLI / psycopg2)
```sql
-- Query 1: Jennifer blood pressure / Lisinopril timing notes
SELECT message_id, caregiver_name, note_type, content, created_at
FROM messages
WHERE conversation_id = '327dff0c-19f4-49db-b1c0-01aa51fc7594'
  AND (caregiver_name ILIKE '%Jennifer%' OR content ILIKE '%Jennifer%' OR content ILIKE '%Lisinopril%' OR content ILIKE '%blood pressure%')
ORDER BY created_at ASC;

-- Query 2: David vegetable soup / food notes
SELECT message_id, caregiver_name, note_type, content, created_at
FROM messages
WHERE conversation_id = '327dff0c-19f4-49db-b1c0-01aa51fc7594'
  AND (content ILIKE '%soup%' OR content ILIKE '%vegetable%' OR (caregiver_name ILIKE '%David%' AND content ILIKE '%food%'))
ORDER BY created_at ASC;
```

---

## Milestone 14: Flagship Retrieval Fix, Full Dataset Deduplication, & Gateway Safeguard

### 1. Maria's Note Reword & SageMaker Embedding Regeneration
```bash
python scripts/apply_note_reword.py
```
*Expected Output*: Updates `message_id: 9990a8de-e074-4002-a5e8-c8c9fac19f16` in `messages` and `memory_embeddings` to `"Gave Grandma Chen her afternoon blood pressure medication booster (Amlodipine 5mg) at 2:00 PM with a glass of water after her nap."` and regenerates its 1024-dim embedding via SageMaker.

### 2. Full Dataset Deduplication & Safety Cross-Reference
```bash
# Dry run scan and safeguard cross-reference
python scripts/deduplicate_dataset.py

# Execute chunked deletion (2,536 duplicate rows removed)
python scripts/deduplicate_dataset.py --execute
```
*Expected Output*: Identifies 676 duplicate groups, verifies safeguard message IDs (Maria, Nurse Sarah, Nurse Jennifer, David), and executes chunked deletion across `memory_embeddings` and `messages`. Reduces dataset to **3,348 unique messages** and **3,448 embeddings**.

### 3. Re-Verify Vector Index Scan (`EXPLAIN`) at Deduplicated Scale
```bash
python scripts/verify_cloud_explain.py
```
*Expected Output*: Confirms `vector search` using C-SPANN index (`memory_embeddings@idx_memory_embeddings`) on CockroachDB Cloud at 3,448 embedding scale.

### 4. Run Full Re-Verification Suite
```bash
python scripts/run_step5_verification.py
```
*Expected Output*: Runs flagship conflict question 5x in a row, verifies Nurse Jennifer Lisinopril query (single note with timing typo described), executes full 6-question suite, and confirms final row counts (3,348 messages / 3,448 embeddings).

---

## Milestone 15: Content-Based Message Verification & Dynamic EXPLAIN Scale Audit

### 1. Content-Based Message Verification Queries (psycopg / SQL)
```sql
-- Query 1: Nurse Sarah's flagship note (post-deduplication)
SELECT message_id, created_at, content 
FROM messages 
WHERE conversation_id = '327dff0c-19f4-49db-b1c0-01aa51fc7594' 
  AND caregiver_name ILIKE '%Sarah%' 
  AND (content ILIKE '%pill box%' OR content ILIKE '%pillbox%') 
  AND content ILIKE '%missed%';
-- Result: 1 row found (message_id: f2329738-654b-459a-8e2b-fd54eca45785)

-- Query 2: David's vegetable soup note (post-deduplication)
SELECT message_id, created_at, content 
FROM messages 
WHERE conversation_id = '327dff0c-19f4-49db-b1c0-01aa51fc7594' 
  AND caregiver_name ILIKE '%David%' 
  AND content ILIKE '%vegetable soup%';
-- Result: 1 row found (message_id: 154f35ef-7a46-4659-a888-e252e4fdfdd8)
```

### 2. Run Dynamic EXPLAIN Verification on CockroachDB Cloud
```bash
python scripts/verify_cloud_explain.py
```
*Expected Output*: Dynamically fetches current cloud embedding count (3,448) and verifies vector search plan using C-SPANN index (`memory_embeddings@idx_memory_embeddings`) at exact current scale (`3,448-note scale`).

---

## Milestone 16: Pre-Submission Secret Scan & Git Safety Audit

### 1. Check Untracked Status of Secret-Bearing Files
```bash
# Verify .env was never committed in full git history
git log --all --full-history -- .env

# Verify sensitive state and key files were never committed
git log --all --full-history -- sagemaker_endpoint.txt active_conversation.id *.pem *.key
```
*Expected Output*: Zero output (exit code 0), confirming `.env` and sensitive state files have never been tracked or committed at any point in git history.

### 2. Run Full Git History Secret Pattern Scan (Bash / Grep)
```bash
bash -c "git log --all -p | grep -iE 'AKIA|sk-ant|api[_-]?key|secret|password|COCKROACHDB_MCP_API_KEY|ANTHROPIC_API_KEY|AWS_SECRET'"
```
*Expected Output*: All matches correspond strictly to documentation variable placeholders, config file definitions (`os.getenv`), and comments. Zero plaintext credentials, private keys, or API tokens committed.

### 3. Exhaustive Regex Secret Scan across Full Git History (Python)
```bash
python -c "
import subprocess, re
cmd = ['git', 'log', '--all', '-p']
p = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
pattern = re.compile(r'(AKIA[0-9A-Z]{16}|sk-ant-[a-zA-Z0-9_\-]{20,}|api[_-]?key|secret|password|COCKROACHDB_MCP_API_KEY|ANTHROPIC_API_KEY|AWS_SECRET)', re.IGNORECASE)
matches = [(line.strip()) for line in p.stdout if (line.startswith('+') or line.startswith('-')) and not line.startswith('+++') and not line.startswith('---') and pattern.search(line)]
p.wait()
print(f'Total matched diff lines: {len(matches)}')
"
```
*Expected Output*: Displays count of matched diff lines and confirms all entries are template strings or variable names.

---

## Milestone 17: Production README & MIT License Finalization

### 1. Finalize Documentation and Licensing
```bash
# Verify finalized README and MIT License status
git status
```
*Expected Output*: Displays clean working tree with finalized `README.md` and `LICENSE` committed and pushed to `main`.

