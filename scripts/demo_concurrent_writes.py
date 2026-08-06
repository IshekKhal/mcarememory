import sys
import os
import time
import threading
from datetime import datetime

# Ensure app module is in path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.memory_store import get_connection, create_conversation, add_caregiver_note
from scripts.demo_seed import SAMPLE_NOTES

CONCURRENT_NOTES = [
    {
        "caregiver_name": "Nurse Sarah",
        "note_type": "medication",
        "content": "Grandma Chen requested her PRN topical pain relief cream for left knee soreness at 2:15 PM. Applied cream and logged her discomfort level at 3/10."
    },
    {
        "caregiver_name": "Maria (Caregiver)",
        "note_type": "appointment",
        "content": "Scheduled physical therapy follow-up session with Dr. Vance for next Thursday at 11:00 AM to focus on her left knee mobility and strengthening."
    },
    {
        "caregiver_name": "David (Son)",
        "note_type": "observation",
        "content": "Grandma Chen had a peaceful afternoon resting on the porch listening to classical radio after her tea, reporting no further knee pain."
    }
]

def load_or_create_conversation_id() -> str:
    id_filepath = os.path.join(os.path.dirname(__file__), "..", "active_conversation.id")
    if os.path.exists(id_filepath):
        with open(id_filepath, "r") as f:
            cid = f.read().strip()
            if cid:
                return cid
    cid = create_conversation(agent_id="multi_caregiver_memory_v1")
    with open(id_filepath, "w") as f:
        f.write(cid)
    return cid

def reset_conversation_notes(conversation_id: str):
    print(f"\n1. Resetting conversation memory to clean state (Target: {conversation_id})...")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM memory_embeddings WHERE conversation_id = %s;", (conversation_id,))
            cur.execute("DELETE FROM messages WHERE conversation_id = %s;", (conversation_id,))
            conn.commit()
    print("   Cleared old messages and embeddings.")
    
    print(f"   Re-seeding original {len(SAMPLE_NOTES)} baseline caregiver notes...")
    for i, note in enumerate(SAMPLE_NOTES, start=1):
        add_caregiver_note(
            conversation_id=conversation_id,
            caregiver_name=note["caregiver_name"],
            content=note["content"],
            note_type=note["note_type"]
        )
    print(f"   ✓ Reset completed successfully: Exactly {len(SAMPLE_NOTES)} base notes in database.")

def run_concurrent_writes(conversation_id: str):
    print(f"\n2. Initiating Concurrent Multi-Caregiver Write Simulation (3 Threads)...")
    print("-" * 75)
    
    results = []
    lock = threading.Lock()
    barrier = threading.Barrier(len(CONCURRENT_NOTES))
    
    def worker_task(idx: int, note_data: dict):
        thread_name = f"CaregiverThread-{idx}"
        caregiver = note_data["caregiver_name"]
        
        # Synchronize all threads so they issue CockroachDB write requests simultaneously
        barrier.wait()
        
        start_time = datetime.now()
        start_str = start_time.strftime("%H:%M:%S.%f")[:-3]
        print(f"[{start_str}] 🚀 [{thread_name}] Caregiver '{caregiver}' STARTING write...")
        
        t0 = time.perf_counter()
        try:
            msg_id = add_caregiver_note(
                conversation_id=conversation_id,
                caregiver_name=caregiver,
                content=note_data["content"],
                note_type=note_data["note_type"]
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            end_time = datetime.now()
            end_str = end_time.strftime("%H:%M:%S.%f")[:-3]
            
            print(f"[{end_str}] ✅ [{thread_name}] Caregiver '{caregiver}' SUCCESS ({elapsed_ms:.1f} ms) | Msg ID: {msg_id}")
            
            with lock:
                results.append({
                    "thread": thread_name,
                    "caregiver": caregiver,
                    "note_type": note_data["note_type"],
                    "start_time": start_str,
                    "end_time": end_str,
                    "elapsed_ms": elapsed_ms,
                    "msg_id": msg_id,
                    "status": "SUCCESS",
                    "error": None
                })
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            end_time = datetime.now()
            end_str = end_time.strftime("%H:%M:%S.%f")[:-3]
            print(f"[{end_str}] ❌ [{thread_name}] Caregiver '{caregiver}' FAILED ({elapsed_ms:.1f} ms) | Error: {e}")
            
            with lock:
                results.append({
                    "thread": thread_name,
                    "caregiver": caregiver,
                    "note_type": note_data["note_type"],
                    "start_time": start_str,
                    "end_time": end_str,
                    "elapsed_ms": elapsed_ms,
                    "msg_id": None,
                    "status": "FAILED",
                    "error": str(e)
                })

    threads = []
    for i, note in enumerate(CONCURRENT_NOTES, start=1):
        t = threading.Thread(target=worker_task, args=(i, note), name=f"CaregiverThread-{i}")
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    print("-" * 75)
    return results

def verify_and_summarize(conversation_id: str, results: list[dict]):
    print("\n3. CockroachDB Data Integrity & Concurrency Audit...")
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s;", (conversation_id,))
            msg_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM memory_embeddings WHERE conversation_id = %s;", (conversation_id,))
            emb_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(DISTINCT memory_id) FROM memory_embeddings WHERE conversation_id = %s;", (conversation_id,))
            unique_emb_count = cur.fetchone()[0]
            
    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    fail_count = sum(1 for r in results if r["status"] == "FAILED")
    
    print("\n" + "=" * 75)
    print("CONCURRENT WRITE EXECUTION SUMMARY")
    print("=" * 75)
    print(f"Conversation ID:         {conversation_id}")
    print(f"Base Notes Seeded:       9")
    print(f"Concurrent Writes Fired: 3")
    print(f"Successful Writes:       {success_count}/3")
    print(f"Failed Writes:           {fail_count}/3")
    print(f"Total Database Messages: {msg_count} (Expected: 12)")
    print(f"Total Vector Embeddings: {emb_count} (Expected: 12)")
    print(f"Unique Embedding IDs:    {unique_emb_count} (Expected: 12)")
    print("-" * 75)
    
    print("Thread Breakdown:")
    for r in results:
        print(f"  • [{r['thread']}] {r['caregiver']} ({r['note_type']}): {r['start_time']} -> {r['end_time']} ({r['elapsed_ms']:.1f} ms) | Status: {r['status']}")
    print("-" * 75)
    
    if success_count == 3 and msg_count == 12 and emb_count == 12 and fail_count == 0:
        print("🎉 SUCCESS: CockroachDB perfectly handled concurrent multi-caregiver writes with ZERO deadlocks, ZERO errors, and ZERO lost writes!")
    else:
        print("⚠️ WARNING: Validation mismatch detected!")
        sys.exit(1)
    print("=" * 75)

def main():
    print("=" * 75)
    print("Milestone 6: Concurrent Multi-Caregiver Write Simulation")
    print("=" * 75)
    
    conversation_id = load_or_create_conversation_id()
    reset_conversation_notes(conversation_id)
    results = run_concurrent_writes(conversation_id)
    verify_and_summarize(conversation_id, results)

if __name__ == "__main__":
    main()
