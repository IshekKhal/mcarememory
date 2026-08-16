import os
import sys
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.web_server import app, get_active_conversation_id
from app.memory_store import get_connection

def run_prompt_u_tests():
    print("=" * 80)
    print("PROMPT U: FULL VERIFICATION SUITE")
    print("=" * 80)

    client = app.test_client()
    cid = get_active_conversation_id()
    print(f"Active Conversation ID: {cid}\n")

    # --------------------------------------------------------------------------
    # STEP 1: Test Global Flask JSON Error Handler (@app.errorhandler(Exception))
    # --------------------------------------------------------------------------
    print("--- 1. Testing Global Flask JSON Error Handler ---")
    
    # 1a. Test 404 Route
    res_404 = client.get("/api/nonexistent_route_test")
    print(f"GET /api/nonexistent_route_test -> HTTP {res_404.status_code}")
    print(f"Content-Type: {res_404.content_type}")
    data_404 = res_404.get_json(silent=True)
    print(f"Response JSON: {data_404}")
    assert res_404.status_code == 404, f"Expected 404, got {res_404.status_code}"
    assert "application/json" in res_404.content_type, f"Expected JSON content-type, got {res_404.content_type}"
    assert data_404 is not None and data_404.get("status") == "error", "Expected JSON status: error"
    print("[PASS] 404 handler returns clean JSON instead of default HTML.\n")

    # 1b. Test 400 Bad Request Payload
    res_400 = client.post("/api/ask", json={})
    print(f"POST /api/ask with empty payload -> HTTP {res_400.status_code}")
    print(f"Content-Type: {res_400.content_type}")
    data_400 = res_400.get_json(silent=True)
    print(f"Response JSON: {data_400}")
    assert res_400.status_code == 400, f"Expected 400, got {res_400.status_code}"
    assert "application/json" in res_400.content_type
    print("[PASS] Bad request validation returns clean JSON.\n")

    # --------------------------------------------------------------------------
    # STEP 2: Test 'Log Caregiver Note' End-to-End Persistence to CockroachDB Cloud
    # --------------------------------------------------------------------------
    print("--- 2. Testing 'Log Caregiver Note' End-to-End Persistence ---")
    
    # 2a. Query baseline row counts
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM messages WHERE conversation_id = %s;", (cid,))
            conv_msgs_before = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM messages;")
            total_msgs_before = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM memory_embeddings;")
            total_embeddings_before = cur.fetchone()[0]

    print(f"[Before] Active Conversation Messages: {conv_msgs_before}")
    print(f"[Before] CockroachDB Total Messages:     {total_msgs_before}")
    print(f"[Before] CockroachDB Total Embeddings:   {total_embeddings_before}")

    # 2b. Submit real note via /api/notes
    note_payload = {
        "caregiver_name": "Physical Therapist Rachel",
        "note_type": "observation",
        "content": "Grandma Chen completed a 20-minute seated leg lift session with steady mobility and no discomfort."
    }
    print(f"\nSubmitting note via POST /api/notes: {note_payload}")
    t0 = time.time()
    res_note = client.post("/api/notes", json=note_payload)
    latency_note = (time.time() - t0) * 1000
    print(f"POST /api/notes -> HTTP {res_note.status_code} in {latency_note:.1f}ms")
    data_note = res_note.get_json()
    print(f"Response: {data_note}")
    assert res_note.status_code == 201, f"Expected 201, got {res_note.status_code}"
    assert data_note.get("status") == "success"
    created_msg_id = data_note.get("message_id")
    print(f"Created Message ID: {created_msg_id}")

    # 2c. Query row counts after insertion
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM messages WHERE conversation_id = %s;", (cid,))
            conv_msgs_after = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM messages;")
            total_msgs_after = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM memory_embeddings;")
            total_embeddings_after = cur.fetchone()[0]
            cur.execute("""
                SELECT message_id, caregiver_name, note_type, content, created_at 
                FROM messages 
                WHERE message_id = %s;
            """, (created_msg_id,))
            inserted_row = cur.fetchone()

    print(f"\n[After]  Active Conversation Messages: {conv_msgs_after} (+{conv_msgs_after - conv_msgs_before})")
    print(f"[After]  CockroachDB Total Messages:     {total_msgs_after} (+{total_msgs_after - total_msgs_before})")
    print(f"[After]  CockroachDB Total Embeddings:   {total_embeddings_after} (+{total_embeddings_after - total_embeddings_before})")

    assert conv_msgs_after == conv_msgs_before + 1, "Active conversation message count did not increase by 1"
    assert total_msgs_after == total_msgs_before + 1, "Total message count did not increase by 1"
    assert total_embeddings_after == total_embeddings_before + 1, "Total embedding count did not increase by 1"
    assert inserted_row is not None, "Inserted note record not found in database"
    print(f"Verified row persisted directly: ID={inserted_row[0]}, Caregiver={inserted_row[1]}, Type={inserted_row[2]}")

    # 2d. Verify note appears in GET /api/notes (Live Memory Stream)
    res_list = client.get("/api/notes")
    assert res_list.status_code == 200
    notes_list_data = res_list.get_json()
    assert notes_list_data.get("count") == conv_msgs_after
    latest_note = notes_list_data.get("notes", [])[0]
    print(f"Verified Live Memory Stream Top Note: '{latest_note.get('content')[:60]}...' by {latest_note.get('caregiver_name')}")
    print("[PASS] 'Log Caregiver Note' end-to-end persistence fully verified on CockroachDB Cloud.\n")

    # --------------------------------------------------------------------------
    # STEP 3: Test Concurrent Rapid Repeated Requests (/api/ask)
    # --------------------------------------------------------------------------
    print("--- 3. Testing Concurrent Rapid Repeated Requests (/api/ask) ---")
    rapid_questions = [
        {"question": "Was her afternoon blood pressure medication given today?", "mode": "sql"},
        {"question": "Was there any blood pressure medication discrepancy today?", "mode": "sql"},
        {"question": "Has Grandma Chen complained of joint pain or mobility issues?", "mode": "sql"},
        {"question": "What is Grandma Chen's current Lisinopril dosage prescription?", "mode": "sql"}
    ]

    print(f"Firing {len(rapid_questions)} concurrent /api/ask calls simultaneously...")
    results = []

    def call_ask(idx, q_item):
        t_start = time.time()
        c = app.test_client()
        resp = c.post("/api/ask", json=q_item)
        elapsed = (time.time() - t_start) * 1000
        return {
            "index": idx,
            "question": q_item["question"],
            "status_code": resp.status_code,
            "content_type": resp.content_type,
            "is_json": "application/json" in resp.content_type,
            "data": resp.get_json(silent=True),
            "latency_ms": elapsed
        }

    t_all_start = time.time()
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(call_ask, i + 1, q) for i, q in enumerate(rapid_questions)]
        for f in as_completed(futures):
            results.append(f.result())
    t_all_elapsed = (time.time() - t_all_start) * 1000

    results.sort(key=lambda x: x["index"])

    print(f"All {len(results)} concurrent requests completed in {t_all_elapsed:.1f}ms total.\n")
    for r in results:
        print(f"  Req #{r['index']}: '{r['question'][:45]}...'")
        print(f"    HTTP Status: {r['status_code']}, Content-Type: {r['content_type']}, Latency: {r['latency_ms']:.1f}ms")
        assert r["status_code"] == 200, f"Req #{r['index']} failed with HTTP {r['status_code']}"
        assert r["is_json"], f"Req #{r['index']} did not return JSON"
        assert r["data"] is not None and r["data"].get("status") == "success", f"Req #{r['index']} missing success status"
        answer_preview = (r["data"].get("answer") or "")[:80].replace("\n", " ")
        print(f"    Answer Preview: \"{answer_preview}...\"")
        print()

    print("[PASS] All concurrent rapid requests succeeded with 100% valid JSON and zero HTML errors.\n")
    print("=" * 80)
    print("ALL PROMPT U VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    run_prompt_u_tests()
