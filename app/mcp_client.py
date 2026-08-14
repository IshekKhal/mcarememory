import os
import json
import logging
import requests
from app.config import COCKROACHDB_MCP_API_KEY, COCKROACHDB_MCP_URL, COCKROACHDB_CLUSTER_ID

logger = logging.getLogger(__name__)

# Global singleton client instance
_GLOBAL_MCP_CLIENT = None

def get_mcp_client() -> "CockroachCloudMCPClient":
    """Returns or initializes the global singleton CockroachCloudMCPClient instance."""
    global _GLOBAL_MCP_CLIENT
    if _GLOBAL_MCP_CLIENT is None:
        _GLOBAL_MCP_CLIENT = CockroachCloudMCPClient()
    return _GLOBAL_MCP_CLIENT

class CockroachCloudMCPClient:
    """
    HTTP JSON-RPC client for CockroachDB Cloud MCP Server (https://cockroachlabs.cloud/mcp).
    Authenticates unattended using Service Account Bearer API Token.
    Uses persistent HTTP keep-alive session and caches cluster UUID and tool discovery.
    """
    def __init__(self, api_key: str = None, mcp_url: str = None, cluster_id: str = None):
        self.api_key = api_key or COCKROACHDB_MCP_API_KEY or os.getenv("COCKROACHDB_MCP_API_KEY", "")
        self.mcp_url = mcp_url or COCKROACHDB_MCP_URL or "https://cockroachlabs.cloud/mcp"
        self.cluster_id = cluster_id or COCKROACHDB_CLUSTER_ID or os.getenv("COCKROACHDB_CLUSTER_ID", "cdbaws-31819")
        self._msg_id = 0
        self._cached_tools = None
        self._target_tool_name = None
        self._initialized = False

        # Persistent HTTP session with connection pooling and keep-alive
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "cdbaws-mcp-client/1.0"
        })
        if self.cluster_id and len(self.cluster_id) == 36 and "-" in self.cluster_id:
            self.session.headers["mcp-cluster-id"] = self.cluster_id

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    def _post(self, payload: dict) -> dict:
        if not self.api_key:
            raise ValueError("COCKROACHDB_MCP_API_KEY is not set.")

        try:
            resp = self.session.post(self.mcp_url, json=payload, timeout=30)
            if not resp.text:
                return {}

            text = resp.text.strip()
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
                return resp.json()
            except Exception:
                return {"raw_text": text}
        except requests.exceptions.HTTPError as e:
            err_body = e.response.text if e.response else str(e)
            logger.error(f"MCP HTTP Error: {err_body}")
            raise RuntimeError(f"MCP HTTP Error: {err_body}") from e
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
        self._initialized = True
        return res

    def list_tools(self, force_refresh: bool = False) -> list[dict]:
        """
        Returns the list of available MCP tools from CockroachDB Cloud.
        Results are cached in memory after first call to eliminate redundant network round-trips.
        """
        if self._cached_tools and not force_refresh:
            return self._cached_tools

        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
            "params": {}
        }
        res = self._post(payload)
        if "result" in res and "tools" in res["result"]:
            self._cached_tools = res["result"]["tools"]
            return self._cached_tools
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
        """
        Dynamically resolves and caches cluster UUID from CockroachDB Cloud via list_clusters tool.
        Caches the 36-character UUID on self.cluster_id and in session headers so list_clusters is
        never called more than once per application lifecycle.
        """
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
                                        self.session.headers["mcp-cluster-id"] = self.cluster_id
                                        logger.info(f"Resolved CockroachDB Cloud Cluster UUID: {c_id}")
                                        return c_id
        except Exception as e:
            logger.warning(f"Could not resolve cluster_id via list_clusters: {e}")
        return self.cluster_id

    def _get_target_sql_tool(self) -> str:
        """Resolves and caches the appropriate SQL tool name from available MCP tools."""
        if self._target_tool_name:
            return self._target_tool_name

        tools = self.list_tools()
        tool_names = [t.get("name") for t in tools]
        for candidate in ["select_query", "execute_sql", "run_sql", "execute_query", "query"]:
            if candidate in tool_names:
                self._target_tool_name = candidate
                return candidate

        if tool_names:
            self._target_tool_name = tool_names[0]
            return self._target_tool_name

        # Fallback default if tool discovery list was empty
        self._target_tool_name = "select_query"
        return self._target_tool_name

    def execute_sql_query(self, sql_query: str, params: list = None) -> list[dict]:
        """
        Executes a SQL query against CockroachDB Cloud via MCP.
        Supports parameterized query string formatting and tool invocation.
        Reuses cached cluster UUID and cached SQL tool name to minimize round-trip overhead.
        """
        # 1. Resolve Cluster UUID (cached after 1st call)
        self.resolve_cluster_id()

        # 2. Format positional parameters into SQL if provided
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

        # 3. Get cached query execution tool
        target_tool = self._get_target_sql_tool()

        args = {"database": "defaultdb", "query": formatted_sql}
        # cluster_id is provided via the mcp-cluster-id header after resolve_cluster_id()
        # Do NOT pass it as a tool argument — the server rejects duplicates.

        logger.debug(f"MCP query length: {len(formatted_sql)} chars (limit: 16384)")
        if len(formatted_sql) > 14000:
            logger.warning(f"MCP query approaching limit! First 100 chars: {formatted_sql[:100]}")

        res = self.call_tool(target_tool, args)

        # 4. Parse MCP response content
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
