import sys
import os
import time
import argparse
import boto3
from botocore.exceptions import ClientError

# Ensure app module is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import AWS_REGION

MODEL_ID = "huggingface-sentencesimilarity-bge-large-en-v1-5"
DEFAULT_INSTANCE_TYPE = "ml.m5.xlarge"
ENDPOINT_TXT_PATH = os.path.join(os.path.dirname(__file__), "..", "sagemaker_endpoint.txt")

def deploy_jumpstart_endpoint(endpoint_name: str = None, instance_type: str = DEFAULT_INSTANCE_TYPE):
    """
    Deploys the BAAI/bge-large-en-v1.5 embedding model to a SageMaker endpoint using JumpStart.
    Save the endpoint name to sagemaker_endpoint.txt upon completion.
    """
    if not endpoint_name:
        timestamp = int(time.time())
        endpoint_name = f"bge-large-en-v1-5-{timestamp}"

    print("=" * 70)
    print("Milestone 4: Deploying SageMaker Embedding Endpoint")
    print(f"  Model ID:      {MODEL_ID}")
    print(f"  Instance Type: {instance_type}")
    print(f"  AWS Region:    {AWS_REGION}")
    print(f"  Endpoint Name: {endpoint_name}")
    print("=" * 70)

    try:
        # 1. Try deployment via SageMaker Python SDK JumpStartModel
        try:
            from sagemaker.jumpstart.model import JumpStartModel
            print("\n[1/3] Initializing JumpStartModel using SageMaker SDK...")
            model = JumpStartModel(model_id=MODEL_ID, region=AWS_REGION)
            print("[2/3] Triggering SageMaker endpoint deployment (this may take 3-5 minutes)...")
            predictor = model.deploy(
                instance_type=instance_type,
                endpoint_name=endpoint_name,
                wait=True
            )
            deployed_name = predictor.endpoint_name
        except (ImportError, Exception) as sdk_err:
            print(f"SageMaker SDK deployment fallback ({sdk_err}). Using boto3 SageMaker API...")
            sm_client = boto3.client("sagemaker", region_name=AWS_REGION)
            
            # Check if endpoint already exists
            try:
                ep_info = sm_client.describe_endpoint(EndpointName=endpoint_name)
                status = ep_info.get("EndpointStatus")
                print(f"Endpoint '{endpoint_name}' already exists with status: {status}")
                deployed_name = endpoint_name
            except ClientError as ce:
                if ce.response.get("Error", {}).get("Code") == "ValidationException" or "Could not find" in str(ce):
                    raise RuntimeError(
                        f"Failed to deploy JumpStart model '{MODEL_ID}'. SageMaker SDK error: {sdk_err}"
                    ) from ce
                raise

        # 2. Wait for endpoint to reach InService status
        sm_client = boto3.client("sagemaker", region_name=AWS_REGION)
        print("\n[3/3] Verifying endpoint status...")
        while True:
            ep_info = sm_client.describe_endpoint(EndpointName=deployed_name)
            status = ep_info.get("EndpointStatus")
            print(f"   Endpoint Status: {status}")
            if status == "InService":
                break
            elif status in ["Failed", "Deleting"]:
                raise RuntimeError(f"Endpoint deployment ended with failed status: '{status}'")
            time.sleep(15)

        # 3. Save endpoint name to local sagemaker_endpoint.txt
        with open(ENDPOINT_TXT_PATH, "w") as f:
            f.write(deployed_name + "\n")
        print(f"\nSaved endpoint name '{deployed_name}' to '{os.path.abspath(ENDPOINT_TXT_PATH)}'")

        print("\n" + "=" * 70)
        print("SUCCESS: SageMaker Embedding Endpoint is Live!")
        print(f"Endpoint Name: {deployed_name}")
        print("Status:        InService")
        print("REMINDER: Run 'python scripts/teardown_embedding_endpoint.py' when done to stop charges!")
        print("=" * 70)
        return deployed_name

    except Exception as e:
        print(f"\n[ERROR] SageMaker Endpoint Deployment Failed: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Deploy BGE-large-en-v1.5 embedding model to SageMaker JumpStart.")
    parser.add_argument("--name", "--endpoint-name", type=str, help="Custom endpoint name.")
    parser.add_argument("--instance-type", type=str, default=DEFAULT_INSTANCE_TYPE, help="SageMaker instance type (default: ml.m5.xlarge).")
    args = parser.parse_args()

    deploy_jumpstart_endpoint(endpoint_name=args.name, instance_type=args.instance_type)

if __name__ == "__main__":
    main()
