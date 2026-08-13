import sys
import os
import time
import psycopg

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import ACTIVE_CONVERSATION_ID
from app.memory_store import get_connection

# Exact IDs of the 4 test notes added during Prompt C /api/simulate test run
TEST_NOTE_IDS = [
    "92e45682-8409-421d-8189-577b2dc8a4c3",  # Physical Therapist Rachel (observation)
    "9e859862-3d76-428d-b11f-7a7acc44e5c9",  # Caregiver Mark (medication)
    "11bcc4a8-0ef2-48f5-a48e-b094b04aaf40",  # Dr. Evelyn Vance (medication)
    "c942b662-4ddb-45af-8d5d-0d3cae19a8f0",  # Nurse David (observation)
]

def cleanup():
    cid = ACTIVE_CONVERSATION_ID
    print("=" * 80)
    print(f"STEP 1: CLEANUP TEST NOTES FROM DEMO CONVERSATION {cid}")
    print("=" * 80)
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Baseline Counts
            cur.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s;", (cid,))
            msg_before = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM memory_embeddings WHERE conversation_id = %s;", (cid,))
            emb_before = cur.fetchone()[0]
            
            print(f"\nBEFORE CLEANUP:")
            print(f"  Messages Count: {msg_before}")
            print(f"  Embeddings Count: {emb_before}")
            
            print(f"\nExact 4 Message IDs to be deleted:")
            for note_id in TEST_NOTE_IDS:
                cur.execute("SELECT caregiver_name, note_type, content FROM messages WHERE message_id = %s;", (note_id,))
                row = cur.fetchone()
                if row:
                    print(f"  - [{note_id}] {row[0]} ({row[1]}): \"{row[2][:60]}...\"")
                else:
                    print(f"  - [{note_id}] (NOT FOUND in database)")
                    
            print("\nExecuting deletion of specific 4 test notes and matching embeddings...")
            
            deleted_embs = 0
            deleted_msgs = 0
            
            # Retry loop for CockroachDB transaction serialization
            for attempt in range(5):
                try:
                    cur.execute(
                        "DELETE FROM memory_embeddings WHERE source_message_id = ANY(%s::uuid[]);",
                        (TEST_NOTE_IDS,)
                    )
                    deleted_embs = cur.rowcount
                    
                    cur.execute(
                        "DELETE FROM messages WHERE message_id = ANY(%s::uuid[]);",
                        (TEST_NOTE_IDS,)
                    )
                    deleted_msgs = cur.rowcount
                    
                    conn.commit()
                    print(f"Deletion succeeded on attempt {attempt + 1}.")
                    break
                except Exception as e:
                    conn.rollback()
                    if attempt < 4 and ("restart transaction" in str(e) or "SerializationFailure" in str(type(e))):
                        print(f"Attempt {attempt + 1} serialization conflict: {e}. Retrying in {(attempt + 1) * 0.5}s...")
                        time.sleep((attempt + 1) * 0.5)
                    else:
                        raise e
            
            # 2. Counts after cleanup
            cur.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s;", (cid,))
            msg_after = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM memory_embeddings WHERE conversation_id = %s;", (cid,))
            emb_after = cur.fetchone()[0]
            
            print(f"\nAFTER CLEANUP:")
            print(f"  Deleted {deleted_msgs} message rows and {deleted_embs} embedding rows.")
            print(f"  Messages Count: {msg_after} (Expected: 5884)")
            print(f"  Embeddings Count: {emb_after} (Expected: 5984)")
            
            if msg_after == 5884 and emb_after == 5984:
                print("\n[SUCCESS] Note count and embedding count successfully restored to baseline!")
            else:
                print(f"\n[WARNING] Count mismatch: expected (5884, 5984), got ({msg_after}, {emb_after})")
                
    print("=" * 80)

if __name__ == "__main__":
    cleanup()
