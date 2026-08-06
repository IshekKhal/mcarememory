import sys
import os
import argparse

# Ensure app module is in path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.memory_store import recall_relevant_notes

def load_active_conversation_id() -> str:
    """Loads saved conversation ID from active_conversation.id file if present."""
    id_filepath = os.path.join(os.path.dirname(__file__), "..", "active_conversation.id")
    if os.path.exists(id_filepath):
        with open(id_filepath, "r") as f:
            cid = f.read().strip()
            if cid:
                return cid
    return None

def execute_query(conversation_id: str, question: str, k: int = 3):
    print(f"\nQuery: \"{question}\"")
    print("-" * 70)
    
    try:
        results = recall_relevant_notes(conversation_id=conversation_id, question=question, k=k)
        
        if not results:
            print("No relevant notes found.")
            return
            
        for rank, item in enumerate(results, start=1):
            print(f"Match #{rank} (Cosine Distance: {item['distance']:.4f})")
            print(f"  Caregiver: {item['caregiver_name']} | Type: {item['note_type']} | Date: {item['created_at']}")
            print(f"  Note: \"{item['content']}\"")
            print()
    except Exception as e:
        print(f"Error executing recall query: {e}")

def main():
    parser = argparse.ArgumentParser(description="Demo script for semantic recall of caregiver notes via SageMaker BGE & CockroachDB vector search.")
    parser.add_argument("question", nargs="?", type=str, help="Question to search for semantically relevant caregiver notes.")
    parser.add_argument("--conversation-id", "--cid", type=str, help="Target conversation ID UUID string.")
    parser.add_argument("-k", type=int, default=3, help="Number of top matches to return (default: 3).")
    
    args = parser.parse_args()
    
    conversation_id = args.conversation_id or load_active_conversation_id()
    
    if not conversation_id:
        print("Error: No active conversation ID found. Please run 'python scripts/demo_seed.py' first to seed data.")
        sys.exit(1)
        
    print("=" * 70)
    print("Milestone 4 Demo: Caregiver Memory Semantic Recall")
    print(f"Active Conversation ID: {conversation_id}")
    print("=" * 70)
    
    if args.question:
        execute_query(conversation_id, args.question, k=args.k)
    else:
        print("\nNo question passed on command line. Running 3 standard domain queries...\n")
        
        queries = [
            "has she seemed confused or anxious lately?",
            "what medication did she take today and when?",
            "when is her next doctor appointment scheduled?"
        ]
        
        for q in queries:
            execute_query(conversation_id, q, k=args.k)
            
    print("=" * 70)

if __name__ == "__main__":
    main()
