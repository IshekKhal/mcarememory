#!/usr/bin/env bash
set -e

echo "=== Initializing CockroachDB Cluster ==="

# Trigger cluster initialization on roach1
echo "Initializing cluster on roach1..."
docker exec roach1 ./cockroach init --insecure --host=roach1:26257 2>&1 || echo "Cluster initialization already performed or in progress."

echo "Waiting for cluster nodes to become healthy..."
MAX_RETRIES=30
RETRY_COUNT=0

until [ $RETRY_COUNT -ge $MAX_RETRIES ]; do
  NODE_COUNT=$(docker exec roach1 ./cockroach node status --insecure --host=roach1:26257 2>/dev/null | tail -n +2 | wc -l || echo "0")
  if [ "$NODE_COUNT" -ge 3 ]; then
    echo "All 3 nodes are online and healthy!"
    break
  fi
  echo "Waiting for 3 nodes... current count: ${NODE_COUNT} (Attempt $((RETRY_COUNT+1))/$MAX_RETRIES)"
  RETRY_COUNT=$((RETRY_COUNT+1))
  sleep 2
done

if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
  echo "ERROR: Timed out waiting for 3 nodes to join cluster."
  exit 1
fi

echo ""
echo "=== CockroachDB Cluster Ready ==="
echo "Node Status:"
docker exec roach1 ./cockroach node status --insecure --host=roach1:26257

echo ""
echo "DB Console UI available at: http://localhost:8080"
