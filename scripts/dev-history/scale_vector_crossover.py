import sys
import os
import time
import random
import argparse
from datetime import datetime, timedelta

# Ensure app module is in path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.memory_store import create_conversation, recall_relevant_notes, get_connection
from app.embeddings import generate_embeddings_batch, generate_embedding

CAREGIVERS = [
    "Nurse Sarah", "Nurse David", "Maria (Caregiver)", "Dr. Robert Chen",
    "Lisa (Daughter)", "Alex (Physical Therapist)", "Nurse Jennifer", "Mark (Caregiver)"
]

CATEGORIES = ["medication", "observation", "appointment", "general"]

MEDICATION_TEMPLATES = [
    "Administered morning {med} {dose} at {time} with breakfast.",
    "Checked pill dispenser for {med} {dose}; compartment was empty, confirmed taken at {time}.",
    "Assisted Grandma Chen with taking her afternoon {med} {dose} alongside a full glass of water.",
    "Logged evening administration of {med} {dose} at {time}.",
    "Refilled weekly pill container with {med} {dose} for the upcoming week.",
    "Grandma Chen requested her {med} {dose} early at {time} after experiencing mild discomfort."
]

MEDICATIONS = [
    ("Amlodipine", "5mg"), ("Metformin", "500mg"), ("Donepezil", "10mg"),
    ("Lisinopril", "10mg"), ("Atorvastatin", "20mg"), ("Calcium Supplement", "600mg"),
    ("Vitamin D3", "1000 IU"), ("Eye Drops (Artificial Tears)", "1 drop"), ("Aspirin", "81mg")
]

OBSERVATION_TEMPLATES = [
    "Checked vital signs at {time}: Blood pressure {bp}, heart rate {hr} bpm, oxygen saturation {spo2}%.",
    "Grandma Chen enjoyed a 30-minute walk in the garden today at {time}. Mood was upbeat and cheerful.",
    "Noticed mild stiffness in left knee during afternoon walk. Applied warm compress at {time}.",
    "Grandma Chen completed a 100-piece jigsaw puzzle in the living room. Excellent focus and cognitive engagement.",
    "Ate a complete meal for lunch (chicken soup and steamed vegetables). Hydration is good ({water}ml water consumed).",
    "Took a 45-minute afternoon nap between 2:00 PM and 2:45 PM. Slept soundly.",
    "Listened to classical music on the radio after tea time. Seemed relaxed and peaceful."
]

APPOINTMENT_TEMPLATES = [
    "Tele-health checkup with Dr. {doctor} completed at {time}. Vital trends reviewed and approved.",
    "Physical therapy session with Alex completed. Worked on balance and gait exercises for 40 minutes.",
    "Scheduled upcoming {specialty} consultation for next {day} at {app_time}.",
    "Routine blood draw performed by home health phlebotomist at {time}. Samples sent to lab.",
    "Dentist hygiene checkup completed at dental clinic. Teeth and gums look healthy."
]

def generate_synthetic_notes(target_count: int = 5000) -> list[dict]:
    """Generates varied synthetic caregiver notes."""
    notes = []
    for i in range(target_count):
        caregiver = random.choice(CAREGIVERS)
        category = random.choice(CATEGORIES)
        
        if category == "medication":
            med, dose = random.choice(MEDICATIONS)
            t_str = f"{random.randint(7, 20)}:00 PM" if random.choice([True, False]) else f"{random.randint(7, 11)}:00 AM"
            content = random.choice(MEDICATION_TEMPLATES).format(med=med, dose=dose, time=t_str)
        elif category == "observation":
            t_str = f"{random.randint(8, 19)}:30 PM"
            bp = f"{random.randint(110, 138)}/{random.randint(70, 88)}"
            hr = random.randint(64, 82)
            spo2 = random.randint(96, 99)
            water = random.randint(500, 1500)
            content = random.choice(OBSERVATION_TEMPLATES).format(time=t_str, bp=bp, hr=hr, spo2=spo2, water=water)
        elif category == "appointment":
            t_str = f"{random.randint(9, 16)}:00 AM"
            doc = random.choice(["Smith", "Patel", "Chen", "Johnson", "Williams"])
            specialty = random.choice(["Cardiology", "Podiatry", "Neurology", "General Wellness"])
            day = random.choice(["Monday", "Wednesday", "Friday"])
            app_time = f"{random.randint(9, 15)}:00 AM"
            content = random.choice(APPOINTMENT_TEMPLATES).format(doctor=doc, time=t_str, specialty=specialty, day=day, app_time=app_time)
        else:
            content = f"General care routine log #{i+1} by {caregiver}: Assisted Grandma Chen with routine daily activities."

        notes.append({
            "caregiver_name": caregiver,
            "note_type": category,
            "content": content
        })
    return notes


def seed_scale_conversation(target_notes: int = 5000, batch_size: int = 50) -> str:
    """Creates a dedicated scale conversation and seeds target_notes caregiver notes efficiently."""
    test_cid = create_conversation(agent_id=f"scale_crossover_{target_notes}_notes")
    print(f"\n[1/4] Created SEPARATE Scale Test Conversation ID: {test_cid}")
    print(f"      (Target scale: {target_notes} notes. 'Grandma Chen's Care Record' remains untouched)")

    print(f"\n[2/4] Seeding {target_notes} realistic notes via SageMaker batch embeddings & transaction batching...")
    raw_notes = generate_synthetic_notes(target_notes)
    
    start_time = time.perf_counter()
    inserted_count = 0

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS resolves_note_ids TEXT[];")
            conn.commit()

            for chunk_start in range(0, target_notes, batch_size):
                chunk_notes = raw_notes[chunk_start:chunk_start + batch_size]
                contents = [n["content"] for n in chunk_notes]
                
                # Batch generate embeddings via SageMaker
                embeddings = generate_embeddings_batch(contents, batch_size=32)

                # Batch insert into messages and memory_embeddings
                for note, emb in zip(chunk_notes, embeddings):
                    emb_str = f"[{','.join(str(f) for f in emb)}]"
                    cur.execute(
                        """
                        INSERT INTO messages (conversation_id, role, content, caregiver_name, note_type)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING message_id;
                        """,
                        (test_cid, "user", note["content"], note["caregiver_name"], note["note_type"])
                    )
                    msg_id = str(cur.fetchone()[0])
                    
                    cur.execute(
                        """
                        INSERT INTO memory_embeddings (conversation_id, source_message_id, content, embedding)
                        VALUES (%s, %s, %s, %s::vector);
                        """,
                        (test_cid, msg_id, note["content"], emb_str)
                    )
                conn.commit()
                inserted_count += len(chunk_notes)

                if inserted_count % 500 == 0 or inserted_count == target_notes:
                    elapsed = time.perf_counter() - start_time
                    print(f"      Progress: {inserted_count}/{target_notes} notes ingested into CockroachDB ({elapsed:.1f}s elapsed)")

    total_time = time.perf_counter() - start_time
    print(f"   ✓ Ingestion complete: {target_notes} notes stored with 1024-dim embeddings in {total_time:.2f}s.")
    return test_cid


def analyze_and_explain(conversation_id: str):
    """Runs ANALYZE table stats and executes EXPLAIN on production vector queries."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM memory_embeddings;")
            total_db_embeddings = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM memory_embeddings WHERE conversation_id = %s;", (conversation_id,))
            target_cid_embeddings = cur.fetchone()[0]

            print("\n" + "=" * 85)
            print(f"MILESTONE 12: VECTOR INDEX CROSSOVER ANALYSIS AT {target_cid_embeddings}-NOTE SCALE")
            print(f"(Total embeddings across all conversations in DB: {total_db_embeddings})")
            print("=" * 85)

            # 1. EXPLAIN BEFORE Explicit ANALYZE
            dummy_vector = [0.0] * 1024
            vector_str = f"[{','.join(str(f) for f in dummy_vector)}]"

            prod_sql = """
                EXPLAIN SELECT e.memory_id, e.content, m.caregiver_name, m.note_type, m.created_at, e.distance, m.message_id, m.resolves_note_ids
                FROM (
                    SELECT memory_id, source_message_id, conversation_id, content, (embedding <-> %s::vector) AS distance
                    FROM memory_embeddings
                    ORDER BY embedding <-> %s::vector ASC
                    LIMIT 500
                ) e
                JOIN messages m ON e.source_message_id = m.message_id
                WHERE e.conversation_id = %s
                ORDER BY e.distance ASC
                LIMIT 5;
            """
            
            scoped_sql = """
                EXPLAIN SELECT e.memory_id, e.content, m.caregiver_name, m.note_type, m.created_at, e.distance, m.message_id, m.resolves_note_ids
                FROM (
                    SELECT memory_id, source_message_id, conversation_id, content, (embedding <-> %s::vector) AS distance
                    FROM memory_embeddings
                    WHERE conversation_id = %s
                    ORDER BY embedding <-> %s::vector ASC
                    LIMIT 500
                ) e
                JOIN messages m ON e.source_message_id = m.message_id
                ORDER BY e.distance ASC
                LIMIT 5;
            """

            direct_sql = """
                EXPLAIN SELECT memory_id, content, (embedding <-> %s::vector) AS distance
                FROM memory_embeddings
                ORDER BY embedding <-> %s::vector ASC
                LIMIT 5;
            """

            print("\n[3/4] EXPLAIN Plan BEFORE Explicit ANALYZE (checking for stale stats impact):")
            print("-" * 80)
            cur.execute(prod_sql, (vector_str, vector_str, conversation_id))
            before_rows = cur.fetchall()
            for r in before_rows:
                print(r[0] if isinstance(r, (list, tuple)) else r)

            # 2. Run Explicit ANALYZE
            print("\n--> Executing ANALYZE memory_embeddings; and ANALYZE messages; ...")
            cur.execute("ANALYZE memory_embeddings;")
            cur.execute("ANALYZE messages;")
            conn.commit()
            print("✓ Table statistics successfully updated via ANALYZE.")

            # 3. EXPLAIN AFTER Explicit ANALYZE
            print("\n[4/4] EXPLAIN Plans AFTER Explicit ANALYZE:")
            
            queries = [
                ("A. Real App Recall Query (Subquery <-> + JOIN messages + WHERE outer)", prod_sql, (vector_str, vector_str, conversation_id)),
                ("B. Scoped Subquery (<-> + WHERE conversation_id inside subquery + JOIN)", scoped_sql, (vector_str, conversation_id, vector_str)),
                ("C. Direct Vector Search (Pure <-> without JOIN or WHERE)", direct_sql, (vector_str, vector_str))
            ]

            plan_outcomes = {}
            for label, sql, params in queries:
                print(f"\n" + "=" * 80)
                print(f"EXPLAIN Plan: {label}")
                print("=" * 80)
                cur.execute(sql, params)
                rows = cur.fetchall()
                plan_text = "\n".join([r[0] if isinstance(r, (list, tuple)) else str(r) for r in rows])
                print(plan_text)
                
                has_vector_search = "vector search" in plan_text.lower() or "idx_memory_embeddings" in plan_text
                plan_outcomes[label] = "VECTOR SEARCH (idx_memory_embeddings)" if has_vector_search else "FULL SCAN"

            # Benchmark Recall Query Performance
            print("\n" + "=" * 85)
            print("RAW SQL RECALL QUERY BENCHMARK AT 5,000-NOTE SCALE")
            print("=" * 85)
            sample_question = "What are her latest recorded vital signs?"
            _, metrics = recall_relevant_notes(conversation_id=conversation_id, question=sample_question, k=5, return_metrics=True)
            
            print(f"Question: \"{sample_question}\"")
            print(f"  • Question Embedding Latency (SageMaker BGE): {metrics['embed_latency_ms']:.2f} ms")
            print(f"  • CockroachDB Raw pgvector SQL Query Latency: {metrics['raw_sql_latency_ms']:.2f} ms")
            print(f"  • Total Memory Recall Latency:               {metrics['total_recall_ms']:.2f} ms")

            print("\n" + "=" * 85)
            print("MILESTONE 12 FINDINGS SUMMARY")
            print("=" * 85)
            for label, status in plan_outcomes.items():
                print(f"  • {label:<60} : {status}")
            print("=" * 85)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Milestone 12 scale crossover investigation in CockroachDB.")
    parser.add_argument("--target-notes", type=int, default=5000, help="Number of notes to seed (default: 5000).")
    parser.add_argument("--conversation-id", "--cid", type=str, help="Existing target conversation ID if skipping seed.")
    parser.add_argument("--skip-seed", action="store_true", help="Skip seeding and run ANALYZE + EXPLAIN on existing data.")
    args = parser.parse_args()

    if args.skip_seed and args.conversation_id:
        analyze_and_explain(args.conversation_id)
    elif args.skip_seed:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT conversation_id, COUNT(*) as cnt FROM memory_embeddings GROUP BY conversation_id ORDER BY cnt DESC LIMIT 1;")
                row = cur.fetchone()
                if not row:
                    print("Error: No memory_embeddings found to analyze.")
                    sys.exit(1)
                analyze_and_explain(str(row[0]))
    else:
        cid = seed_scale_conversation(target_notes=args.target_notes)
        analyze_and_explain(cid)
