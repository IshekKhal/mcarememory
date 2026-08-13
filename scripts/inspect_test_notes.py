import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import ACTIVE_CONVERSATION_ID
from app.memory_store import get_connection

def inspect_notes():
    cid = ACTIVE_CONVERSATION_ID
    print(f"Active conversation ID: {cid}")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s;", (cid,))
            msg_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM memory_embeddings WHERE conversation_id = %s;", (cid,))
            emb_count = cur.fetchone()[0]
            
            print(f"Total messages count: {msg_count}")
            print(f"Total embeddings count: {emb_count}")
            
            print("\nMost recent 10 notes (ordered by created_at DESC):")
            cur.execute("""
                SELECT message_id, caregiver_name, note_type, content, created_at
                FROM messages
                WHERE conversation_id = %s
                ORDER BY created_at DESC
                LIMIT 10;
            """, (cid,))
            rows = cur.fetchall()
            for r in rows:
                print(f"ID: {r[0]} | Caregiver: {r[1]} ({r[2]}) | Time: {r[4]}")
                print(f"  Content: {r[3]}\n")

if __name__ == "__main__":
    inspect_notes()
