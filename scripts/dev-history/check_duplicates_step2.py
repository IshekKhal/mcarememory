import os
import psycopg
from app.config import COCKROACH_CLOUD_URL, ACTIVE_CONVERSATION_ID

def run_step2_checks():
    url = COCKROACH_CLOUD_URL
    if "sslmode=verify-full" in url and "sslrootcert=" not in url:
        url = url.replace("sslmode=verify-full", "sslmode=require")
        
    out = []
    def log(msg=""):
        out.append(msg)

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            log("=== STEP 2 FINDINGS ===")
            log("\n--- 0. DISTINCT conversation_ids across database ---")
            
            # Check conversations table
            try:
                cur.execute("SELECT conversation_id, created_at FROM conversations ORDER BY created_at ASC;")
                convs = cur.fetchall()
                log(f"conversations table row count: {len(convs)}")
                for c in convs:
                    log(f"  conv_id: {c[0]} | created_at: {c[1]}")
            except Exception as e:
                log(f"conversations table error: {e}")
                conn.rollback()
                
            # Check messages table distinct conversation_id counts
            cur.execute("""
                SELECT conversation_id, COUNT(*) 
                FROM messages 
                GROUP BY conversation_id 
                ORDER BY COUNT(*) DESC;
            """)
            msg_convs = cur.fetchall()
            log(f"messages table distinct conversation_ids ({len(msg_convs)} total):")
            for mc in msg_convs:
                log(f"  conversation_id: {mc[0]} | row_count: {mc[1]}")

            # Check memory_embeddings table distinct conversation_id if exists
            try:
                cur.execute("""
                    SELECT conversation_id, COUNT(*) 
                    FROM memory_embeddings 
                    GROUP BY conversation_id 
                    ORDER BY COUNT(*) DESC;
                """)
                emb_convs = cur.fetchall()
                log(f"memory_embeddings table distinct conversation_ids ({len(emb_convs)} total):")
                for ec in emb_convs:
                    log(f"  conversation_id: {ec[0]} | row_count: {ec[1]}")
            except Exception as e:
                log(f"memory_embeddings table error: {e}")
                conn.rollback()

            log("\n--- 1. Duplicate rows in messages for conversation_id = '327dff0c-19f4-49db-b1c0-01aa51fc7594' ---")
            target_cid = "327dff0c-19f4-49db-b1c0-01aa51fc7594"
            cur.execute("""
                SELECT caregiver_name, content, COUNT(*), array_agg(message_id::text), array_agg(created_at::text)
                FROM messages
                WHERE conversation_id = %s
                GROUP BY caregiver_name, content
                HAVING COUNT(*) > 1
                ORDER BY COUNT(*) DESC;
            """, (target_cid,))
            dupes = cur.fetchall()
            log(f"Total duplicate groups found: {len(dupes)}")
            total_extra_rows = 0
            for i, d in enumerate(dupes, 1):
                cname, content, cnt, msg_ids, timestamps = d
                total_extra_rows += (cnt - 1)
                log(f"\nGroup {i}: ({cnt} rows, {cnt - 1} duplicates)")
                log(f"  Caregiver: {cname}")
                log(f"  Content: {repr(content)}")
                log(f"  Message IDs: {msg_ids}")
                log(f"  Timestamps: {timestamps}")
            
            log(f"\nSummary of duplicates:")
            log(f"  Total duplicate groups: {len(dupes)}")
            log(f"  Total redundant duplicate rows: {total_extra_rows}")

            log("\n--- 2. Nurse Jennifer's Lisinopril note check ---")
            cur.execute("""
                SELECT message_id, conversation_id, caregiver_name, content, created_at
                FROM messages
                WHERE conversation_id = %s
                  AND (caregiver_name ILIKE '%%Jennifer%%' AND content ILIKE '%%Lisinopril%%')
                ORDER BY created_at ASC;
            """, (target_cid,))
            j_rows = cur.fetchall()
            log(f"Exact rows matching caregiver_name ILIKE '%Jennifer%' AND content ILIKE '%Lisinopril%': {len(j_rows)}")
            for j in j_rows:
                log(f"  message_id: {j[0]}")
                log(f"  conversation_id: {j[1]}")
                log(f"  caregiver_name: {j[2]}")
                log(f"  created_at: {j[4]}")
                log(f"  content verbatim:\n{j[3]}")

            # Also check Nurse Sarah's Lisinopril note
            log("\n--- Bonus: Nurse Sarah's Lisinopril note check ---")
            cur.execute("""
                SELECT message_id, conversation_id, caregiver_name, content, created_at
                FROM messages
                WHERE conversation_id = %s
                  AND (caregiver_name ILIKE '%%Sarah%%' AND content ILIKE '%%Lisinopril%%')
                ORDER BY created_at ASC;
            """, (target_cid,))
            s_rows = cur.fetchall()
            log(f"Exact rows matching caregiver_name ILIKE '%Sarah%' AND content ILIKE '%Lisinopril%': {len(s_rows)}")
            for s in s_rows:
                log(f"  message_id: {s[0]}")
                log(f"  conversation_id: {s[1]}")
                log(f"  caregiver_name: {s[2]}")
                log(f"  created_at: {s[4]}")
                log(f"  content verbatim:\n{s[3]}")

            # Also check Maria's note check
            log("\n--- Bonus: Maria's flagship note check ---")
            cur.execute("""
                SELECT message_id, conversation_id, caregiver_name, content, created_at
                FROM messages
                WHERE conversation_id = %s
                  AND caregiver_name ILIKE '%%Maria%%'
                ORDER BY created_at ASC;
            """, (target_cid,))
            m_rows = cur.fetchall()
            log(f"Exact rows matching caregiver_name ILIKE '%Maria%': {len(m_rows)}")
            for m in m_rows:
                log(f"  message_id: {m[0]}")
                log(f"  conversation_id: {m[1]}")
                log(f"  caregiver_name: {m[2]}")
                log(f"  created_at: {m[4]}")
                log(f"  content verbatim:\n{m[3]}")

            # Total messages count
            cur.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s;", (target_cid,))
            total_msg_cnt = cur.fetchone()[0]
            log(f"\n--- 3. Dataset Scope & Summary ---")
            log(f"Total messages count for conversation_id={target_cid}: {total_msg_cnt}")
            log(f"Total duplicate groups: {len(dupes)}")
            log(f"Total redundant duplicate rows: {total_extra_rows}")
            log(f"Corrected unique notes count if deduped: {total_msg_cnt - total_extra_rows}")

    result_str = "\n".join(out)
    with open("scripts/step2_output.txt", "w", encoding="utf-8") as f:
        f.write(result_str)
    print(f"Output saved to scripts/step2_output.txt. Total length: {len(result_str)} chars.")

if __name__ == "__main__":
    run_step2_checks()
