import sys
import os
import argparse
import boto3
from botocore.exceptions import ClientError

# Ensure app module is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import AWS_REGION

ENDPOINT_TXT_PATH = os.path.join(os.path.dirname(__file__), "..", "sagemaker_endpoint.txt")

def get_target_endpoint_name(custom_name: str = None) -> str:
    """Resolves target endpoint name from argument, sagemaker_endpoint.txt, env var, or default."""
    if custom_name and custom_name.strip():
        return custom_name.strip()

    if os.path.exists(ENDPOINT_TXT_PATH):
        with open(ENDPOINT_TXT_PATH, "r") as f:
            val = f.read().strip()
            if val:
                return val

    env_name = os.getenv("SAGEMAKER_ENDPOINT_NAME")
    if env_name and env_name.strip():
        return env_name.strip()

    return "caregiver-bge-embeddings"

def teardown_endpoint(endpoint_name: str = None):
    """
    Deletes the target SageMaker endpoint and its EndpointConfig.
    Removes sagemaker_endpoint.txt upon completion.
    """
    target = get_target_endpoint_name(endpoint_name)

    print("=" * 70)
    print("Milestone 4: Teardown SageMaker Embedding Endpoint")
    print(f"  AWS Region:          {AWS_REGION}")
    print(f"  Target Endpoint:     {target or 'Not Found'}")
    print("=" * 70)

    if not target:
        print("\nNo endpoint name found in sagemaker_endpoint.txt or SAGEMAKER_ENDPOINT_NAME env var.")
        print("Nothing to tear down.")
        return

    sm_client = boto3.client("sagemaker", region_name=AWS_REGION)

    # 1. Fetch EndpointConfigName before deletion if endpoint exists
    config_name = None
    try:
        ep_info = sm_client.describe_endpoint(EndpointName=target)
        config_name = ep_info.get("EndpointConfigName")
        status = ep_info.get("EndpointStatus")
        print(f"\n[1/3] Found endpoint '{target}' (Status: {status})")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ValidationException" or "Could not find" in str(e):
            print(f"\nEndpoint '{target}' does not exist in region '{AWS_REGION}' (already deleted or never created).")
        else:
            print(f"\n[WARNING] Error describing endpoint '{target}': {e}")

    # 2. Delete Endpoint
    print(f"[2/3] Deleting SageMaker endpoint '{target}'...")
    try:
        sm_client.delete_endpoint(EndpointName=target)
        print(f"   Submitted delete request for endpoint '{target}'.")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ValidationException" or "Could not find" in str(e):
            print(f"   Endpoint '{target}' already deleted.")
        else:
            print(f"   [ERROR] Failed deleting endpoint '{target}': {e}")

    # 3. Delete EndpointConfig if found
    if config_name:
        print(f"[3/3] Deleting SageMaker endpoint config '{config_name}'...")
        try:
            sm_client.delete_endpoint_config(EndpointConfigName=config_name)
            print(f"   Deleted endpoint config '{config_name}'.")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "ValidationException" or "Could not find" in str(e):
                print(f"   Endpoint config '{config_name}' already deleted.")
            else:
                print(f"   [WARNING] Failed deleting endpoint config '{config_name}': {e}")

    # 4. Remove local sagemaker_endpoint.txt file
    if os.path.exists(ENDPOINT_TXT_PATH):
        try:
            os.remove(ENDPOINT_TXT_PATH)
            print(f"\nRemoved local state file '{os.path.abspath(ENDPOINT_TXT_PATH)}'")
        except Exception as e:
            print(f"Warning: Failed removing '{ENDPOINT_TXT_PATH}': {e}")

    print("\n" + "=" * 70)
    print("SUCCESS: Endpoint Teardown Complete!")
    print(f"Endpoint '{target}' deletion process initiated.")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="Delete SageMaker embedding endpoint and configuration.")
    parser.add_argument("--name", "--endpoint-name", type=str, help="Specific endpoint name to delete.")
    args = parser.parse_args()

    teardown_endpoint(endpoint_name=args.name)

if __name__ == "__main__":
    main()
