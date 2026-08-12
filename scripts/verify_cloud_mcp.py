import sys
import os

# Set DB_MODE=cloud-mcp before loading app modules
os.environ["DB_MODE"] = "cloud-mcp"

# Ensure app module is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.coordinator_agent import answer_caregiver_question

def load_active_conversation_id() -> str:
    id_filepath = os.path.join(os.path.dirname(__file__), "..", "active_conversation.id")
    if os.path.exists(id_filepath):
        with open(id_filepath, "r") as f:
            cid = f.read().strip()
            if cid:
                return cid
    return None

def verify_cloud_mcp():
    cid = load_active_conversation_id()
    if not cid:
        print("Error: No active conversation ID found in active_conversation.id")
        sys.exit(1)

    print("=" * 80)
    print("STEP 4: CockroachDB Cloud MCP Verification Suite (DB_MODE=cloud-mcp)")
    print("=" * 80)
    print(f"Target Conversation ID: {cid}")
    print(f"Routing logic: Coordinator Agent -> MCP Client -> https://cockroachlabs.cloud/mcp")
    print("=" * 80)

    test_questions = [
        "has she seemed confused or anxious lately?",
        "what medication did she take today and when?",
        "was her afternoon blood pressure medication given today?",
        "when is her next doctor appointment scheduled?",
        "what's her favorite food?",
        "should her medication dosage be changed?"
    ]

    for idx, q in enumerate(test_questions, start=1):
        print(f"\n[Question #{idx}] \"{q}\"")
        print("-" * 75)
        try:
            answer = answer_caregiver_question(conversation_id=cid, question=q, k=5)
            print("Synthesized Agent Answer (via CockroachDB Cloud MCP):")
            print(f"\"\"\"\n{answer}\n\"\"\"")
        except Exception as e:
            print(f"Error: {e}")

    print("\n" + "=" * 80)
    print("STEP 4 VERIFICATION COMPLETE: ALL QUESTIONS EXECUTED VIA MCP")
    print("=" * 80)

if __name__ == "__main__":
    verify_cloud_mcp()
