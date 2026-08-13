import sys
import os
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import ACTIVE_CONVERSATION_ID
from app.memory_store import get_connection, add_caregiver_note
from app.coordinator_agent import answer_caregiver_question
from app.web_server import SIMULATION_BATCHES

def run_verification():
    print("=" * 80)
    print("PROMPT C: PRODUCTION-SCALE VERIFICATION & FACT RE-CHECK")
    print("=" * 80)
    
    cid = ACTIVE_CONVERSATION_ID
    print(f"Target Active Conversation ID: {cid}\n")
    
    # -------------------------------------------------------------------------
    # STEP 2: Live simulation against real production dataset (5,884+ notes)
    # -------------------------------------------------------------------------
    print("--- STEP 2: Re-verifying /api/simulate against real production conversation ---")
    print("Connecting to CockroachDB...")
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            print("Querying baseline message and embedding counts...")
            cur.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s;", (cid,))
            count_before = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM memory_embeddings WHERE conversation_id = %s;", (cid,))
            emb_before = cur.fetchone()[0]
            
    print(f"BEFORE SIMULATION: Note Count = {count_before}, Embedding Count = {emb_before}")
    
    print(f"\nSimulating {len(SIMULATION_BATCHES)} live caregiver notes into conversation {cid}...")
    start_sim = time.time()
    inserted_notes = []
    for note in SIMULATION_BATCHES:
        msg_id = add_caregiver_note(
            conversation_id=cid,
            caregiver_name=note["caregiver_name"],
            content=note["content"],
            note_type=note["note_type"]
        )
        inserted_notes.append((msg_id, note["caregiver_name"]))
    sim_time = time.time() - start_sim
    print(f"Simulation completed in {sim_time:.2f}s.")
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s;", (cid,))
            count_after = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM memory_embeddings WHERE conversation_id = %s;", (cid,))
            emb_after = cur.fetchone()[0]

    print(f"AFTER SIMULATION:  Note Count = {count_after}, Embedding Count = {emb_after}")
    print(f"Delta: +{count_after - count_before} notes successfully added.")
    
    question = "Was there any blood pressure medication discrepancy today?"
    print(f"\nSynthesizing follow-up ask response for: '{question}'...")
    start_ask = time.time()
    answer = answer_caregiver_question(conversation_id=cid, question=question, k=5)
    ask_time = time.time() - start_ask
    
    print(f"\n[Synthesized Answer ({ask_time:.2f}s)]:\n{answer}\n")
    
    # -------------------------------------------------------------------------
    # STEP 3: Direct SQL queries on messages table for Fact Re-Check
    # -------------------------------------------------------------------------
    print("--- STEP 3: Direct SQL Query on messages table for Fact Re-Check ---")
    
    print("\n1. Querying messages for Jennifer's blood pressure / timing entries...")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT message_id, caregiver_name, note_type, content, created_at
                FROM messages
                WHERE conversation_id = %s
                  AND (caregiver_name ILIKE '%%Jennifer%%' OR content ILIKE '%%Jennifer%%' OR content ILIKE '%%Lisinopril%%' OR content ILIKE '%%blood pressure%%')
                ORDER BY created_at ASC;
            """, (cid,))
            jennifer_rows = cur.fetchall()

    print(f"Found {len(jennifer_rows)} matching notes for Lisinopril / blood pressure / Jennifer:")
    for idx, r in enumerate(jennifer_rows, 1):
        print(f"  [{idx}] ID: {r[0]} | Caregiver: {r[1]} ({r[2]}) | Time: {r[4]}")
        print(f"      Content: \"{r[3]}\"")
        
    print("\n2. Querying messages for David's vegetable soup / food entries...")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT message_id, caregiver_name, note_type, content, created_at
                FROM messages
                WHERE conversation_id = %s
                  AND (content ILIKE '%%soup%%' OR content ILIKE '%%vegetable%%' OR (caregiver_name ILIKE '%%David%%' AND content ILIKE '%%food%%'))
                ORDER BY created_at ASC;
            """, (cid,))
            soup_rows = cur.fetchall()

    print(f"Found {len(soup_rows)} matching notes for vegetable soup / David's food logs:")
    for idx, r in enumerate(soup_rows, 1):
        print(f"  [{idx}] ID: {r[0]} | Caregiver: {r[1]} ({r[2]}) | Time: {r[4]}")
        print(f"      Content: \"{r[3]}\"")

    print("\n" + "=" * 80)
    print("VERIFICATION RUN COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    run_verification()
