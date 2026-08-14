import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import ACTIVE_CONVERSATION_ID
from app.coordinator_agent import answer_caregiver_question

def test_questions():
    cid = ACTIVE_CONVERSATION_ID
    
    q1 = "was her afternoon blood pressure medication given today?"
    print(f"Question 1: {q1}")
    ans1 = answer_caregiver_question(conversation_id=cid, question=q1, k=5)
    print("Answer 1:")
    print(ans1)
    print("-" * 60)
    
    q2 = "what's her favorite food?"
    print(f"Question 2: {q2}")
    ans2 = answer_caregiver_question(conversation_id=cid, question=q2, k=5)
    print("Answer 2:")
    print(ans2)
    print("-" * 60)

if __name__ == "__main__":
    test_questions()
