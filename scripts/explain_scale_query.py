import sys
import os
import argparse
import psycopg

# Ensure app module is in path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import COCKROACH_URL
from app.memory_store import get_connection

def explain_vector_query(conversation_id: str = None, run_analyze: bool = False):
    """
    Executes EXPLAIN on the similarity query used by recall_relevant_notes()
    and variants (no JOIN, no WHERE, <-> vs <=>) to diagnose vector index usage.
    """
    dummy_vector = [0.0] * 1024
    vector_str = f"[{','.join(str(f) for f in dummy_vector)}]"

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Check total note count across entire database
            cur.execute("SELECT COUNT(*) FROM memory_embeddings;")
            total_embeddings = cur.fetchone()[0]

            if not conversation_id:
                cur.execute(
                    """
                    SELECT conversation_id, COUNT(*) as cnt 
                    FROM memory_embeddings 
                    GROUP BY conversation_id 
                    ORDER BY cnt DESC 
                    LIMIT 1;
                    """
                )
                row = cur.fetchone()
                if not row:
                    print("Error: No memory_embeddings found in database. Run demo_scale_test.py or scale_vector_crossover.py first.")
                    sys.exit(1)
                conversation_id = str(row[0])
                note_count = row[1]
                print(f"Total memory_embeddings across DB: {total_embeddings}")
                print(f"Auto-selected Conversation ID with most embeddings ({note_count} notes): {conversation_id}")
            else:
                cur.execute("SELECT COUNT(*) FROM memory_embeddings WHERE conversation_id = %s;", (conversation_id,))
                note_count = cur.fetchone()[0]
                print(f"Total memory_embeddings across DB: {total_embeddings}")
                print(f"Target Conversation ID note count: {note_count} notes ({conversation_id})")

            if run_analyze:
                print("\n--- Running ANALYZE on memory_embeddings and messages tables ---")
                cur.execute("ANALYZE memory_embeddings;")
                cur.execute("ANALYZE messages;")
                conn.commit()
                print("✓ Table statistics re-computed via ANALYZE.")

            print("\n--- 1. SHOW INDEXES FROM memory_embeddings ---")
            cur.execute("SHOW INDEXES FROM memory_embeddings;")
            for r in cur.fetchall():
                print(r)

            queries = [
                (
                    "1. Real App Recall Query (Subquery <-> + JOIN messages + WHERE outer)",
                    """
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
                    """,
                    (vector_str, vector_str, conversation_id)
                ),
                (
                    "2. Scoped Subquery (<-> + WHERE conversation_id inside subquery + JOIN)",
                    """
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
                    """,
                    (vector_str, conversation_id, vector_str)
                ),
                (
                    "3. Direct Vector Search (Pure <-> without JOIN or WHERE)",
                    """
                    EXPLAIN SELECT memory_id, content, (embedding <-> %s::vector) AS distance
                    FROM memory_embeddings
                    ORDER BY embedding <-> %s::vector ASC
                    LIMIT 5;
                    """,
                    (vector_str, vector_str)
                )
            ]

            for label, sql, params in queries:
                print(f"\n================================================================================")
                print(f"EXPLAIN: {label}")
                print("================================================================================")
                try:
                    cur.execute(sql, params)
                    for r in cur.fetchall():
                        print(r[0] if isinstance(r, (list, tuple)) else r)
                except Exception as e:
                    print(f"Error executing EXPLAIN: {e}")
            print("================================================================================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run EXPLAIN on similarity search query in CockroachDB.")
    parser.add_argument("--conversation-id", "--cid", type=str, help="Target conversation ID UUID string.")
    parser.add_argument("--analyze", action="store_true", help="Run ANALYZE before executing EXPLAIN to update CBO stats.")
    args = parser.parse_args()
    
    explain_vector_query(args.conversation_id, run_analyze=args.analyze)

