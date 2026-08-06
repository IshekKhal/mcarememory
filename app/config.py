import os
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# CockroachDB connection string
COCKROACH_URL = os.getenv(
    "COCKROACH_URL",
    "postgresql://root@localhost:26257/agent_memory?sslmode=disable"
)

# AWS Bedrock configuration
AWS_REGION = os.getenv(
    "AWS_REGION",
    os.getenv("AWS_DEFAULT_REGION", "us-east-1")
)

BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID",
    "amazon.titan-embed-text-v2:0"
)

EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1024"))
