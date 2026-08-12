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

def launch_safety_timer(endpoint_name: str, minutes: float):
    """Launches auto_safety_timer.py in the background for the target endpoint."""
    timer_script = os.path.join(os.path.dirname(__file__), "auto_safety_timer.py")
    mins_str = f"{int(minutes)}" if minutes == int(minutes) else f"{minutes}"
    print(f"\n[Auto-Safety-Timer] Launching background safety timer ({mins_str} mins auto-teardown)...")
    cmd = [sys.executable, timer_script, "--minutes", str(minutes), "--endpoint-name", endpoint_name]
    subprocess.Popen(cmd)

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

    raw_timer_env = os.getenv("SAFETY_TIMER_MINUTES")
    if raw_timer_env:
        try:
            timer_minutes = float(raw_timer_env)
        except ValueError:
            timer_minutes = 60.0
    else:
        timer_minutes = 60.0

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
    print("  Billing Mode:    Serverless (Scales to 0, zero idle cost)")
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
            launch_safety_timer(endpoint_name, timer_minutes)
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
            launch_safety_timer(endpoint_name, timer_minutes)
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
        from sagemaker.serve.model_builder import ModelBuilder
        from sagemaker.core.jumpstart.configs import JumpStartConfig
        try:
            from sagemaker.core.serverless_inference_config import ServerlessInferenceConfig
        except ImportError:
            try:
                from sagemaker.serve.serverless.serverless_inference_config import ServerlessInferenceConfig
            except ImportError:
                from sagemaker.serverless import ServerlessInferenceConfig

        print("\n[1/3] Initializing JumpStart model via SageMaker ModelBuilder...")
        jumpstart_config = JumpStartConfig(model_id=MODEL_ID)

        mb_kwargs = {
            "jumpstart_config": jumpstart_config,
        }
        if role_arn:
            mb_kwargs["role_arn"] = role_arn

        model_builder = ModelBuilder.from_jumpstart_config(**mb_kwargs)
        core_model = model_builder.build(model_name=f"{MODEL_ID}-model")
        
        serverless_config = ServerlessInferenceConfig(
            memory_size_in_mb=memory_mb,
            max_concurrency=max_concurrency
        )

        print(f"\n[2/3] Deploying SageMaker Serverless endpoint '{endpoint_name}' (4096MB memory)...")
        endpoint = model_builder.deploy(
            endpoint_name=endpoint_name,
            serverless_inference_config=serverless_config
        )
        deployed_name = getattr(endpoint, "name", getattr(endpoint, "endpoint_name", endpoint_name))

        print("\n[3/3] Verifying endpoint status...")
        while True:
            try:
                ep_info = sm_client.describe_endpoint(EndpointName=deployed_name)
                status = ep_info.get("EndpointStatus")
                print(f"   Endpoint Status: {status}")
                if status == "InService":
                    break
                elif status in ["Failed", "Deleting"]:
                    raise RuntimeError(f"Endpoint deployment ended with failed status: '{status}'")
            except ClientError as ce:
                error_code = ce.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "AccessDeniedException":
                    print("\n[IAM PERMISSION ERROR] Access denied calling DescribeEndpoint.")
                    raise ce
                raise
            time.sleep(15)

        with open(ENDPOINT_TXT_PATH, "w") as f:
            f.write(deployed_name + "\n")
        print(f"\nSaved endpoint name '{deployed_name}' to '{os.path.abspath(ENDPOINT_TXT_PATH)}'")

        launch_safety_timer(deployed_name, timer_minutes)
        print("\n" + "=" * 70)
        print("SUCCESS: SageMaker Serverless Embedding Endpoint is Live!")
        print(f"Endpoint Name: {deployed_name}")
        print("Status:        InService")
        print("Billing:       Serverless (Zero idle cost)")
        print("=" * 70)
        return deployed_name

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
