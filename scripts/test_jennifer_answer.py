import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import ACTIVE_CONVERSATION_ID
from app.coordinator_agent import answer_caregiver_question

def test_jennifer():
    cid = ACTIVE_CONVERSATION_ID
    q = "what did Nurse Jennifer log about blood pressure medication?"
    print(f"Question: {q}")
    ans = answer_caregiver_question(conversation_id=cid, question=q, k=5)
    print("Answer:")
    print(ans)

if __name__ == "__main__":
    test_jennifer()
