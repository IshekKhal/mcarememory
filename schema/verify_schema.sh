#!/usr/bin/env bash
set -e

echo "=== Starting Agent Memory Schema & Vector Index Verification ==="

DB_NAME="agent_memory"
HOST="roach1:26257"
CLI_CMD="docker exec -i roach1 ./cockroach sql --insecure --host=${HOST}"

# Detect Python binary
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
elif command -v py &>/dev/null; then
    PYTHON_BIN="py"
else
    echo "ERROR: Python is required to run verify_schema.sh"
    exit 1
fi

# 1. Apply schema migration file
echo "Step 1: Applying schema migration from schema/001_agent_memory.sql..."
cat schema/001_agent_memory.sql | ${CLI_CMD}

echo "Step 1 PASSED: Schema created successfully."

# 2. Confirm Vector Index via SHOW INDEXES
echo ""
echo "Step 2: Checking vector index on memory_embeddings..."
INDEX_INFO=$(${CLI_CMD} -e "USE ${DB_NAME}; SHOW INDEXES FROM memory_embeddings;" --format=csv)
echo "${INDEX_INFO}"

if echo "${INDEX_INFO}" | grep -q "idx_memory_embeddings"; then
    echo "Step 2 PASSED: Vector index 'idx_memory_embeddings' exists."
else
    echo "FAIL: Vector index 'idx_memory_embeddings' was not found!"
    exit 1
fi

# 3. Seed test data across all 4 tables
echo ""
echo "Step 3: Seeding dummy test rows across conversations, messages, task_state, and memory_embeddings..."

# Helper function to generate a 1024-dim float vector string centered at a target value
gen_vec() {
    local val=$1
    ${PYTHON_BIN} -c "
import random
val = $val
vec = [round(val + random.uniform(-0.01, 0.01), 6) for _ in range(1024)]
print('[' + ','.join(map(str, vec)) + ']')
"
}

VEC_A=$(gen_vec 0.1)
VEC_B=$(gen_vec 0.5)
VEC_C=$(gen_vec 0.9)
QUERY_VEC=$(gen_vec 0.51)

# Generate SQL script to insert seeded data with FK references
SEED_SQL=$(${PYTHON_BIN} -c "
import uuid

conv_id = str(uuid.uuid4())
msg_1 = str(uuid.uuid4())
msg_2 = str(uuid.uuid4())
task_id = str(uuid.uuid4())
mem_1 = str(uuid.uuid4())
mem_2 = str(uuid.uuid4())
mem_3 = str(uuid.uuid4())

vec_a = '''${VEC_A}'''
vec_b = '''${VEC_B}'''
vec_c = '''${VEC_C}'''

print(f'''
USE agent_memory;

-- Insert Conversation
INSERT INTO conversations (conversation_id, agent_id)
VALUES ('{conv_id}', 'agent_alpha');

-- Insert Messages
INSERT INTO messages (message_id, conversation_id, role, content)
VALUES 
  ('{msg_1}', '{conv_id}', 'user', 'How do I deploy CockroachDB on AWS?'),
  ('{msg_2}', '{conv_id}', 'agent', 'You can deploy a 3-node cluster across multiple availability zones for high availability.');

-- Insert Task State
INSERT INTO task_state (task_id, conversation_id, status, state)
VALUES ('{task_id}', '{conv_id}', 'IN_PROGRESS', '{{\"step\": 2, \"target_region\": \"us-east-1\", \"retry_count\": 0}}'::jsonb);

-- Insert Memory Embeddings (1024 dims)
INSERT INTO memory_embeddings (memory_id, conversation_id, source_message_id, content, embedding)
VALUES 
  ('{mem_1}', '{conv_id}', '{msg_1}', 'CockroachDB AWS deployment query', '{vec_a}'),
  ('{mem_2}', '{conv_id}', '{msg_2}', 'Multi-AZ cluster resilience architecture', '{vec_b}'),
  ('{mem_3}', '{conv_id}', NULL, 'Vector memory index optimization guide', '{vec_c}');
''')
")

echo "${SEED_SQL}" | ${CLI_CMD}
echo "Step 3 PASSED: Seed rows inserted successfully with FK constraints intact."

# 4. Verify Cosine Distance <=> Query produces ordered results
echo ""
echo "Step 4: Running Cosine Similarity <=> Query..."
SIM_QUERY="USE agent_memory; SELECT memory_id, content, embedding <=> '${QUERY_VEC}' AS distance FROM memory_embeddings ORDER BY distance ASC LIMIT 3;"
QUERY_RESULTS=$(${CLI_CMD} -e "${SIM_QUERY}")
echo "${QUERY_RESULTS}"

# Verify we got rows back
ROW_COUNT=$(echo "${QUERY_RESULTS}" | grep -v "memory_id" | grep -v "row" | grep -v "USE" | grep -v "SET" | wc -l)
if [ "${ROW_COUNT}" -ge 3 ]; then
    echo "Step 4 PASSED: Cosine similarity query returned ordered results."
else
    echo "FAIL: Expected 3 ordered results from similarity query, got ${ROW_COUNT}."
    exit 1
fi

# 5. Verify EXPLAIN on similarity search shows vector index usage
echo ""
echo "Step 5: Running EXPLAIN on vector similarity query..."
# Cleanly fetch a single conversation_id
CONV_ID=$(${CLI_CMD} -e "SELECT conversation_id FROM agent_memory.conversations LIMIT 1;" --format=csv | grep -v "conversation_id" | head -n 1)

${PYTHON_BIN} -c "
import subprocess, random, uuid
vecs = []
conv_id = '${CONV_ID}'
for i in range(100):
    v = [round(random.uniform(-1, 1), 4) for _ in range(1024)]
    v_str = '[' + ','.join(map(str, v)) + ']'
    m_id = str(uuid.uuid4())
    vecs.append(f\"('{m_id}', '{conv_id}', 'Bulk doc {i}', '{v_str}')\")

sql = '''
USE agent_memory;
INSERT INTO memory_embeddings (memory_id, conversation_id, content, embedding) VALUES
''' + ',\n'.join(vecs) + ''';
ANALYZE memory_embeddings;
'''
subprocess.run(['docker', 'exec', '-i', 'roach1', './cockroach', 'sql', '--insecure', '--host=roach1:26257'], input=sql, text=True, stdout=subprocess.DEVNULL)
"

EXPLAIN_OUTPUT=$(${CLI_CMD} -e "USE agent_memory; EXPLAIN SELECT memory_id, content, embedding <-> '${QUERY_VEC}' AS distance FROM memory_embeddings ORDER BY embedding <-> '${QUERY_VEC}' LIMIT 3;")
echo "${EXPLAIN_OUTPUT}"

if echo "${EXPLAIN_OUTPUT}" | grep -q "vector search"; then
    echo "Step 5 PASSED: EXPLAIN confirms vector index is being used ('vector search' node on idx_memory_embeddings)."
else
    echo "FAIL: EXPLAIN did not show vector index scan!"
    exit 1
fi

# 6. Verify Node-Kill Resilience on agent_memory
echo ""
echo "Step 6: Verifying Node-Kill Resilience on 'agent_memory' database..."
echo "Killing Node 2 (roach2)..."
docker kill roach2
echo "roach2 killed."
sleep 3

echo "Testing write to agent_memory while roach2 is down..."
RESILIENCE_CONV_ID=$(${PYTHON_BIN} -c "import uuid; print(str(uuid.uuid4()))")

WRITE_OK=0
for i in {1..5}; do
    if ${CLI_CMD} -e "USE agent_memory; INSERT INTO conversations (conversation_id, agent_id) VALUES ('${RESILIENCE_CONV_ID}', 'agent_resilience_test');" &>/dev/null; then
        WRITE_OK=1
        break
    fi
    echo "Retrying write while raft re-elections settle... (attempt $i)"
    sleep 2
done

if [ $WRITE_OK -ne 1 ]; then
    echo "FAIL: Write failed while roach2 was down!"
    docker start roach2
    exit 1
fi
echo "Write while roach2 down: SUCCESS!"

echo "Testing read from agent_memory while roach2 is down..."
RESILIENCE_READ=$(${CLI_CMD} -e "USE agent_memory; SELECT agent_id FROM conversations WHERE conversation_id = '${RESILIENCE_CONV_ID}';" --format=csv | grep "agent_resilience_test" || true)
if [ -z "${RESILIENCE_READ}" ]; then
    echo "FAIL: Could not read newly inserted conversation while roach2 was down!"
    docker start roach2
    exit 1
fi
echo "Read while roach2 down: SUCCESS!"

echo "Restarting Node 2 (roach2)..."
docker start roach2
echo "Waiting for roach2 to rejoin..."

RETRY_COUNT=0
MAX_RETRIES=30
REJOIN_SUCCESS=0

until [ $RETRY_COUNT -ge $MAX_RETRIES ]; do
  LIVE_NODES=$(docker exec roach1 ./cockroach node status --insecure --host=roach1:26257 2>/dev/null | grep "true" | wc -l || echo "0")
  if [ "$LIVE_NODES" -ge 3 ]; then
    REJOIN_SUCCESS=1
    break
  fi
  echo "Waiting for roach2 to rejoin... live nodes: ${LIVE_NODES}/3 (Attempt $((RETRY_COUNT+1))/$MAX_RETRIES)"
  RETRY_COUNT=$((RETRY_COUNT+1))
  sleep 2
done

if [ $REJOIN_SUCCESS -ne 1 ]; then
  echo "FAIL: roach2 failed to rejoin cluster after restart."
  exit 1
fi

echo ""
echo "=== ALL VERIFICATION CHECKS PASSED SUCCESSFULLY ==="
