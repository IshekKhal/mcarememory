import os
import sys
import psycopg
from app.config import COCKROACH_CLOUD_URL, ACTIVE_CONVERSATION_ID
from app.embeddings import generate_embedding

TARGET_MESSAGE_ID = "9990a8de-e074-4002-a5e8-c8c9fac19f16"
NEW_CONTENT = "Gave Grandma Chen her afternoon blood pressure medication booster (Amlodipine 5mg) at 2:00 PM with a glass of water after her nap."

def apply_reword():
    url = COCKROACH_CLOUD_URL
    if "sslmode=verify-full" in url and "sslrootcert=" not in url:
        url = url.replace("sslmode=verify-full", "sslmode=require")

    print(f"=== STEP 1: NOTE REWORDING & EMBEDDING REGENERATION ===")
    print(f"Target message_id: {TARGET_MESSAGE_ID}")

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            # 1. Fetch BEFORE state
            cur.execute("""
                SELECT message_id, caregiver_name, content, created_at
                FROM messages
                WHERE message_id = %s;
            """, (TARGET_MESSAGE_ID,))
            before_msg = cur.fetchone()
            
            cur.execute("""
                SELECT memory_id, content, embedding
                FROM memory_embeddings
                WHERE source_message_id = %s;
            """, (TARGET_MESSAGE_ID,))
            before_emb = cur.fetchone()

            print("\n--- BEFORE EDIT ---")
            if before_msg:
                print(f"messages.caregiver_name : {before_msg[1]}")
                print(f"messages.created_at     : {before_msg[3]}")
                print(f"messages.content        : {repr(before_msg[2])}")
            else:
                print("ERROR: Target message_id not found in `messages`!")
                return

            if before_emb:
                print(f"memory_embeddings.id    : {before_emb[0]}")
                print(f"memory_embeddings.content: {repr(before_emb[1])}")
                emb_str = str(before_emb[2])
                print(f"memory_embeddings.emb_len: {len(emb_str)} chars")
            else:
                print("ERROR: Target message_id not found in `memory_embeddings`!")
                return

            print("\n--- REGENERATING EMBEDDING VIA SAGEMAKER ---")
            print(f"New content text: {repr(NEW_CONTENT)}")
            new_vec = generate_embedding(NEW_CONTENT)
            print(f"Generated new embedding vector: {len(new_vec)} dimensions (sample: {new_vec[:3]}...)")

            new_vec_str = f"[{','.join(str(f) for f in new_vec)}]"

            print("\n--- EXECUTING UPDATE IN COCKROACHDB CLOUD ---")
            # Update messages table
            cur.execute("""
                UPDATE messages
                SET content = %s
                WHERE message_id = %s;
            """, (NEW_CONTENT, TARGET_MESSAGE_ID))

            # Update memory_embeddings table
            cur.execute("""
                UPDATE memory_embeddings
                SET content = %s, embedding = %s::vector
                WHERE source_message_id = %s;
            """, (NEW_CONTENT, new_vec_str, TARGET_MESSAGE_ID))

            conn.commit()
            print("Successfully updated `messages` and `memory_embeddings` tables!")

            # 2. Fetch AFTER state
            cur.execute("""
                SELECT message_id, caregiver_name, content, created_at
                FROM messages
                WHERE message_id = %s;
            """, (TARGET_MESSAGE_ID,))
            after_msg = cur.fetchone()

            cur.execute("""
                SELECT memory_id, content, embedding
                FROM memory_embeddings
                WHERE source_message_id = %s;
            """, (TARGET_MESSAGE_ID,))
            after_emb = cur.fetchone()

            print("\n--- AFTER EDIT ---")
            print(f"messages.caregiver_name : {after_msg[1]}")
            print(f"messages.created_at     : {after_msg[3]}")
            print(f"messages.content        : {repr(after_msg[2])}")
            print(f"memory_embeddings.id    : {after_emb[0]}")
            print(f"memory_embeddings.content: {repr(after_emb[1])}")
            print("VERIFICATION PASSED: Content and embedding updated cleanly.")

if __name__ == "__main__":
    apply_reword()
