import sys
import os

# Ensure app module is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.memory_store import get_connection

def load_active_cid() -> str:
    id_filepath = os.path.join(os.path.dirname(__file__), "..", "active_conversation.id")
    if os.path.exists(id_filepath):
        with open(id_filepath, "r") as f:
            return f.read().strip()
    return ""

def consolidate_dataset():
    active_cid = load_active_cid()
    if not active_cid:
        print("Error: No active conversation ID found in active_conversation.id")
        sys.exit(1)

    print("=" * 80)
    print("STEP 2: Consolidate into One Unified Dataset")
    print("=" * 80)
    print(f"Target Conversation ID ('Grandma Chen's Care Record'): {active_cid}")

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Verify target conversation current count
            cur.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s;", (active_cid,))
            current_target_count = cur.fetchone()[0]
            print(f"  • Current notes in Grandma Chen's conversation: {current_target_count}")

            if current_target_count >= 5000:
                print("✓ Grandma Chen's Care Record is ALREADY consolidated with 5,000+ notes!")
            else:
                # 2. Find scale test conversation ID (with 5000 notes)
                cur.execute("""
                    SELECT conversation_id, COUNT(*) as cnt 
                    FROM messages 
                    WHERE conversation_id != %s 
                    GROUP BY conversation_id 
                    ORDER BY cnt DESC 
                    LIMIT 1;
                """, (active_cid,))
                row = cur.fetchone()
                if not row or row[1] < 100:
                    print("Notice: No separate 5,000 scale conversation found to copy from.")
                else:
                    scale_cid = str(row[0])
                    scale_cnt = row[1]
                # 1. Update any remaining messages from scale conversations
                cur.execute("UPDATE messages SET conversation_id = %s WHERE conversation_id != %s;", (active_cid, active_cid))
                msg_updated = cur.rowcount
                conn.commit()
                print(f"  ✓ Updated {msg_updated} messages to conversation_id = {active_cid}")

                # 2. Update memory_embeddings in batches of 1,000 to prevent clock-drift/lease locks
                total_emb_updated = 0
                while True:
                    cur.execute("""
                        UPDATE memory_embeddings SET conversation_id = %s 
                        WHERE memory_id IN (
                            SELECT memory_id FROM memory_embeddings WHERE conversation_id != %s LIMIT 1000
                        );
                    """, (active_cid, active_cid))
                    updated = cur.rowcount
                    conn.commit()
                    total_emb_updated += updated
                    if updated == 0:
                        break
                    print(f"      Batched embedding update progress: {total_emb_updated} embeddings updated...")

                print(f"  ✓ Complete: Re-assigned messages and {total_emb_updated} embeddings into Grandma Chen's Care Record.")

            # 3. Verify final consolidated dataset
            cur.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s;", (active_cid,))
            final_msg_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM memory_embeddings WHERE conversation_id = %s;", (active_cid,))
            final_emb_count = cur.fetchone()[0]

            print("-" * 80)
            print("CONSOLIDATED DATASET SUMMARY:")
            print(f"  • Target Conversation ID:                 {active_cid}")
            print(f"  • Total Messages under Grandma Chen:      {final_msg_count}")
            print(f"  • Total Embeddings under Grandma Chen:    {final_emb_count}")
            print("-" * 80)

            # Check presence of conflict story notes
            cur.execute("""
                SELECT message_id, caregiver_name, note_type, content 
                FROM messages 
                WHERE conversation_id = %s AND content LIKE '%%Amlodipine%%';
            """, (active_cid,))
            conflict_notes = cur.fetchall()
            print(f"Conflict Story Check ({len(conflict_notes)} Amlodipine notes present):")
            for cn in conflict_notes:
                print(f"  • [{cn[1]}] ({cn[2]}): {cn[3]}")

            # Check sample background notes
            cur.execute("""
                SELECT message_id, caregiver_name, note_type, content 
                FROM messages 
                WHERE conversation_id = %s AND content NOT LIKE '%%Amlodipine%%'
                LIMIT 5;
            """, (active_cid,))
            sample_bg_notes = cur.fetchall()
            print(f"\nSample Background Scale Notes in Grandma Chen's Record:")
            for sbg in sample_bg_notes:
                print(f"  • [{sbg[1]}] ({sbg[2]}): {sbg[3][:90]}...")

            print("=" * 80)

if __name__ == "__main__":
    consolidate_dataset()
