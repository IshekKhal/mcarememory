#!/usr/bin/env bash
set -e

echo "=== Starting CockroachDB Node-Kill Verification (Full Real Pipeline) ==="

DB_NAME="agent_memory"

# 1. Verify database and schema on roach1
echo "Verifying real schema on database '${DB_NAME}' via roach1..."
docker exec -i roach1 ./cockroach sql --insecure --host=roach1:26257 <<EOF
USE ${DB_NAME};
ALTER TABLE messages ADD COLUMN IF NOT EXISTS resolves_note_ids TEXT[];
EOF

INITIAL_MSG_COUNT=$(docker exec -i roach1 ./cockroach sql --insecure --host=roach1:26257 -e "SELECT count(*) FROM ${DB_NAME}.messages;" --format=csv | tail -n 1)
INITIAL_EMBED_COUNT=$(docker exec -i roach1 ./cockroach sql --insecure --host=roach1:26257 -e "SELECT count(*) FROM ${DB_NAME}.memory_embeddings;" --format=csv | tail -n 1)

echo "Initial dataset status:"
echo "  - messages count: ${INITIAL_MSG_COUNT}"
echo "  - memory_embeddings count: ${INITIAL_EMBED_COUNT}"

# 2. Simulate Node Outage (Kill roach2)
echo ""
echo "=== Killing Node 2 (roach2) ==="
docker kill roach2
echo "roach2 has been killed."

# 3. Test survival (write and read on surviving nodes via roach1)
echo "Testing write to surviving cluster nodes (roach1 & roach3)..."
WRITE_SUCCESS=0
docker exec -i roach1 ./cockroach sql --insecure --host=roach1:26257 <<EOF && WRITE_SUCCESS=1
USE ${DB_NAME};
INSERT INTO messages (conversation_id, role, content, caregiver_name, note_type, resolves_note_ids)
SELECT conversation_id, 'user', 'Shell script node-kill resilience verification note', 'Nurse Sarah', 'observation', ARRAY['test-resolution-id']
FROM conversations LIMIT 1;
EOF

if [ $WRITE_SUCCESS -ne 1 ]; then
  echo "FAIL: Write failed while roach2 was down!"
  exit 1
fi
echo "Post-kill WRITE to real messages table succeeded!"

echo "Testing read from surviving cluster nodes..."
POST_KILL_COUNT=$(docker exec -i roach1 ./cockroach sql --insecure --host=roach1:26257 -e "SELECT count(*) FROM ${DB_NAME}.messages;" --format=csv | tail -n 1)
echo "Post-kill message count: ${POST_KILL_COUNT}"

if [ "${POST_KILL_COUNT}" -le "${INITIAL_MSG_COUNT}" ]; then
  echo "FAIL: Post-kill read failed or missing new message row!"
  exit 1
fi
echo "Post-kill READ succeeded!"

# 4. Restart killed node and verify rejoin
echo ""
echo "=== Restarting Node 2 (roach2) ==="
docker start roach2
echo "roach2 started. Waiting for node to rejoin..."

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
echo "=== RESULT: PASS ==="
echo "All 3 nodes are online and healthy!"
docker exec roach1 ./cockroach node status --insecure --host=roach1:26257
