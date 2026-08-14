import json
import urllib.request
import time

URL = "http://localhost:5000/api/ask"

def ask(question, mode):
    req_data = json.dumps({"question": question, "mode": mode}).encode("utf-8")
    req = urllib.request.Request(
        URL,
        data=req_data,
        headers={"Content-Type": "application/json"}
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        res_json = json.loads(resp.read().decode("utf-8"))
    t1 = time.perf_counter()
    wall_ms = round((t1 - t0) * 1000.0, 2)
    return res_json, wall_ms

def main():
    print("--- 1. Warm-up Request ---")
    w_res, w_wall = ask("test", "sql")
    w_receipt = w_res.get("retrieval_receipt", {})
    print(f"Warm-up receipt: {w_receipt} (wall: {w_wall} ms)")
    
    questions = [
        ("MCP", "was her afternoon blood pressure medication given today?", "mcp"),
        ("SQL", "when is her next doctor appointment scheduled?", "sql"),
        ("MCP", "has she seemed confused or anxious lately?", "mcp"),
        ("SQL", "what medication did she take today and when?", "sql"),
        ("MCP", "should her medication dosage be changed?", "mcp")
    ]
    
    print("\n--- 2. Firing 5 Back-to-Back Questions ---")
    results = []
    for label, q, mode in questions:
        res, wall = ask(q, mode)
        receipt = res.get("retrieval_receipt", {})
        results.append({
            "label": label,
            "mode": mode,
            "question": q,
            "receipt": receipt,
            "latency_ms": receipt.get("latency_ms"),
            "wall_ms": wall,
            "status": res.get("status"),
            "answer": res.get("answer")
        })
        print(f"[{label}] {q}")
        print(f"  retrieval_receipt.latency_ms: {receipt.get('latency_ms')} ms")
        print(f"  receipt: {receipt}")
        print(f"  wall_time: {wall} ms")
        print()

    print("--- RAW SUMMARY ---")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
