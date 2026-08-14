import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import ACTIVE_CONVERSATION_ID
from app.memory_store import get_connection

def main():
    cid = ACTIVE_CONVERSATION_ID
    print("=" * 80)
    print(f"EXACT FACT RE-CHECK FOR CONVERSATION: {cid}")
    print("=" * 80)

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. David's vegetable soup notes
            print("\n--- FACT RE-CHECK 1: David's Vegetable Soup Entries ---")
            cur.execute("""
                SELECT message_id, caregiver_name, note_type, content, created_at
                FROM messages
                WHERE conversation_id = %s
                  AND caregiver_name ILIKE '%%David%%'
                  AND content ILIKE '%%soup%%';
            """, (cid,))
            david_soup_rows = cur.fetchall()
            print(f"Total entries logged by David mentioning soup: {len(david_soup_rows)}")
            for idx, r in enumerate(david_soup_rows, 1):
                print(f"  [{idx}] ID: {r[0]} | Caregiver: {r[1]} | Time: {r[4]}")
                print(f"      Content: \"{r[3]}\"")

            # 2. Jennifer's timing / blood pressure notes
            print("\n--- FACT RE-CHECK 2: Jennifer's Lisinopril / Blood Pressure Entries ---")
            cur.execute("""
                SELECT message_id, caregiver_name, note_type, content, created_at
                FROM messages
                WHERE conversation_id = %s
                  AND (caregiver_name ILIKE '%%Jennifer%%' OR content ILIKE '%%Jennifer%%')
                  AND (content ILIKE '%%Lisinopril%%' OR content ILIKE '%%blood pressure%%' OR content ILIKE '%%medication%%');
            """, (cid,))
            jennifer_rows = cur.fetchall()
            print(f"Total entries logged by/mentioning Jennifer for medication/blood pressure: {len(jennifer_rows)}")
            for idx, r in enumerate(jennifer_rows, 1):
                print(f"  [{idx}] ID: {r[0]} | Caregiver: {r[1]} | Time: {r[4]}")
                print(f"      Content: \"{r[3]}\"")

    print("=" * 80)

if __name__ == "__main__":
    main()
