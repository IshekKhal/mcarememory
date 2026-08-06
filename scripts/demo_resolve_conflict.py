import sys
import os
import argparse

# Ensure app module is in path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.memory_store import get_connection, add_resolution_note

def load_active_conversation_id() -> str:
    """Loads saved conversation ID from active_conversation.id file if present."""
    id_filepath = os.path.join(os.path.dirname(__file__), "..", "active_conversation.id")
    if os.path.exists(id_filepath):
        with open(id_filepath, "r") as f:
            cid = f.read().strip()
            if cid:
                return cid
    return None

def find_conflicting_note_ids(conversation_id: str, keyword: str = "Amlodipine") -> list[str]:
    """Finds message IDs of notes matching keyword in conversation_id."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT message_id, caregiver_name, content 
                FROM messages 
                WHERE conversation_id = %s AND (content ILIKE %s OR content ILIKE %s)
                ORDER BY created_at ASC;
                """,
                (conversation_id, f"%{keyword}%", "%blood pressure%")
            )
            rows = cur.fetchall()
            return [str(row[0]) for row in rows]

def resolve_conflict(
    conversation_id: str,
    caregiver_name: str,
    resolution_text: str,
    note_ids: list[str] = None
):
    if not note_ids:
        note_ids = find_conflicting_note_ids(conversation_id, "Amlodipine")
        
    print("=" * 75)
    print("Milestone 8 Demo: Recording Caregiver Conflict Resolution Note")
    print("=" * 75)
    print(f"Active Conversation ID: {conversation_id}")
    print(f"Caregiver / Role:       {caregiver_name}")
    print(f"Resolving Note IDs:     {note_ids}")
    print(f"Resolution Note Text:   \"{resolution_text}\"")
    print("-" * 75)
    
    msg_id = add_resolution_note(
        conversation_id=conversation_id,
        caregiver_name=caregiver_name,
        content=resolution_text,
        resolves_note_ids=note_ids
    )
    
    print(f"✓ Resolution note recorded successfully into CockroachDB!")
    print(f"  New Resolution Message ID: {msg_id}")
    print("=" * 75)
    print("You can now verify the resolved conflict with:")
    print("  python scripts/demo_ask.py \"was her afternoon blood pressure medication given today?\"")
    print("=" * 75)
    return msg_id

def main():
    parser = argparse.ArgumentParser(
        description="CLI tool to record a conflict resolution note linking conflicting caregiver notes."
    )
    parser.add_argument(
        "--content", "-c", 
        type=str, 
        default="Confirmed with Maria that the 2:00 PM blood pressure medication (Amlodipine 5mg) was given at 2:00 PM. Nurse Sarah checked the pill box right before Maria updated the log.",
        help="Resolution note content explaining what was confirmed."
    )
    parser.add_argument(
        "--caregiver", "-g", 
        type=str, 
        default="Care Coordinator",
        help="Name or role of person logging resolution."
    )
    parser.add_argument(
        "--cid", 
        type=str, 
        help="Target conversation ID UUID string."
    )
    parser.add_argument(
        "--resolves-ids", 
        nargs="*", 
        help="Specific message ID UUIDs being resolved. If omitted, automatically finds conflicting Amlodipine notes."
    )
    
    args = parser.parse_args()
    
    conversation_id = args.cid or load_active_conversation_id()
    if not conversation_id:
        print("Error: No active conversation ID found. Please run 'python scripts/demo_seed_conflict.py' first.")
        sys.exit(1)
        
    resolve_conflict(
        conversation_id=conversation_id,
        caregiver_name=args.caregiver,
        resolution_text=args.content,
        note_ids=args.resolves_ids
    )

if __name__ == "__main__":
    main()
