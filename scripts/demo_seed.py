import sys
import os

# Ensure app module is in path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.memory_store import create_conversation, add_caregiver_note

SAMPLE_NOTES = [
    {
        "caregiver_name": "Nurse Sarah",
        "note_type": "medication",
        "content": "Grandma Chen took her morning blood pressure medication (Lisinopril 10mg) at 8:30 AM with breakfast and water."
    },
    {
        "caregiver_name": "David (Son)",
        "note_type": "medication",
        "content": "Gave her evening Donepezil (5mg) for memory support around 8:00 PM after dinner. She took it smoothly with warm tea."
    },
    {
        "caregiver_name": "Maria (Caregiver)",
        "note_type": "observation",
        "content": "Noticed Grandma Chen seemed quite confused around mid-afternoon today, repeatedly asking where her late husband was and pacing anxiously near the window."
    },
    {
        "caregiver_name": "David (Son)",
        "note_type": "observation",
        "content": "Grandma was in bright spirits this evening! She spent an hour happily completing a jigsaw puzzle and singing along to old classical radio tunes."
    },
    {
        "caregiver_name": "Nurse Sarah",
        "note_type": "appointment",
        "content": "Dr. Aris Thorne (Cardiologist) follow-up appointment confirmed for next Tuesday at 10:00 AM at St. Jude Medical Center."
    },
    {
        "caregiver_name": "Maria (Caregiver)",
        "note_type": "appointment",
        "content": "Scheduled optometrist eye exam with Dr. Lin for August 18th at 2:00 PM to check her cataract progression and update lens prescription."
    },
    {
        "caregiver_name": "Nurse Sarah",
        "note_type": "medication",
        "content": "Restocked her weekly pill dispenser with morning and evening prescriptions. Lisinopril and Donepezil have 3 weeks of refills remaining."
    },
    {
        "caregiver_name": "Maria (Caregiver)",
        "note_type": "observation",
        "content": "Grandma Chen complained of mild left knee soreness during her morning garden walk. Applied a warm compress and she rested comfortably."
    },
    {
        "caregiver_name": "David (Son)",
        "note_type": "general",
        "content": "Brought over fresh homemade vegetable soup for lunch. Grandma ate a full bowl and enjoyed chatting about her balcony flower garden."
    }
]

def seed_demo_data():
    print("=" * 70)
    print("Milestone 4 Demo: Seeding Caregiver Memory into CockroachDB")
    print("=" * 70)
    
    # 1. Create a new conversation for Grandma Chen
    print("\n1. Creating conversation for 'Grandma Chen's Care Record'...")
    conversation_id = create_conversation(agent_id="multi_caregiver_memory_v1")
    print(f"   Created Conversation ID: {conversation_id}")
    
    # 2. Save conversation ID to file for demo_query.py
    id_filepath = os.path.join(os.path.dirname(__file__), "..", "active_conversation.id")
    with open(id_filepath, "w") as f:
        f.write(conversation_id)
    print(f"   Saved active conversation ID to '{id_filepath}'")
    
    # 3. Ingest caregiver notes and generate real Titan V2 embeddings
    print(f"\n2. Ingesting {len(SAMPLE_NOTES)} caregiver notes & computing Bedrock Titan V2 embeddings...")
    for i, note in enumerate(SAMPLE_NOTES, start=1):
        print(f"   [{i}/{len(SAMPLE_NOTES)}] Inserting note from {note['caregiver_name']} ({note['note_type']})...")
        msg_id = add_caregiver_note(
            conversation_id=conversation_id,
            caregiver_name=note["caregiver_name"],
            content=note["content"],
            note_type=note["note_type"]
        )
        print(f"       -> Message ID: {msg_id}")
        
    print("\n" + "=" * 70)
    print("Seeding Complete Successfully!")
    print(f"Conversation ID: {conversation_id}")
    print("You can now test semantic recall with 'python scripts/demo_query.py \"<question>\"'")
    print("=" * 70)

if __name__ == "__main__":
    seed_demo_data()
