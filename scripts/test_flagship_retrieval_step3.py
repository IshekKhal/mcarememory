import os
import psycopg
from app.config import COCKROACH_CLOUD_URL, ACTIVE_CONVERSATION_ID
from app.embeddings import generate_embedding

def test_ranks():
    url = COCKROACH_CLOUD_URL
    if "sslmode=verify-full" in url and "sslrootcert=" not in url:
        url = url.replace("sslmode=verify-full", "sslmode=require")

    questions = [
        "was her afternoon blood pressure medication given today",
        "did she get her afternoon BP medication",
        "was her blood pressure booster given this afternoon",
        "did Grandma Chen receive her blood pressure medication this afternoon",
        "what blood pressure medication was given to Grandma Chen in the afternoon",
        "was her blood pressure medication given"
    ]

    # Target message IDs to track
    maria_msg_id = "9990a8de-e074-4002-a5e8-c8c9fac19f16" # Maria: afternoon blood pressure booster (Amlodipine 5mg)
    sarah_msg_id = "3d3d6bac-863e-4d3b-979b-7d1c79bc722c" # Sarah: morning blood pressure medication (Lisinopril 10mg)
    jennifer_msg_id = "2465545b-ca99-474e-a03c-a9ff843f869e" # Jennifer: afternoon Lisinopril 10mg

    lines = []
    def log(msg=""):
        lines.append(msg)

    log("=== STEP 3: RETRIEVAL RANKS TEST ===\n")

    # First pre-generate embeddings for all questions
    log("Generating embeddings for test questions...")
    q_embeddings = [generate_embedding(q) for q in questions]

    # Pre-generate embeddings for proposed reworded notes
    maria_reworded_1 = "Gave Grandma Chen her afternoon blood pressure medication (Amlodipine 5mg booster) at 2:00 PM with a glass of water after her nap."
    maria_reworded_2 = "Gave Grandma Chen her afternoon blood pressure medication booster (Amlodipine 5mg) at 2:00 PM with a glass of water after her nap."
    sarah_reworded_1 = "Grandma Chen took her morning blood pressure medication (Lisinopril 10mg) at 8:30 AM with breakfast and water." # existing text

    maria_reworded_1_emb = generate_embedding(maria_reworded_1)
    maria_reworded_2_emb = generate_embedding(maria_reworded_2)

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            for q_idx, (q, q_emb) in enumerate(zip(questions, q_embeddings), 1):
                log(f"--- Question {q_idx}: '{q}' ---")
                q_emb_str = f"[{','.join(str(f) for f in q_emb)}]"

                cur.execute("""
                    SELECT 
                        ROW_NUMBER() OVER (ORDER BY e.embedding <-> %s::vector ASC) as rank,
                        m.message_id,
                        m.caregiver_name,
                        e.content,
                        (e.embedding <-> %s::vector) as distance
                    FROM memory_embeddings e
                    JOIN messages m ON e.source_message_id = m.message_id
                    WHERE e.conversation_id = %s
                    ORDER BY distance ASC;
                """, (q_emb_str, q_emb_str, ACTIVE_CONVERSATION_ID))

                all_results = cur.fetchall()
                log(f"Total notes searched: {len(all_results)}")

                # Print top 10 results
                log("Top 10 retrieved notes:")
                for r in all_results[:10]:
                    rk, msg_id, cname, content, dist = r
                    flag = ""
                    if msg_id == maria_msg_id:
                        flag = " *** [MARIA FLAGSHIP NOTE] ***"
                    elif msg_id == sarah_msg_id:
                        flag = " *** [SARAH FLAGSHIP NOTE] ***"
                    elif msg_id == jennifer_msg_id:
                        flag = " *** [JENNIFER LISINOPRIL NOTE] ***"
                    log(f"  Rank {rk:3d} | dist={dist:.4f} | {cname}: {content[:80]}...{flag}")

                # Print specific ranks for target notes
                maria_rank = next((r for r in all_results if r[1] == maria_msg_id), None)
                sarah_rank = next((r for r in all_results if r[1] == sarah_msg_id), None)
                jennifer_rank = next((r for r in all_results if r[1] == jennifer_msg_id), None)

                log("\n  Target Note Ranks (EXISTING PRODUCTION NOTES):")
                if maria_rank:
                    log(f"    Maria's afternoon booster note: Rank {maria_rank[0]} (dist={maria_rank[4]:.4f})")
                else:
                    log(f"    Maria's afternoon booster note: NOT FOUND")

                if sarah_rank:
                    log(f"    Sarah's morning BP note: Rank {sarah_rank[0]} (dist={sarah_rank[4]:.4f})")
                else:
                    log(f"    Sarah's morning BP note: NOT FOUND")

                if jennifer_rank:
                    log(f"    Jennifer's afternoon Lisinopril note: Rank {jennifer_rank[0]} (dist={jennifer_rank[4]:.4f})")
                else:
                    log(f"    Jennifer's afternoon Lisinopril note: NOT FOUND")

                # Test simulated distance and rank for reworded Maria notes
                import math
                def cosine_dist(vecA, vecB):
                    dot = sum(a * b for a, b in zip(vecA, vecB))
                    normA = math.sqrt(sum(a * a for a in vecA))
                    normB = math.sqrt(sum(b * b for b in vecB))
                    return 1.0 - (dot / (normA * normB))

                def l2_dist(vecA, vecB):
                    return math.sqrt(sum((a - b) ** 2 for a, b in zip(vecA, vecB)))

                dist_reworded_1 = l2_dist(q_emb, maria_reworded_1_emb)
                dist_reworded_2 = l2_dist(q_emb, maria_reworded_2_emb)

                # Find simulated rank among all_results
                sim_rank_1 = sum(1 for r in all_results if r[4] < dist_reworded_1) + 1
                sim_rank_2 = sum(1 for r in all_results if r[4] < dist_reworded_2) + 1

                log(f"\n  SIMULATED PROPOSED REWORDED MARIA NOTE RANKS:")
                log(f"    Option 1 ('...afternoon blood pressure medication (Amlodipine 5mg booster)...'): Simulated dist={dist_reworded_1:.4f} -> Simulated Rank {sim_rank_1}")
                log(f"    Option 2 ('...afternoon blood pressure medication booster (Amlodipine 5mg)...'): Simulated dist={dist_reworded_2:.4f} -> Simulated Rank {sim_rank_2}")

                log("\n" + "="*60 + "\n")

    res = "\n".join(lines)
    with open("scripts/step3_output.txt", "w", encoding="utf-8") as f:
        f.write(res)
    print("Saved step3_output.txt")

if __name__ == "__main__":
    test_ranks()
