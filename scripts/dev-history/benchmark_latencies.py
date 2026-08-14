import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
from app.memory_store import generate_embedding, recall_relevant_notes
from app.mcp_client import get_mcp_client

cid = '327dff0c-19f4-49db-b1c0-01aa51fc7594'

print('=== 1. Testing SageMaker Embedding Latency ===')
for i in range(3):
    t0 = time.perf_counter()
    vec = generate_embedding('test question')
    t_emb = (time.perf_counter() - t0) * 1000.0
    print(f'Embedding #{i+1}: {t_emb:.2f} ms (dim={len(vec)})')

print('\n=== 2. Testing MCP Recall Latency (Persistent Singleton) ===')
q1 = 'was her afternoon blood pressure medication given today?'
q2 = 'when is her next doctor appointment scheduled?'
q3 = 'has she seemed confused or anxious lately?'

for label, q in [('MCP Q1', q1), ('MCP Q2', q2), ('MCP Q3', q3)]:
    notes, m = recall_relevant_notes(cid, q, mode='mcp', return_metrics=True)
    print(f"{label}: total_recall_ms={m['total_recall_ms']:.2f}, embed_latency_ms={m['embed_latency_ms']:.2f}, mcp_sql_latency_ms={m['raw_sql_latency_ms']:.2f}, notes={len(notes)}")

print('\n=== 3. Testing Direct SQL Recall Latency ===')
notes, s = recall_relevant_notes(cid, 'what medication did she take today and when?', mode='sql', return_metrics=True)
print(f"SQL Q4: total_recall_ms={s['total_recall_ms']:.2f}, embed_latency_ms={s['embed_latency_ms']:.2f}, raw_sql_latency_ms={s['raw_sql_latency_ms']:.2f}, notes={len(notes)}")

