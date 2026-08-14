import time
import os
import sys
import json
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import COCKROACHDB_MCP_API_KEY, ACTIVE_CONVERSATION_ID
from app.memory_store import generate_embedding
from app.mcp_client import CockroachCloudMCPClient

def run_diagnostic():
    print("=" * 80)
    print("MCP LATENCY BREAKDOWN & DIAGNOSTIC PROBE")
    print("=" * 80)

    # 1. Embedding generation timing
    print("\n--- 1. Question Embedding Latency (SageMaker Serverless) ---")
    t0 = time.perf_counter()
    embedding = generate_embedding("was her afternoon blood pressure medication given today?")
    t_embed = (time.perf_counter() - t0) * 1000.0
    print(f"Embedding generated: 1024 dims in {t_embed:.2f} ms")

    # 2. Breakdown of current un-cached CockroachCloudMCPClient
    print("\n--- 2. Un-cached CockroachCloudMCPClient Step Timings ---")
    client = CockroachCloudMCPClient()
    
    t0 = time.perf_counter()
    cid = client.resolve_cluster_id()
    t_resolve = (time.perf_counter() - t0) * 1000.0
    print(f"  • resolve_cluster_id() via list_clusters tool: {t_resolve:.2f} ms")

    t0 = time.perf_counter()
    tools = client.list_tools()
    t_tools = (time.perf_counter() - t0) * 1000.0
    print(f"  • list_tools() via tools/list:                 {t_tools:.2f} ms")

    query_vector_str_mcp = f"[{','.join(f'{f:.6f}' for f in embedding)}]"
    sql_knn_mcp = f"""
        WITH qv AS (SELECT {query_vector_str_mcp}::vector AS v)
        SELECT
            e.memory_id, e.content,
            m.caregiver_name, m.note_type, m.created_at,
            e.distance, m.message_id, m.resolves_note_ids
        FROM (
            SELECT memory_id, source_message_id, conversation_id, content,
                   (embedding <-> (SELECT v FROM qv)) AS distance
            FROM memory_embeddings
            ORDER BY embedding <-> (SELECT v FROM qv) ASC
            LIMIT 500
        ) e
        JOIN messages m ON e.source_message_id = m.message_id
        WHERE e.conversation_id = '{ACTIVE_CONVERSATION_ID}'
        ORDER BY e.distance ASC
        LIMIT 5;
    """

    t0 = time.perf_counter()
    res1 = client.call_tool("select_query", {"database": "defaultdb", "query": sql_knn_mcp})
    t_knn = (time.perf_counter() - t0) * 1000.0
    print(f"  • call_tool('select_query') for KNN query:      {t_knn:.2f} ms")

    t0 = time.perf_counter()
    tools2 = client.list_tools()
    t_tools2 = (time.perf_counter() - t0) * 1000.0
    print(f"  • list_tools() repeated for 2nd query:         {t_tools2:.2f} ms")

    sql_resolutions = f"""
        SELECT 
            e.memory_id, e.content, m.caregiver_name, m.note_type, m.created_at, m.message_id, m.resolves_note_ids
        FROM memory_embeddings e
        JOIN messages m ON e.source_message_id = m.message_id
        WHERE e.conversation_id = '{ACTIVE_CONVERSATION_ID}' AND m.note_type = 'resolution';
    """
    t0 = time.perf_counter()
    res2 = client.call_tool("select_query", {"database": "defaultdb", "query": sql_resolutions})
    t_res = (time.perf_counter() - t0) * 1000.0
    print(f"  • call_tool('select_query') for resolutions:    {t_res:.2f} ms")

    total_old = t_embed + t_resolve + t_tools + t_knn + t_tools2 + t_res
    print(f"\n  Total old un-cached recall latency: {total_old:.2f} ms ({total_old/1000.0:.2f} s)")

    # 3. Optimized session with cached cluster UUID and cached query tool
    print("\n--- 3. Optimized Persistent requests.Session with Cached UUID & Tool ---")
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {COCKROACHDB_MCP_API_KEY}",
        "mcp-cluster-id": cid,
        "User-Agent": "cdbaws-mcp-client/1.0"
    })

    # Test 3 runs
    for run in range(1, 4):
        t0 = time.perf_counter()
        r1 = session.post("https://cockroachlabs.cloud/mcp", json={
            "jsonrpc": "2.0",
            "id": run * 2,
            "method": "tools/call",
            "params": {"name": "select_query", "arguments": {"database": "defaultdb", "query": sql_knn_mcp}}
        }, timeout=30)
        t_opt_knn = (time.perf_counter() - t0) * 1000.0

        t0 = time.perf_counter()
        r2 = session.post("https://cockroachlabs.cloud/mcp", json={
            "jsonrpc": "2.0",
            "id": run * 2 + 1,
            "method": "tools/call",
            "params": {"name": "select_query", "arguments": {"database": "defaultdb", "query": sql_resolutions}}
        }, timeout=30)
        t_opt_res = (time.perf_counter() - t0) * 1000.0

        total_opt = t_embed + t_opt_knn + t_opt_res
        print(f"  [Run {run}] KNN: {t_opt_knn:.2f} ms | Resolutions: {t_opt_res:.2f} ms | Total with Embed: {total_opt:.2f} ms ({total_opt/1000.0:.2f} s)")

    print("=" * 80)

if __name__ == "__main__":
    run_diagnostic()
