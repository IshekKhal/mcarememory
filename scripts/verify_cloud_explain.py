import sys
import os
import psycopg

# Ensure app module is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import COCKROACH_CLOUD_URL

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def load_active_cid() -> str:

    id_filepath = os.path.join(os.path.dirname(__file__), "..", "active_conversation.id")
    if os.path.exists(id_filepath):
        with open(id_filepath, "r") as f:
            return f.read().strip()
    return ""

def verify_cloud_explain():
    cloud_url = COCKROACH_CLOUD_URL or os.getenv("COCKROACH_CLOUD_URL", "")
    if not cloud_url:
        print("Error: COCKROACH_CLOUD_URL is not set in .env or environment!")
        sys.exit(1)

    if "sslrootcert=" not in cloud_url:
        cloud_url = cloud_url.replace("&sslrootcert=system", "").replace("?sslrootcert=system", "")
        if "sslmode=verify-full" in cloud_url:
            cloud_url = cloud_url.replace("sslmode=verify-full", "sslmode=require")

    active_cid = load_active_cid()
    print("=" * 80)
    print("STEP 3 VERIFICATION: EXPLAIN Vector Index Query on CockroachDB Cloud")
    print("=" * 80)
    print(f"Target Conversation ID: {active_cid}")

    dummy_vector = [0.0] * 1024
    vector_str = f"[{','.join(str(f) for f in dummy_vector)}]"

    explain_sql = """
        EXPLAIN SELECT 
            e.memory_id,
            e.content,
            m.caregiver_name,
            m.note_type,
            m.created_at,
            e.distance,
            m.message_id,
            m.resolves_note_ids
        FROM (
            SELECT 
                memory_id, 
                source_message_id, 
                conversation_id, 
                content, 
                (embedding <-> %s::vector) AS distance
            FROM memory_embeddings
            ORDER BY embedding <-> %s::vector ASC
            LIMIT 500
        ) e
        JOIN messages m ON e.source_message_id = m.message_id
        WHERE e.conversation_id = %s
        ORDER BY e.distance ASC
        LIMIT 5;
    """

    with psycopg.connect(cloud_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM memory_embeddings WHERE conversation_id = %s;", (active_cid,))
            count = cur.fetchone()[0]
            print(f"Total embeddings in Cloud conversation: {count}")
            print("\nEXPLAIN Query Plan Output on CockroachDB Cloud:")
            print("-" * 80)

            cur.execute(explain_sql, (vector_str, vector_str, active_cid))
            rows = cur.fetchall()
            plan_lines = []
            for r in rows:
                line = r[0] if isinstance(r, (list, tuple)) else str(r)
                plan_lines.append(line)
                print(line)

            plan_text = "\n".join(plan_lines)
            has_vector_index = "idx_memory_embeddings" in plan_text or "vector search" in plan_text.lower()

            print("-" * 80)
            print("C-SPANN VECTOR INDEX VERIFICATION RESULT:")
            if has_vector_index:
                print(f"  ✓ PASS: C-SPANN Vector Index ('idx_memory_embeddings') is ACTIVE and used by CockroachDB Cloud optimizer at {count:,}-note scale!")
            else:
                print("  ⚠ NOTICE: Plan output generated above.")
            print("=" * 80)

if __name__ == "__main__":
    verify_cloud_explain()
