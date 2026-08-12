import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import time
import argparse
import subprocess
import boto3
from botocore.exceptions import ClientError

# Ensure app module is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import AWS_REGION

DEFAULT_ENDPOINT_NAME = "caregiver-bge-serverless"
MODEL_ID = "huggingface-sentencesimilarity-bge-large-en-v1-5"
DEFAULT_MEMORY_MB = 4096
DEFAULT_MAX_CONCURRENCY = 10
ENDPOINT_TXT_PATH = os.path.join(os.path.dirname(__file__), "..", "sagemaker_endpoint.txt")

def deploy_serverless_endpoint(
    endpoint_name: str = None,
    memory_mb: int = DEFAULT_MEMORY_MB,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    role_arn: str = None
):
    """
    Deploys the BAAI/bge-large-en-v1.5 embedding model to a SageMaker Serverless Inference Endpoint.
    Serverless endpoints scale automatically to zero when idle, avoiding ongoing hourly EC2 charges.
    """
    os.environ["AWS_DEFAULT_REGION"] = AWS_REGION

    if not endpoint_name or not endpoint_name.strip():
        endpoint_name = os.getenv("SAGEMAKER_ENDPOINT_NAME", DEFAULT_ENDPOINT_NAME).strip()

    role_arn = role_arn or os.getenv("SAGEMAKER_ROLE_ARN")
    if not role_arn:
        try:
            from sagemaker.core.helper import IamRoleResolver
            role_arn = IamRoleResolver().create_execution_role(role_type="serving")
        except Exception:
            pass

    print("=" * 70)
    print("Milestone 11 / Step 5: Deploying SageMaker Serverless Embedding Endpoint")
    print(f"  Model ID:        {MODEL_ID}")
    print(f"  Memory Size:     {memory_mb} MB")
    print(f"  Max Concurrency: {max_concurrency}")
    print(f"  AWS Region:      {AWS_REGION}")
    print(f"  Endpoint Name:   {endpoint_name}")
    if role_arn:
        print(f"  Role ARN:        {role_arn}")
    print("  Billing Mode:    Serverless (Scales to 0, zero idle cost, no auto-teardown)")
    print("=" * 70)

    sm_client = boto3.client("sagemaker", region_name=AWS_REGION)

    # Check if endpoint already exists and is InService
    try:
        ep_info = sm_client.describe_endpoint(EndpointName=endpoint_name)
        status = ep_info.get("EndpointStatus")
        print(f"\nFound existing endpoint '{endpoint_name}' with status '{status}'.")
        if status == "InService":
            print(f"Reusing existing active SageMaker Serverless endpoint '{endpoint_name}'.")
            with open(ENDPOINT_TXT_PATH, "w") as f:
                f.write(endpoint_name + "\n")
            print(f"Saved endpoint name '{endpoint_name}' to '{os.path.abspath(ENDPOINT_TXT_PATH)}'")
            print("=" * 70)
            print("SUCCESS: SageMaker Serverless Embedding Endpoint is Live (Reused)!")
            print(f"Endpoint Name: {endpoint_name}")
            print("Status:        InService")
            print("=" * 70)
            return endpoint_name
        elif status in ["Creating", "Updating"]:
            print(f"Endpoint '{endpoint_name}' is currently in '{status}' state. Waiting for InService...")
            while True:
                ep_info = sm_client.describe_endpoint(EndpointName=endpoint_name)
                status = ep_info.get("EndpointStatus")
                print(f"   Endpoint Status: {status}")
                if status == "InService":
                    break
                elif status in ["Failed", "Deleting"]:
                    raise RuntimeError(f"Endpoint deployment ended with failed status: '{status}'")
                time.sleep(15)
            with open(ENDPOINT_TXT_PATH, "w") as f:
                f.write(endpoint_name + "\n")
            print("=" * 70)
            print("SUCCESS: SageMaker Serverless Embedding Endpoint is Live!")
            print(f"Endpoint Name: {endpoint_name}")
            print("Status:        InService")
            print("=" * 70)
            return endpoint_name
    except ClientError as ce:
        error_code = ce.response.get("Error", {}).get("Code", "Unknown")
        error_msg = ce.response.get("Error", {}).get("Message", str(ce))
        if error_code == "AccessDeniedException":
            print("\n[IAM PERMISSION ERROR] Access denied calling DescribeEndpoint.")
            print("Please ensure policy 'AmazonSageMakerFullAccess' is attached to your AWS IAM user/role.")
            raise ce
        elif "Could not find" in error_msg or error_code == "ValidationException":
            print(f"\nEndpoint '{endpoint_name}' does not exist yet. Proceeding with serverless deployment...")
        else:
            print(f"\nDescribeEndpoint warning: {error_msg}. Proceeding with deployment attempt...")

    try:
        # ── Resolve container image via JumpStart ──────────────────────
        from sagemaker.core.jumpstart.artifacts.image_uris import _retrieve_image_uri

        print("\n[1/4] Resolving inference container image...")
        image_uri = _retrieve_image_uri(
            model_id=MODEL_ID, model_version="*",
            image_scope="inference", region=AWS_REGION,
            instance_type="ml.m5.xlarge",           # only used for container lookup
        )
        print(f"   Container: {image_uri}")

        # HuggingFace Hub env vars — container pulls model at startup
        env_vars = {
            "HF_MODEL_ID": "BAAI/bge-large-en-v1.5",
            "HF_TASK": "feature-extraction",
            "SAGEMAKER_CONTAINER_LOG_LEVEL": "20",
            "SAGEMAKER_REGION": AWS_REGION,
        }

        # ── Unique resource names (timestamp-based) ────────────────────
        ts = int(time.time())
        model_name = f"{endpoint_name}-model-{ts}"
        config_name = f"{endpoint_name}-config-{ts}"

        # ── boto3: CreateModel ─────────────────────────────────────────
        print(f"\n[2/4] Creating SageMaker Model '{model_name}'...")
        create_model_params = {
            "ModelName": model_name,
            "PrimaryContainer": {
                "Image": image_uri,
                "Environment": env_vars,
            },
            "EnableNetworkIsolation": False,
        }
        if role_arn:
            create_model_params["ExecutionRoleArn"] = role_arn
        sm_client.create_model(**create_model_params)
        print(f"   Model '{model_name}' created.")

        # ── boto3: CreateEndpointConfig (Serverless) ───────────────────
        print(f"\n[3/4] Creating Serverless EndpointConfig '{config_name}'...")
        sm_client.create_endpoint_config(
            EndpointConfigName=config_name,
            ProductionVariants=[
                {
                    "VariantName": "AllTraffic",
                    "ModelName": model_name,
                    "ServerlessConfig": {
                        "MemorySizeInMB": memory_mb,
                        "MaxConcurrency": max_concurrency,
                    },
                }
            ],
        )
        print(f"   EndpointConfig '{config_name}' created.")

        # ── boto3: CreateEndpoint ──────────────────────────────────────
        print(f"\n[4/4] Creating Serverless Endpoint '{endpoint_name}'...")
        sm_client.create_endpoint(
            EndpointName=endpoint_name,
            EndpointConfigName=config_name,
        )

        # ── Wait for InService ─────────────────────────────────────────
        print("\n   Waiting for endpoint to reach InService (this may take 3-8 minutes)...")
        while True:
            try:
                ep_info = sm_client.describe_endpoint(EndpointName=endpoint_name)
                status = ep_info.get("EndpointStatus")
                print(f"   Endpoint Status: {status}")
                if status == "InService":
                    break
                elif status in ["Failed", "Deleting"]:
                    failure = ep_info.get("FailureReason", "Unknown")
                    raise RuntimeError(
                        f"Endpoint deployment ended with status '{status}': {failure}"
                    )
            except ClientError as ce:
                error_code = ce.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "AccessDeniedException":
                    print("\n[IAM PERMISSION ERROR] Access denied calling DescribeEndpoint.")
                    raise ce
                raise
            time.sleep(15)

        with open(ENDPOINT_TXT_PATH, "w") as f:
            f.write(endpoint_name + "\n")
        print(f"\nSaved endpoint name '{endpoint_name}' to '{os.path.abspath(ENDPOINT_TXT_PATH)}'")

        print("\n" + "=" * 70)
        print("SUCCESS: SageMaker Serverless Embedding Endpoint is Live!")
        print(f"Endpoint Name: {endpoint_name}")
        print("Status:        InService")
        print("Billing:       Serverless (Zero idle cost, persistent)")
        print("=" * 70)
        return endpoint_name

    except Exception as e:
        print(f"\n[ERROR] SageMaker Serverless Endpoint Deployment Failed: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Deploy BGE-large-en-v1.5 embedding model to SageMaker Serverless Inference.")
    parser.add_argument("--name", "--endpoint-name", type=str, help="Custom endpoint name.")
    parser.add_argument("--memory-mb", type=int, default=DEFAULT_MEMORY_MB, help="Serverless memory size in MB (default: 4096).")
    parser.add_argument("--max-concurrency", type=int, default=DEFAULT_MAX_CONCURRENCY, help="Max concurrency limit (default: 10).")
    parser.add_argument("--role-arn", type=str, help="SageMaker execution role ARN (optional).")
    args = parser.parse_args()

    deploy_serverless_endpoint(
        endpoint_name=args.name,
        memory_mb=args.memory_mb,
        max_concurrency=args.max_concurrency,
        role_arn=args.role_arn
    )

if __name__ == "__main__":
    main()
