import json
import logging
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError, BotoCoreError
from app.config import AWS_REGION, EMBEDDING_DIMENSION, get_sagemaker_endpoint_name

logger = logging.getLogger(__name__)

def get_sagemaker_runtime_client():
    """Returns a boto3 sagemaker-runtime client configured with app region."""
    config = Config(
        retries={
            "max_attempts": 5,
            "mode": "standard"
        }
    )
    return boto3.client("sagemaker-runtime", region_name=AWS_REGION, config=config)

def generate_embedding(text: str) -> list[float]:
    """
    Generates a 1024-dimensional embedding vector for input text using SageMaker-hosted BGE-large-en-v1.5.
    
    Args:
        text (str): The note or text string to embed.
        
    Returns:
        list[float]: A list of 1024 floating point numbers representing the embedding.

    Raises:
        ValueError: If text is empty or invalid.
        RuntimeError: If SageMaker endpoint invocation fails (bad credentials, region error, non-existent endpoint, etc.).
    """
    if not text or not text.strip():
        raise ValueError("Input text for embedding cannot be empty or whitespace.")

    clean_text = text.strip()
    endpoint_name = get_sagemaker_endpoint_name()
    
    payload = {
        "text_inputs": [clean_text],
        "mode": "embedding"
    }
    
    try:
        client = get_sagemaker_runtime_client()
        response = client.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="application/json",
            Accept="application/json",
            Body=json.dumps(payload)
        )
        
        raw_body = response["Body"].read().decode("utf-8")
        response_data = json.loads(raw_body)
        
        # Parse vector from SageMaker response
        embedding = None
        if isinstance(response_data, dict):
            for key in ["embedding", "vectors", "predictions"]:
                if key in response_data:
                    val = response_data[key]
                    if isinstance(val, list) and len(val) > 0 and isinstance(val[0], list):
                        embedding = val[0]
                    elif isinstance(val, list):
                        embedding = val
                    break
        elif isinstance(response_data, list):
            if len(response_data) > 0 and isinstance(response_data[0], list):
                embedding = response_data[0]
            elif len(response_data) > 0 and isinstance(response_data[0], (float, int)):
                embedding = response_data

        if embedding is None:
            raise RuntimeError(f"Could not parse embedding vector from SageMaker response. Raw output structure: {type(response_data)}")
            
        if len(embedding) != EMBEDDING_DIMENSION:
            raise RuntimeError(f"Expected embedding dimension of {EMBEDDING_DIMENSION}, but received {len(embedding)} dimensions.")
            
        return [float(x) for x in embedding]

    except NoCredentialsError as e:
        err_msg = (
            "AWS Credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY "
            "environment variables, or configure AWS credentials via AWS CLI/profile."
        )
        logger.error(err_msg)
        raise RuntimeError(err_msg) from e

    except EndpointConnectionError as e:
        err_msg = (
            f"Could not connect to SageMaker endpoint '{endpoint_name}' in region '{AWS_REGION}'. "
            "Please check network connectivity or confirm the endpoint region."
        )
        logger.error(err_msg)
        raise RuntimeError(err_msg) from e

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        
        if error_code == "ValidationError" or "Could not resolve" in error_msg:
            msg = f"SageMaker endpoint '{endpoint_name}' not found or not in 'InService' state in region '{AWS_REGION}'. Please deploy the endpoint first using scripts/deploy_embedding_endpoint.py."
        elif error_code == "AccessDeniedException":
            msg = f"Access denied invoking SageMaker endpoint '{endpoint_name}'. Ensure your IAM role/user has 'sagemaker:InvokeEndpoint' permissions."
        elif error_code == "ModelError":
            msg = f"SageMaker model error during inference on endpoint '{endpoint_name}': {error_msg}"
        else:
            msg = f"SageMaker ClientError [{error_code}]: {error_msg}"
            
        logger.error(msg)
        raise RuntimeError(msg) from e

    except BotoCoreError as e:
        err_msg = f"BotoCore error invoking SageMaker endpoint '{endpoint_name}': {e}"
        logger.error(err_msg)
        raise RuntimeError(err_msg) from e

    except Exception as e:
        err_msg = f"Unexpected error during embedding generation via SageMaker: {e}"
        logger.error(err_msg)
        raise RuntimeError(err_msg) from e

