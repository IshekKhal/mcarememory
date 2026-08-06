import sys
import os

# Ensure app module is in path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.memory_store import get_connection, create_conversation, add_caregiver_note
from scripts.demo_seed import SAMPLE_NOTES

CONFLICT_NOTES = [
    {
        "caregiver_name": "Maria (Caregiver)",
        "note_type": "medication",
        "content": "Gave Grandma Chen her afternoon blood pressure booster (Amlodipine 5mg) at 2:00 PM with a glass of water after her nap."
    },
    {
        "caregiver_name": "Nurse Sarah",
        "note_type": "medication",
        "content": "Checked Grandma Chen's pill box at 2:30 PM and noticed her afternoon blood pressure booster (Amlodipine 5mg) was missed and still in the compartment. Left a reminder note on the counter."
    }
]

def load_or_create_conversation_id() -> str:
    """Loads saved conversation ID from active_conversation.id file or creates a new one."""
    id_filepath = os.path.join(os.path.dirname(__file__), "..", "active_conversation.id")
    if os.path.exists(id_filepath):
        with open(id_filepath, "r") as f:
            cid = f.read().strip()
            if cid:
                return cid
    cid = create_conversation(agent_id="multi_caregiver_memory_v1")
    with open(id_filepath, "w") as f:
        f.write(cid)
    return cid

def seed_conflict_demo_data():
    print("=" * 75)
    print("Milestone 7 Demo: Seeding Conflicting Caregiver Notes into CockroachDB")
    print("=" * 75)
    
    conversation_id = load_or_create_conversation_id()
    print(f"\nTarget Conversation ID: {conversation_id}")
    
    # 1. Reset conversation memory to baseline 9 notes
    print("\n1. Resetting conversation memory to clean baseline state...")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM memory_embeddings WHERE conversation_id = %s;", (conversation_id,))
            cur.execute("DELETE FROM messages WHERE conversation_id = %s;", (conversation_id,))
            conn.commit()
    print("   Cleared old messages and embeddings.")
    
    print(f"   Re-seeding original {len(SAMPLE_NOTES)} baseline caregiver notes...")
    for i, note in enumerate(SAMPLE_NOTES, start=1):
        add_caregiver_note(
            conversation_id=conversation_id,
            caregiver_name=note["caregiver_name"],
            content=note["content"],
            note_type=note["note_type"]
        )
    print(f"   ✓ Baseline reset complete: {len(SAMPLE_NOTES)} notes stored.")
    
    # 2. Insert conflicting caregiver notes
    print(f"\n2. Ingesting {len(CONFLICT_NOTES)} conflicting caregiver notes & computing embeddings...")
    for i, note in enumerate(CONFLICT_NOTES, start=1):
        print(f"   [Conflict Note #{i}] Ingesting note from {note['caregiver_name']} ({note['note_type']})...")
        msg_id = add_caregiver_note(
            conversation_id=conversation_id,
            caregiver_name=note["caregiver_name"],
            content=note["content"],
            note_type=note["note_type"]
        )
        print(f"       -> Message ID: {msg_id}")
        
    total_expected = len(SAMPLE_NOTES) + len(CONFLICT_NOTES)
    print("\n" + "=" * 75)
    print("Conflict Data Seeding Completed Successfully!")
    print(f"Total Notes in Database: {total_expected} (9 baseline + 2 conflicting)")
    print(f"Active Conversation ID:  {conversation_id}")
    print("You can now test conflict-aware synthesis with:")
    print("  python scripts/demo_ask.py \"was her afternoon blood pressure medication given today?\"")
    print("=" * 75)

if __name__ == "__main__":
    seed_conflict_demo_data()
