import os
import json
import urllib.request
import urllib.error
import logging
from app.config import COCKROACHDB_MCP_API_KEY, COCKROACHDB_MCP_URL, COCKROACHDB_CLUSTER_ID

logger = logging.getLogger(__name__)

class CockroachCloudMCPClient:
    """
    HTTP JSON-RPC client for CockroachDB Cloud MCP Server (https://cockroachlabs.cloud/mcp).
    Authenticates unattended using Service Account Bearer API Token.
    """
    def __init__(self, api_key: str = None, mcp_url: str = None, cluster_id: str = None):
        self.api_key = api_key or COCKROACHDB_MCP_API_KEY or os.getenv("COCKROACHDB_MCP_API_KEY", "")
        self.mcp_url = mcp_url or COCKROACHDB_MCP_URL or "https://cockroachlabs.cloud/mcp"
        self.cluster_id = cluster_id or COCKROACHDB_CLUSTER_ID or os.getenv("COCKROACHDB_CLUSTER_ID", "cdbaws-31819")
        self._msg_id = 0

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    def _post(self, payload: dict) -> dict:
        if not self.api_key:
            raise ValueError("COCKROACHDB_MCP_API_KEY is not set.")

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "cdbaws-mcp-client/1.0"
        }

        # Set mcp-cluster-id header when a 36-char UUID cluster_id is resolved
        target_url = self.mcp_url
        if self.cluster_id and len(self.cluster_id) == 36 and "-" in self.cluster_id:
            headers["mcp-cluster-id"] = self.cluster_id

        req = urllib.request.Request(target_url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_bytes = resp.read()
                if not resp_bytes:
                    return {}
                text = resp_bytes.decode("utf-8").strip()
                if "data:" in text:
                    for line in text.splitlines():
                        if line.startswith("data:"):
                            j_str = line[5:].strip()
                            if j_str:
                                try:
                                    return json.loads(j_str)
                                except Exception:
                                    pass
                try:
                    return json.loads(text)
                except Exception:
                    return {"raw_text": text}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            logger.error(f"MCP HTTP Error {e.code}: {err_body}")
            raise RuntimeError(f"MCP HTTP Error {e.code}: {err_body}") from e
        except Exception as e:
            logger.error(f"MCP Request Error: {e}")
            raise

    def initialize(self) -> dict:
        """Initializes the MCP session with CockroachDB Cloud MCP Server."""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "cdbaws-mcp-client",
                    "version": "1.0.0"
                }
            }
        }
        res = self._post(payload)
        # Send initialized notification per MCP spec
        try:
            self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        except Exception:
            pass
        return res

    def list_tools(self) -> list[dict]:
        """Returns the list of available MCP tools from CockroachDB Cloud."""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
            "params": {}
        }
        res = self._post(payload)
        if "result" in res and "tools" in res["result"]:
            return res["result"]["tools"]
        return []

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Calls a specific MCP tool with arguments."""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        return self._post(payload)

    def resolve_cluster_id(self) -> str:
        """Dynamically resolves and caches cluster UUID from CockroachDB Cloud via list_clusters tool."""
        if self.cluster_id and len(self.cluster_id) == 36 and "-" in self.cluster_id:
            return self.cluster_id
            
        try:
            res = self.call_tool("list_clusters", {})
            content = res.get("result", {}).get("content", [])
            for item in content:
                if item.get("type") == "text":
                    clusters_data = json.loads(item.get("text", "[]"))
                    if isinstance(clusters_data, dict):
                        clusters_data = clusters_data.get("rows") or clusters_data.get("clusters") or []
                    if isinstance(clusters_data, list) and len(clusters_data) > 0:
                        for cl in clusters_data:
                            if isinstance(cl, dict):
                                c_id = cl.get("id") or cl.get("cluster_id")
                                c_name = cl.get("name")
                                if c_name == "cdbaws" or len(clusters_data) == 1:
                                    if c_id:
                                        self.cluster_id = c_id
                                        logger.info(f"Resolved CockroachDB Cloud Cluster UUID: {c_id}")
                                        return c_id
        except Exception as e:
            logger.warning(f"Could not resolve cluster_id via list_clusters: {e}")
        return self.cluster_id

    def execute_sql_query(self, sql_query: str, params: list = None) -> list[dict]:
        """
        Executes a SQL query against CockroachDB Cloud via MCP.
        Supports parameterized query string formatting and tool invocation.
        """
        # Resolve Cluster UUID first
        cluster_uuid = self.resolve_cluster_id()

        # Format positional parameters into SQL if provided
        formatted_sql = sql_query
        if params:
            formatted_params = []
            for p in params:
                if p is None:
                    formatted_params.append("NULL")
                elif isinstance(p, (int, float)):
                    formatted_params.append(str(p))
                elif isinstance(p, list):
                    # Array or vector
                    array_str = ",".join(f"'{x}'" if isinstance(x, str) else str(x) for x in p)
                    formatted_params.append(f"ARRAY[{array_str}]")
                else:
                    # String escape
                    escaped_str = str(p).replace("'", "''")
                    formatted_params.append(f"'{escaped_str}'")
            
            # Replace %s placeholders with formatted parameter literals
            parts = formatted_sql.split("%s")
            if len(parts) - 1 == len(formatted_params):
                reconstructed = []
                for idx, part in enumerate(parts[:-1]):
                    reconstructed.append(part)
                    reconstructed.append(formatted_params[idx])
                reconstructed.append(parts[-1])
                formatted_sql = "".join(reconstructed)

        # Call MCP query execution tool
        # We try standard tool names: 'run_sql', 'execute_sql', 'query', or 'execute_query'
        tools = self.list_tools()
        tool_names = [t.get("name") for t in tools]
        target_tool = None
        for candidate in ["select_query", "execute_sql", "run_sql", "execute_query", "query"]:
            if candidate in tool_names:
                target_tool = candidate
                break

        if not target_tool and tool_names:
            target_tool = tool_names[0]

        if not target_tool:
            raise RuntimeError(f"No suitable SQL tool found on CockroachDB Cloud MCP. Available tools: {tool_names}")

        args = {"database": "defaultdb", "query": formatted_sql}
        # cluster_id is provided via the mcp-cluster-id header after resolve_cluster_id()
        # Do NOT pass it as a tool argument — the server rejects duplicates.

        logger.info(f"MCP query length: {len(formatted_sql)} chars (limit: 16384)")
        if len(formatted_sql) > 14000:
            logger.warning(f"MCP query approaching limit! First 100 chars: {formatted_sql[:100]}")

        res = self.call_tool(target_tool, args)
        
        # Parse MCP response content
        if "error" in res:
            raise RuntimeError(f"MCP Server error: {res['error']}")

        content_items = res.get("result", {}).get("content", [])
        rows = []
        for item in content_items:
            if item.get("type") == "text":
                text_val = item.get("text", "")
                try:
                    parsed = json.loads(text_val)
                    if isinstance(parsed, list):
                        rows.extend(parsed)
                    elif isinstance(parsed, dict) and "rows" in parsed:
                        rows.extend(parsed["rows"])
                except Exception:
                    logger.debug(f"Raw MCP text response: {text_val}")
        return rows
