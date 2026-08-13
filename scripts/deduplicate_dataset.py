import os
import sys
import time
import psycopg
from psycopg.errors import SerializationFailure
from app.config import COCKROACH_CLOUD_URL, ACTIVE_CONVERSATION_ID

SAFEGUARD_IDS = {
    "9990a8de-e074-4002-a5e8-c8c9fac19f16": "Maria's flagship note",
    "f1f6b935-1f9e-4c54-8c85-2e6f212cfdf6": "Nurse Sarah's flagship note copy 1",
    "3d3d6bac-863e-4d3b-979b-7d1c79bc722c": "Nurse Sarah's flagship note copy 2",
    "14a364fa-5782-4874-aa7b-1e89caa4c3ed": "Nurse Jennifer Lisinopril note 1 (evening log)",
    "2465545b-ca99-474e-a03c-a9ff843f869e": "Nurse Jennifer Lisinopril note 2 (afternoon 23:36:15)",
    "de520dbf-a982-4d2f-be88-d9f23872bb6a": "Nurse Jennifer Lisinopril note 3 (afternoon 23:36:26)",
    "3983b30b-0447-4ae6-b333-68d1eb11b816": "David's soup note"
}

def execute_chunk_delete(conn, table_name, column_name, id_chunk):
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            with conn.cursor() as cur:
                sql = f"DELETE FROM {table_name} WHERE {column_name} = ANY(%s::uuid[]);"
                cur.execute(sql, (id_chunk,))
                count = cur.rowcount
            conn.commit()
            return count
        except SerializationFailure:
            conn.rollback()
            time.sleep(0.2 * attempt)
            if attempt == max_retries:
                raise

def run_deduplication(execute_deletion=False):
    url = COCKROACH_CLOUD_URL
    if "sslmode=verify-full" in url and "sslrootcert=" not in url:
        url = url.replace("sslmode=verify-full", "sslmode=require")

    print(f"=== STEP 2: FULL DATABASE DEDUPLICATION ===")
    print(f"Mode: {'EXECUTE DELETION' if execute_deletion else 'DRY RUN (SCAN & AUDIT ONLY)'}\n")

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            # Step 2.1: Re-confirm duplicate groups fresh
            cur.execute("""
                SELECT 
                    caregiver_name, 
                    content, 
                    COUNT(*) as cnt,
                    array_agg(message_id::text ORDER BY created_at ASC, message_id::text ASC) as msg_ids,
                    array_agg(created_at::text ORDER BY created_at ASC, message_id::text ASC) as created_ats
                FROM messages
                WHERE conversation_id = %s
                GROUP BY caregiver_name, content
                HAVING COUNT(*) > 1
                ORDER BY COUNT(*) DESC;
            """, (ACTIVE_CONVERSATION_ID,))
            dupe_groups = cur.fetchall()

            total_groups = len(dupe_groups)
            total_redundant_rows = sum(g[2] - 1 for g in dupe_groups)

            print(f"1. Fresh Duplicate Scan Results:")
            print(f"   - Conversation ID: {ACTIVE_CONVERSATION_ID}")
            print(f"   - Duplicate Groups Found: {total_groups}")
            print(f"   - Redundant Duplicate Rows to Delete: {total_redundant_rows}\n")

            # Step 2.2: Safety Check against Safeguard IDs
            print("2. Safety Check Cross-Reference Against Known Important IDs:")
            safeguard_findings = {}
            for sg_id, label in SAFEGUARD_IDS.items():
                safeguard_findings[sg_id] = []

            for g_idx, g in enumerate(dupe_groups, 1):
                cname, content, cnt, msg_ids, timestamps = g
                for sg_id in SAFEGUARD_IDS:
                    if sg_id in msg_ids:
                        safeguard_findings[sg_id].append((g_idx, msg_ids))

            for sg_id, label in SAFEGUARD_IDS.items():
                matches = safeguard_findings[sg_id]
                if matches:
                    print(f"   [FOUND IN DUPLICATE GROUP] {sg_id} ({label})")
                    for m in matches:
                        print(f"      Group #{m[0]} (IDs in group: {m[1]})")
                else:
                    print(f"   [UNIQUE / NOT IN DUPLICATE GROUP] {sg_id} ({label})")

            # Step 2.3: Determine KEEP vs DELETE IDs
            ids_to_keep = []
            ids_to_delete = []

            for g_idx, g in enumerate(dupe_groups, 1):
                cname, content, cnt, msg_ids, timestamps = g
                # Keep earliest (msg_ids[0]), delete the rest (msg_ids[1:])
                keep_id = msg_ids[0]
                delete_ids = msg_ids[1:]
                
                ids_to_keep.append(keep_id)
                ids_to_delete.extend(delete_ids)

            print(f"\n3. Keep vs Delete Allocation Summary:")
            print(f"   - Total IDs to Keep: {len(ids_to_keep)}")
            print(f"   - Total IDs to Delete: {len(ids_to_delete)}")

            # Print sample keep/delete breakdown as proof
            print("\n   Sample Keep/Delete breakdown (first 10 groups):")
            for g_idx, g in enumerate(dupe_groups[:10], 1):
                cname, content, cnt, msg_ids, timestamps = g
                print(f"     Group #{g_idx} ({cnt} rows):")
                print(f"       Caregiver: {cname}")
                print(f"       Content: {repr(content[:60])}...")
                print(f"       KEEP  : {msg_ids[0]} (created_at: {timestamps[0]})")
                print(f"       DELETE: {msg_ids[1:]}")

            if not execute_deletion:
                print("\n[DRY RUN COMPLETE] No rows were deleted. Pass '--execute' to perform deletion.")
                return

            print("\n4. Executing Deletion in CockroachDB Cloud in Chunks of 200...")
            chunk_size = 200
            total_embeddings_deleted = 0
            total_messages_deleted = 0

            for i in range(0, len(ids_to_delete), chunk_size):
                chunk = ids_to_delete[i:i + chunk_size]
                emb_cnt = execute_chunk_delete(conn, "memory_embeddings", "source_message_id", chunk)
                msg_cnt = execute_chunk_delete(conn, "messages", "message_id", chunk)
                total_embeddings_deleted += emb_cnt
                total_messages_deleted += msg_cnt
                print(f"   Processed chunk {i//chunk_size + 1}/{(len(ids_to_delete) + chunk_size - 1)//chunk_size} ({len(chunk)} IDs) -> deleted {emb_cnt} embeddings, {msg_cnt} messages.")

            # Step 2.4: Post-deletion total row counts
            with conn.cursor() as cur2:
                cur2.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s;", (ACTIVE_CONVERSATION_ID,))
                final_messages_count = cur2.fetchone()[0]

                cur2.execute("SELECT COUNT(*) FROM memory_embeddings WHERE conversation_id = %s;", (ACTIVE_CONVERSATION_ID,))
                final_embeddings_count = cur2.fetchone()[0]

            print("\n5. Post-Deletion Final Dataset Row Counts:")
            print(f"   - Total `memory_embeddings` deleted: {total_embeddings_deleted}")
            print(f"   - Total `messages` deleted         : {total_messages_deleted}")
            print(f"   - `messages` final row count       : {final_messages_count}")
            print(f"   - `memory_embeddings` final row count: {final_embeddings_count}")
            print("VERIFICATION COMPLETE: Dataset deduplication finished successfully.")

if __name__ == "__main__":
    exec_flag = "--execute" in sys.argv
    run_deduplication(execute_deletion=exec_flag)
