import sys
import os
import time
import requests
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.web_server import app

def run_server():
    app.run(host="127.0.0.1", port=5050, debug=False)

def test_endpoints():
    # Start Flask server in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(2)

    base_url = "http://127.0.0.1:5050"

    print("1. Testing /healthz...")
    resp = requests.get(f"{base_url}/healthz")
    print(f"Status Code: {resp.status_code}, Response: {resp.json()}")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    print("[OK] /healthz verified!")

    print("\n2. Testing /api/notes (GET)...")
    resp = requests.get(f"{base_url}/api/notes")
    print(f"Status Code: {resp.status_code}, Initial Note Count: {resp.json().get('count')}")

    print("\n3. Testing /api/simulate (POST)...")
    resp = requests.post(f"{base_url}/api/simulate")
    print(f"Status Code: {resp.status_code}, Simulation Message: {resp.json().get('message')}")
    assert resp.status_code == 201
    assert resp.json().get("inserted_count") == 4
    print("[OK] /api/simulate verified!")

    print("\n4. Testing /api/notes after simulation...")
    resp = requests.get(f"{base_url}/api/notes")
    print(f"Status Code: {resp.status_code}, Updated Note Count: {resp.json().get('count')}")

    print("\n5. Testing /api/ask (POST) with follow-up question regarding simulated conflict...")
    q = "Was there any blood pressure medication discrepancy today?"
    resp = requests.post(f"{base_url}/api/ask", json={"question": q})
    print(f"Status Code: {resp.status_code}")
    answer_data = resp.json()
    print("Synthesized Answer:")
    print("-" * 60)
    print(answer_data.get("answer"))
    print("-" * 60)

    assert resp.status_code == 200
    assert "answer" in answer_data
    print("[OK] /api/ask verified!")


if __name__ == "__main__":
    test_endpoints()
