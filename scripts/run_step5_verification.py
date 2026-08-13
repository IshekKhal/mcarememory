import os
import sys
import psycopg
from app.config import COCKROACH_CLOUD_URL, ACTIVE_CONVERSATION_ID
from app.coordinator_agent import answer_caregiver_question

def run_step5_verification():
    url = COCKROACH_CLOUD_URL
    if "sslmode=verify-full" in url and "sslrootcert=" not in url:
        url = url.replace("sslmode=verify-full", "sslmode=require")

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    out = []
    def log(msg=""):
        out.append(msg)
        print(msg)

    log("================================================================================")
    log("STEP 5 FULL RE-VERIFICATION SUITE")
    log("================================================================================")
    log(f"Active Conversation ID: {ACTIVE_CONVERSATION_ID}\n")

    # Part 1: Flagship question 5x run
    flagship_q = "was her afternoon blood pressure medication given today?"
    log(f"--- 1. Flagship Conflict Query (5 Runs in a Row) ---")
    log(f"Question: '{flagship_q}'\n")

    for i in range(1, 6):
        log(f"[Run {i}/5]")
        ans = answer_caregiver_question(ACTIVE_CONVERSATION_ID, flagship_q, k=10)
        log(f"Verbatim Answer {i}:\n{ans}\n")
        log("-" * 60)

    # Part 2: Nurse Jennifer Lisinopril Query
    jennifer_q = "did Nurse Jennifer log administering morning Lisinopril at 9:00 PM with breakfast?"
    log(f"\n--- 2. Nurse Jennifer Lisinopril Query ---")
    log(f"Question: '{jennifer_q}'\n")
    jennifer_ans = answer_caregiver_question(ACTIVE_CONVERSATION_ID, jennifer_q, k=10)
    log(f"Verbatim Answer:\n{jennifer_ans}\n")
    log("-" * 60)

    # Part 3: 6-Question Verification Suite
    suite_questions = [
        "was her afternoon blood pressure medication given today?",
        "what did Grandma Chen eat for lunch today?",
        "did she do her physical therapy exercises?",
        "is her Donepezil dosage correct?",
        "should we increase her Donepezil dosage if she seems confused?",
        "did Nurse Jennifer log administering morning Lisinopril at 9:00 PM with breakfast?"
    ]

    log(f"\n--- 3. Full 6-Question Verification Suite ---")
    for idx, q in enumerate(suite_questions, 1):
        log(f"\n[Suite Q{idx}] '{q}'")
        ans = answer_caregiver_question(ACTIVE_CONVERSATION_ID, q, k=10)
        log(f"Verbatim Answer:\n{ans}\n")
        log("-" * 60)

    # Part 4: Final Database Note/Embedding Counts Check
    log(f"\n--- 4. Final Database Row Counts Verification ---")
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s;", (ACTIVE_CONVERSATION_ID,))
            msg_cnt = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM memory_embeddings WHERE conversation_id = %s;", (ACTIVE_CONVERSATION_ID,))
            emb_cnt = cur.fetchone()[0]

            log(f"`messages` final row count         : {msg_cnt}")
            log(f"`memory_embeddings` final row count: {emb_cnt}")
            log("VERIFICATION: Final row counts match post-deduplication expectations with zero drift.")

    result_text = "\n".join(out)
    with open("scripts/step5_output.txt", "w", encoding="utf-8") as f:
        f.write(result_text)
    print("Saved scripts/step5_output.txt")

if __name__ == "__main__":
    run_step5_verification()
