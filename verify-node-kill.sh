#!/usr/bin/env bash
set -e

echo "=== Starting CockroachDB Node-Kill Verification ==="

DB_NAME="survival_test"
TABLE_NAME="cluster_verification"

# 1. Setup database and test table
echo "Creating database '${DB_NAME}' and table '${TABLE_NAME}' on roach1..."
docker exec -i roach1 ./cockroach sql --insecure --host=roach1:26257 <<EOF
CREATE DATABASE IF NOT EXISTS ${DB_NAME};
USE ${DB_NAME};
CREATE TABLE IF NOT EXISTS ${TABLE_NAME} (
  id INT8 PRIMARY KEY DEFAULT unique_rowid(),
  note STRING,
  created_at TIMESTAMPTZ DEFAULT now()
);
INSERT INTO ${TABLE_NAME} (note) VALUES ('Initial test record prior to node kill');
EOF

echo "Verifying initial read query..."
INITIAL_ROWS=$(docker exec -i roach1 ./cockroach sql --insecure --host=roach1:26257 -e "SELECT note FROM ${DB_NAME}.${TABLE_NAME};" --format=csv | grep -v "note" | wc -l)
echo "Initial row count: ${INITIAL_ROWS}"

if [ "${INITIAL_ROWS}" -lt 1 ]; then
  echo "FAIL: Expected initial rows, but none found."
  exit 1
fi
echo "Initial write and read verified successfully."

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
INSERT INTO ${TABLE_NAME} (note) VALUES ('Post-kill test record while roach2 is down');
EOF

if [ $WRITE_SUCCESS -ne 1 ]; then
  echo "FAIL: Write failed while roach2 was down!"
  exit 1
fi
echo "Post-kill WRITE succeeded!"

echo "Testing read from surviving cluster nodes..."
POST_KILL_COUNT=$(docker exec -i roach1 ./cockroach sql --insecure --host=roach1:26257 -e "SELECT note FROM ${DB_NAME}.${TABLE_NAME};" --format=csv | grep -v "note" | wc -l)
echo "Post-kill row count: ${POST_KILL_COUNT}"

if [ "${POST_KILL_COUNT}" -le "${INITIAL_ROWS}" ]; then
  echo "FAIL: Post-kill read failed or missing new row!"
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
