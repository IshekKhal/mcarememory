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

def deploy_jumpstart_endpoint(endpoint_name: str = None, instance_type: str = DEFAULT_INSTANCE_TYPE, role_arn: str = None):
    """
    Deploys the BAAI/bge-large-en-v1.5 embedding model to a SageMaker endpoint using JumpStart / ModelBuilder.
    Saves the endpoint name to sagemaker_endpoint.txt upon completion.
    """
    os.environ["AWS_DEFAULT_REGION"] = AWS_REGION

    if not endpoint_name:
        timestamp = int(time.time())
        endpoint_name = f"bge-large-en-v1-5-{timestamp}"

    role_arn = role_arn or os.getenv("SAGEMAKER_ROLE_ARN")
    if not role_arn:
        try:
            from sagemaker.core.helper import IamRoleResolver
            role_arn = IamRoleResolver().create_execution_role(role_type="serving")
        except Exception:
            pass

    print("=" * 70)
    print("Milestone 4: Deploying SageMaker Embedding Endpoint")
    print(f"  Model ID:      {MODEL_ID}")
    print(f"  Instance Type: {instance_type}")
    print(f"  AWS Region:    {AWS_REGION}")
    print(f"  Endpoint Name: {endpoint_name}")
    if role_arn:
        print(f"  Role ARN:      {role_arn}")
    print("=" * 70)

    try:
        deployed_name = None

        # 1. Deploy via SageMaker v3 ModelBuilder
        from sagemaker.serve.model_builder import ModelBuilder
        from sagemaker.core.jumpstart.configs import JumpStartConfig
        try:
            from sagemaker.core.training.configs import Compute
        except ImportError:
            from sagemaker.train.configs import Compute

        print("\n[1/3] Initializing JumpStart model via SageMaker v3 ModelBuilder...")
        compute = Compute(instance_type=instance_type)
        jumpstart_config = JumpStartConfig(model_id=MODEL_ID)

        mb_kwargs = {
            "jumpstart_config": jumpstart_config,
            "compute": compute,
        }
        if role_arn:
            mb_kwargs["role_arn"] = role_arn

        model_builder = ModelBuilder.from_jumpstart_config(**mb_kwargs)
        core_model = model_builder.build(model_name=f"{MODEL_ID}-model")

        print(f"\n[2/3] Deploying SageMaker endpoint '{endpoint_name}' on instance '{instance_type}' (this may take 3-5 minutes)...")
        endpoint = model_builder.deploy(endpoint_name=endpoint_name)
        deployed_name = getattr(endpoint, "name", getattr(endpoint, "endpoint_name", endpoint_name))

        # 2. Wait for endpoint to reach InService status
        sm_client = boto3.client("sagemaker", region_name=AWS_REGION)
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
                    print("Please ensure policy 'AmazonSageMakerFullAccess' is attached to your AWS IAM user/role.")
                    raise ce
                raise
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
    parser.add_argument("--role-arn", type=str, help="SageMaker execution role ARN (optional).")
    args = parser.parse_args()

    deploy_jumpstart_endpoint(endpoint_name=args.name, instance_type=args.instance_type, role_arn=args.role_arn)

if __name__ == "__main__":
    main()
