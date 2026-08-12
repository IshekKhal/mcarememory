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

def reconcile_dataset_counts():
    active_cid = load_active_cid()
    print("=" * 80)
    print("STEP 1: Dataset Discrepancy Reconciliation")
    print("=" * 80)
    print(f"Active Conversation ID from file ('Grandma Chen's Care Record'): {active_cid or 'NONE FOUND'}")
    print("-" * 80)

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Total counts
            cur.execute("SELECT COUNT(*) FROM messages;")
            total_messages = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM memory_embeddings;")
            total_embeddings = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM conversations;")
            total_conversations = cur.fetchone()[0]

            print(f"Database Overview:")
            print(f"  • Total Conversations in DB: {total_conversations}")
            print(f"  • Total Messages in DB:      {total_messages}")
            print(f"  • Total Embeddings in DB:    {total_embeddings}")
            print("-" * 80)

            # 2. Per conversation breakdown using fast separate aggregations
            cur.execute("SELECT conversation_id, agent_id FROM conversations;")
            conv_map = {str(r[0]): r[1] or "N/A" for r in cur.fetchall()}

            cur.execute("SELECT conversation_id, COUNT(*) FROM messages GROUP BY conversation_id;")
            msg_counts = {str(r[0]): r[1] for r in cur.fetchall()}

            cur.execute("SELECT conversation_id, COUNT(*) FROM memory_embeddings GROUP BY conversation_id;")
            emb_counts = {str(r[0]): r[1] for r in cur.fetchall()}

            all_cids = sorted(list(set(conv_map.keys()) | set(msg_counts.keys()) | set(emb_counts.keys())), 
                              key=lambda c: msg_counts.get(c, 0), reverse=True)

            print(f"{'Conversation ID':<38} | {'Agent ID':<25} | {'Messages':<10} | {'Embeddings':<10} | {'Is Active?':<10}")
            print("-" * 105)

            active_found_messages = 0
            for cid in all_cids:
                agent_id = conv_map.get(cid, "N/A")
                msg_cnt = msg_counts.get(cid, 0)
                emb_cnt = emb_counts.get(cid, 0)
                is_active = "YES (Grandma Chen)" if cid == active_cid else "NO"
                if cid == active_cid:
                    active_found_messages = msg_cnt
                print(f"{cid:<38} | {agent_id:<25} | {msg_cnt:<10} | {emb_cnt:<10} | {is_active:<10}")

            print("=" * 105)
            
            # 3. Check specific notes in active conversation
            if active_cid:
                cur.execute("""
                    SELECT caregiver_name, note_type, content 
                    FROM messages 
                    WHERE conversation_id = %s 
                    LIMIT 10;
                """, (active_cid,))
                sample_notes = cur.fetchall()
                print(f"\nSample notes in Active Conversation ({active_cid}):")
                for sn in sample_notes:
                    print(f"  • [{sn[0]}] ({sn[1]}): {sn[2][:80]}...")

            print("\nReconciliation Summary:")
            print(f"  1. Messages in Active 'Grandma Chen' Conversation ({active_cid}): {active_found_messages}")
            print(f"  2. Total Messages across ALL Conversations: {total_messages}")

if __name__ == "__main__":
    reconcile_dataset_counts()
