import os
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# CockroachDB connection string
COCKROACH_URL = os.getenv(
    "COCKROACH_URL",
    "postgresql://root@localhost:26257/agent_memory?sslmode=disable"
)

# AWS configuration
AWS_REGION = os.getenv(
    "AWS_REGION",
    os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
)

def get_sagemaker_endpoint_name() -> str:
    """
    Returns the SageMaker endpoint name.
    1. Checks SAGEMAKER_ENDPOINT_NAME env var.
    2. Checks local sagemaker_endpoint.txt file.
    3. Defaults to 'caregiver-bge-embeddings'.
    """
    env_name = os.getenv("SAGEMAKER_ENDPOINT_NAME")
    if env_name and env_name.strip():
        return env_name.strip()
        
    endpoint_file = os.path.join(os.path.dirname(__file__), "..", "sagemaker_endpoint.txt")
    if os.path.exists(endpoint_file):
        with open(endpoint_file, "r") as f:
            val = f.read().strip()
            if val:
                return val
                
    return "caregiver-bge-embeddings"

SAGEMAKER_ENDPOINT_NAME = get_sagemaker_endpoint_name()

EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1024"))
EMBEDDING_MODE = os.getenv("EMBEDDING_MODE", "local").lower().strip()

# Database Mode & Cloud configuration
COCKROACH_CLOUD_URL = os.getenv("COCKROACH_CLOUD_URL", "")
DB_MODE = os.getenv("DB_MODE", "cloud" if COCKROACH_CLOUD_URL else "local").lower().strip()

# MCP Configuration
COCKROACHDB_MCP_API_KEY = os.getenv("COCKROACHDB_MCP_API_KEY", "")
COCKROACHDB_CLUSTER_ID = os.getenv("COCKROACHDB_CLUSTER_ID", "cdbaws")
COCKROACHDB_MCP_URL = os.getenv("COCKROACHDB_MCP_URL", "https://cockroachlabs.cloud/mcp")

# Anthropic Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

# Active Conversation Configuration
def load_active_conversation_id() -> str:
    env_cid = os.getenv("ACTIVE_CONVERSATION_ID")
    if env_cid and env_cid.strip():
        return env_cid.strip()
    id_filepath = os.path.join(os.path.dirname(__file__), "..", "active_conversation.id")
    if os.path.exists(id_filepath):
        try:
            with open(id_filepath, "r") as f:
                cid = f.read().strip()
                if cid:
                    return cid
        except Exception:
            pass
    return "327dff0c-19f4-49db-b1c0-01aa51fc7594"

ACTIVE_CONVERSATION_ID = load_active_conversation_id()


