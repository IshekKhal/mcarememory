import sys
import os
import psycopg

# Ensure app module is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import COCKROACH_URL, COCKROACH_CLOUD_URL

def load_active_cid() -> str:
    id_filepath = os.path.join(os.path.dirname(__file__), "..", "active_conversation.id")
    if os.path.exists(id_filepath):
        with open(id_filepath, "r") as f:
            return f.read().strip()
    return ""

def get_cloud_connection():
    cloud_url = COCKROACH_CLOUD_URL or os.getenv("COCKROACH_CLOUD_URL", "")
    if not cloud_url:
        print("Error: COCKROACH_CLOUD_URL is not set in .env or environment!")
        print("Please ensure COCKROACH_CLOUD_URL=<your-cockroach-cloud-connection-string> is present in .env")
        sys.exit(1)

    # Clean up sslrootcert=system if appended previously
    cloud_url = cloud_url.replace("&sslrootcert=system", "").replace("?sslrootcert=system", "")

    # Replace sslmode=verify-full with sslmode=require if no local root cert path is given
    if "sslmode=verify-full" in cloud_url and "sslrootcert=" not in cloud_url:
        cloud_url = cloud_url.replace("sslmode=verify-full", "sslmode=require")

    return psycopg.connect(cloud_url)

def get_local_connection():
    return psycopg.connect(COCKROACH_URL)

def apply_cloud_schema(cloud_conn):
    print("\n[1/3] Applying database schema & vector index to CockroachDB Cloud...")
    with cloud_conn.cursor() as cur:

        # Conversations
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                agent_id STRING NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)

        # Messages
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                conversation_id UUID NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                role STRING NOT NULL CHECK (role IN ('user', 'agent', 'system')),
                content TEXT NOT NULL,
                caregiver_name STRING,
                note_type STRING DEFAULT 'general',
                resolves_note_ids TEXT[],
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)

        # Task state
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_state (
                task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                conversation_id UUID NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                status STRING NOT NULL,
                state JSONB NOT NULL DEFAULT '{}'::jsonb,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)

        # Memory embeddings
        cur.execute("""
            CREATE TABLE IF NOT EXISTS memory_embeddings (
                memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                conversation_id UUID NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                source_message_id UUID REFERENCES messages(message_id) ON DELETE SET NULL,
                content TEXT NOT NULL,
                embedding VECTOR(1024) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)

        # Vector index
        cur.execute("CREATE VECTOR INDEX IF NOT EXISTS idx_memory_embeddings ON memory_embeddings(embedding);")
        cloud_conn.commit()
        print("  ✓ Cloud schema and C-SPANN vector index created successfully.")

def migrate_data():
    active_cid = load_active_cid()
    if not active_cid:
        print("Error: No active conversation ID found in active_conversation.id")
        sys.exit(1)

    print("=" * 80)
    print("STEP 3: Migrate Consolidated Dataset to CockroachDB Cloud")
    print("=" * 80)
    print(f"Target Conversation ID: {active_cid}")

    local_conn = get_local_connection()
    cloud_conn = get_cloud_connection()

    apply_cloud_schema(cloud_conn)

    print("\n[2/3] Exporting local records & importing into CockroachDB Cloud...")
    with local_conn.cursor() as l_cur:
        # 1. Fetch conversations
        l_cur.execute("SELECT conversation_id, agent_id, created_at FROM conversations WHERE conversation_id = %s;", (active_cid,))
        conv_rows = l_cur.fetchall()

        # 2. Fetch messages
        l_cur.execute("""
            SELECT message_id, conversation_id, role, content, caregiver_name, note_type, resolves_note_ids, created_at 
            FROM messages 
            WHERE conversation_id = %s;
        """, (active_cid,))
        msg_rows = l_cur.fetchall()

        # 3. Fetch memory embeddings
        l_cur.execute("""
            SELECT memory_id, conversation_id, source_message_id, content, embedding::text, created_at 
            FROM memory_embeddings 
            WHERE conversation_id = %s;
        """, (active_cid,))
        emb_rows = l_cur.fetchall()

        print(f"  • Local Dataset fetched: {len(conv_rows)} conversation, {len(msg_rows)} messages, {len(emb_rows)} embeddings.")

    with cloud_conn.cursor() as c_cur:
        # ON CONFLICT DO NOTHING handles idempotency and allows clean resumption
        pass

        # Insert conversation
        for r in conv_rows:
            c_cur.execute("""
                INSERT INTO conversations (conversation_id, agent_id, created_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (conversation_id) DO NOTHING;
            """, r)
        cloud_conn.commit()

        # Insert messages in batches
        batch_size = 500
        print(f"  • Migrating {len(msg_rows)} messages to Cloud...")
        for i in range(0, len(msg_rows), batch_size):
            batch = msg_rows[i:i + batch_size]
            for r in batch:
                c_cur.execute("""
                    INSERT INTO messages (message_id, conversation_id, role, content, caregiver_name, note_type, resolves_note_ids, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (message_id) DO NOTHING;
                """, r)
            cloud_conn.commit()
            print(f"      Progress: {min(i + batch_size, len(msg_rows))}/{len(msg_rows)} messages imported to Cloud")

        # Insert memory embeddings in batches of 200 with CockroachDB transaction retry handling
        emb_batch_size = 200
        print(f"  • Migrating {len(emb_rows)} memory embeddings (with 1024-dim vectors preserved) to Cloud...")
        for i in range(0, len(emb_rows), emb_batch_size):
            batch = emb_rows[i:i + emb_batch_size]
            for attempt in range(5):
                try:
                    with cloud_conn.cursor() as c_cur:
                        for r in batch:
                            mem_id, cid, src_id, content, emb_str, created_at = r
                            c_cur.execute("""
                                INSERT INTO memory_embeddings (memory_id, conversation_id, source_message_id, content, embedding, created_at)
                                VALUES (%s, %s, %s, %s, %s::vector, %s)
                                ON CONFLICT (memory_id) DO NOTHING;
                            """, (mem_id, cid, src_id, content, emb_str, created_at))
                    cloud_conn.commit()
                    break
                except Exception as ex:
                    cloud_conn.rollback()
                    if attempt < 4:
                        import time
                        time.sleep(0.2 * (2 ** attempt))
                    else:
                        raise ex

            print(f"      Progress: {min(i + emb_batch_size, len(emb_rows))}/{len(emb_rows)} embeddings imported to Cloud")

        # Run ANALYZE on Cloud tables
        print("\n[3/3] Running ANALYZE on CockroachDB Cloud tables...")
        with cloud_conn.cursor() as v_cur:
            v_cur.execute("ANALYZE memory_embeddings;")
            v_cur.execute("ANALYZE messages;")
            cloud_conn.commit()
            print("  ✓ ANALYZE complete.")

            # Verification query on Cloud
            v_cur.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s;", (active_cid,))
            c_msg_cnt = v_cur.fetchone()[0]
            v_cur.execute("SELECT COUNT(*) FROM memory_embeddings WHERE conversation_id = %s;", (active_cid,))
            c_emb_cnt = v_cur.fetchone()[0]

            print("\n" + "=" * 80)
            print("MIGRATION VERIFICATION SUMMARY:")
            print(f"  • CockroachDB Cloud Messages Count:   {c_msg_cnt}")
            print(f"  • CockroachDB Cloud Embeddings Count: {c_emb_cnt}")
            print("  ✓ Migration completed successfully without re-embedding!")
            print("=" * 80)

if __name__ == "__main__":
    migrate_data()
