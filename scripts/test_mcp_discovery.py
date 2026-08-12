import sys
import os
import json

# Ensure app module is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.mcp_client import CockroachCloudMCPClient

def test_mcp():
    print("=" * 80)
    print("STEP 4: CockroachDB Cloud MCP Client Handshake & Discovery")
    print("=" * 80)

    client = CockroachCloudMCPClient()
    
    print("\n1. Initializing MCP connection to https://cockroachlabs.cloud/mcp...")
    init_res = client.initialize()
    print("   ✓ Handshake successful!")
    print(f"   Response: {json.dumps(init_res, indent=2)[:300]}...")

    print("\n2. Discovering available MCP tools on CockroachDB Cloud...")
    tools_res = client._post({"jsonrpc": "2.0", "id": client._next_id(), "method": "tools/list", "params": {}})
    print(f"   Raw tools/list response: {json.dumps(tools_res, indent=2)}")
    tools = client.list_tools()
    print(f"   Found {len(tools)} tools:")
    for t in tools:
        print(f"     • Tool: {t.get('name')} - {t.get('description', '')[:70]}")

    print("\n3. Testing list_clusters tool to resolve cluster UUID...")
    try:
        lc_res = client.call_tool("list_clusters", {})
        print(f"   list_clusters response: {json.dumps(lc_res, indent=2)}")
    except Exception as e:
        print(f"   list_clusters error: {e}")

    print("\n4. Testing simple query execution via MCP...")
    try:
        rows = client.execute_sql_query("SELECT 1 AS status_check;")
        print(f"   ✓ Query result via MCP: {rows}")
    except Exception as e:
        print(f"   Notice calling tool: {e}")

    print("=" * 80)

if __name__ == "__main__":
    test_mcp()
