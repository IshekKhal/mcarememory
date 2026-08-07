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





