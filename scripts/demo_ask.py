import sys
import os
import argparse

# Ensure app module is in path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.coordinator_agent import answer_caregiver_question

def load_active_conversation_id() -> str:
    """Loads saved conversation ID from active_conversation.id file if present."""
    id_filepath = os.path.join(os.path.dirname(__file__), "..", "active_conversation.id")
    if os.path.exists(id_filepath):
        with open(id_filepath, "r") as f:
            cid = f.read().strip()
            if cid:
                return cid
    return None

def ask_question(conversation_id: str, question: str, k: int = 5):
    print(f"\nQuestion: \"{question}\"")
    print("-" * 70)
    
    try:
        answer = answer_caregiver_question(conversation_id=conversation_id, question=question, k=k)
        print("Synthesized Answer:")
        print(f"{answer}\n")
    except Exception as e:
        print(f"Error executing agent question: {e}\n")

def main():
    parser = argparse.ArgumentParser(
        description="Demo script for coordinator agent synthesizing natural-language answers to caregiver questions via Claude Haiku 4.5."
    )
    parser.add_argument("question", nargs="?", type=str, help="Caregiver question to synthesize an answer for.")
    parser.add_argument("--conversation-id", "--cid", type=str, help="Target conversation ID UUID string.")
    parser.add_argument("-k", type=int, default=5, help="Number of top notes to recall for synthesis (default: 5).")
    
    args = parser.parse_args()
    
    conversation_id = args.conversation_id or load_active_conversation_id()
    
    if not conversation_id:
        print("Error: No active conversation ID found. Please run 'python scripts/demo_seed.py' first to seed data.")
        sys.exit(1)
        
    print("=" * 70)
    print("Milestone 5 Demo: Caregiver Memory Coordinator Agent (Claude Haiku 4.5)")
    print(f"Active Conversation ID: {conversation_id}")
    print("=" * 70)
    
    if args.question:
        ask_question(conversation_id, args.question, k=args.k)
    else:
        print("\nNo question passed on command line. Running standard verification suite...\n")
        
        test_questions = [
            "has she seemed confused or anxious lately?",
            "what medication did she take today and when?",
            "was her afternoon blood pressure medication given today?",
            "when is her next doctor appointment scheduled?",
            "what's her favorite food?",
            "should her medication dosage be changed?"
        ]
        
        for q in test_questions:
            ask_question(conversation_id, q, k=args.k)
            
    print("=" * 70)

if __name__ == "__main__":
    main()
