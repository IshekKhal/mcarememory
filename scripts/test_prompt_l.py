import os
import sys
import json
import re

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure app module is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.web_server import app, get_active_conversation_id

SECRET_PATTERNS = [
    re.compile(r'AKIA[0-9A-Z]{16}'),
    re.compile(r'sk-ant-[a-zA-Z0-9_\-]{20,}'),
    re.compile(r'CCDB1_[a-zA-Z0-9_\-]+'),
    re.compile(r'postgresql://[^\s"\']+'),
    re.compile(r'cockroachlabs\.cloud'),
    re.compile(r'cdbaws-\d+'),
    re.compile(r'Bearer\s+[a-zA-Z0-9_\-]+')
]

def scan_payload_for_secrets(payload_str: str) -> list[str]:
    found = []
    for p in SECRET_PATTERNS:
        matches = p.findall(payload_str)
        if matches:
            found.extend(matches)
    return found

def run_prompt_l_tests():
    cid = get_active_conversation_id()
    print("=" * 80)
    print("PROMPT L: LOCAL TESTING & SECRET AUDIT SUITE")
    print(f"Active Conversation ID: {cid}")
    print("=" * 80)

    client = app.test_client()

    # Part 1: Test 3 Questions via mode="sql"
    sql_questions = [
        "was her afternoon blood pressure medication given today?",
        "has she seemed confused or anxious lately?",
        "what medication did she take today and when?"
    ]

    print("\n" + "=" * 80)
    print("PART 1: TESTING MODE='sql' (Direct SQL)")
    print("=" * 80)

    for idx, q in enumerate(sql_questions, start=1):
        print(f"\n[SQL Query #{idx}] \"{q}\"")
        res = client.post("/api/ask", json={"question": q, "mode": "sql"})
        data = res.get_json()
        raw_json = json.dumps(data, indent=2)
        print("Raw JSON Response:")
        print(raw_json)

        # Secret Audit
        leaks = scan_payload_for_secrets(raw_json)
        print(f"Secret Audit Result: {'FAIL - Leaks Detected: ' + str(leaks) if leaks else 'PASSED (0 Secrets in Payload)'}")
        assert res.status_code == 200
        assert data["mode"] == "sql"
        assert data["retrieval_receipt"]["method_label"] == "Direct SQL (CockroachDB Cloud)"
        assert "cte_restructured" not in data["retrieval_receipt"]
        assert len(leaks) == 0

    # Part 2: Test 3 Questions via mode="mcp"
    mcp_questions = [
        "was her afternoon blood pressure medication given today?",
        "when is her next doctor appointment scheduled?",
        "should her medication dosage be changed?"
    ]

    print("\n" + "=" * 80)
    print("PART 2: TESTING MODE='mcp' (Model Context Protocol)")
    print("=" * 80)

    for idx, q in enumerate(mcp_questions, start=1):
        print(f"\n[MCP Query #{idx}] \"{q}\"")
        res = client.post("/api/ask", json={"question": q, "mode": "mcp"})
        data = res.get_json()
        raw_json = json.dumps(data, indent=2)
        print("Raw JSON Response:")
        print(raw_json)

        # Secret Audit
        leaks = scan_payload_for_secrets(raw_json)
        print(f"Secret Audit Result: {'FAIL - Leaks Detected: ' + str(leaks) if leaks else 'PASSED (0 Secrets in Payload)'}")
        assert res.status_code == 200
        assert data["mode"] == "mcp"
        assert data["retrieval_receipt"]["method_label"] == "MCP Server (Model Context Protocol, JSON-RPC)"
        assert data["retrieval_receipt"]["cte_restructured"] is True
        assert len(leaks) == 0

    # Part 3: Test Default Behavior (mode unspecified or default) across 6-question suite
    suite_questions = [
        "has she seemed confused or anxious lately?",
        "what medication did she take today and when?",
        "was her afternoon blood pressure medication given today?",
        "when is her next doctor appointment scheduled?",
        "what's her favorite food?",
        "should her medication dosage be changed?"
    ]

    print("\n" + "=" * 80)
    print("PART 3: 6-QUESTION SUITE REGRESSION VERIFICATION (Default mode='sql')")
    print("=" * 80)

    for idx, q in enumerate(suite_questions, start=1):
        print(f"\n[Suite Query #{idx}] \"{q}\"")
        res = client.post("/api/ask", json={"question": q})
        data = res.get_json()
        assert res.status_code == 200
        assert data["mode"] == "sql"
        assert data["retrieval_receipt"]["method_label"] == "Direct SQL (CockroachDB Cloud)"
        print(f"Answer snippet: {data['answer'][:120]}...")
        print(f"Latency: {data['retrieval_receipt']['latency_ms']} ms")

    print("\n" + "=" * 80)
    print("PROMPT L TEST SUITE COMPLETE: ALL VERIFICATIONS PASSED SAFELY")
    print("=" * 80)

if __name__ == "__main__":
    run_prompt_l_tests()
