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
    os.getenv("AWS_DEFAULT_REGION", "us-east-1")
)

def get_sagemaker_endpoint_name() -> str:
    """
    Returns the SageMaker endpoint name.
    1. Checks SAGEMAKER_ENDPOINT_NAME env var.
    2. Checks local sagemaker_endpoint.txt file.
    3. Defaults to 'bge-large-en-v1-5-endpoint'.
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
                
    return "bge-large-en-v1-5-endpoint"

SAGEMAKER_ENDPOINT_NAME = get_sagemaker_endpoint_name()

EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1024"))

# Anthropic Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

