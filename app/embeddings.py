import json
import logging
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError, BotoCoreError
from app.config import AWS_REGION, BEDROCK_MODEL_ID, EMBEDDING_DIMENSION

logger = logging.getLogger(__name__)

def get_bedrock_client():
    """Returns a boto3 bedrock-runtime client configured with app region and defensive retry backoff."""
    config = Config(
        retries={
            "max_attempts": 8,
            "mode": "standard"
        }
    )
    return boto3.client("bedrock-runtime", region_name=AWS_REGION, config=config)

def generate_embedding(text: str) -> list[float]:
    """
    Generates a 1024-dimensional embedding vector for input text using Amazon Titan Text Embeddings V2.
    
    Args:
        text (str): The note or text string to embed.
        
    Returns:
        list[float]: A list of 1024 floating point numbers representing the embedding.

    Raises:
        ValueError: If text is empty or invalid.
        RuntimeError: If Bedrock API invocation fails (bad credentials, region error, throttling, etc.).
    """
    if not text or not text.strip():
        raise ValueError("Input text for embedding cannot be empty or whitespace.")

    clean_text = text.strip()
    
    payload = {
        "inputText": clean_text,
        "dimensions": EMBEDDING_DIMENSION,
        "normalize": True
    }
    
    try:
        client = get_bedrock_client()
        response = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(payload)
        )
        
        response_body = json.loads(response["body"].read().decode("utf-8"))
        
        if "embedding" not in response_body:
            raise RuntimeError(f"Unexpected response structure from Bedrock Titan V2 API: missing 'embedding' key. Keys: {list(response_body.keys())}")
            
        embedding = response_body["embedding"]
        
        if len(embedding) != EMBEDDING_DIMENSION:
            raise RuntimeError(f"Expected embedding dimension of {EMBEDDING_DIMENSION}, but received {len(embedding)} dimensions.")
            
        return embedding

    except NoCredentialsError as e:
        err_msg = (
            "AWS Credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY "
            "environment variables, or configure AWS credentials via AWS CLI/profile."
        )
        logger.error(err_msg)
        raise RuntimeError(err_msg) from e

    except EndpointConnectionError as e:
        err_msg = (
            f"Could not connect to Bedrock endpoint in region '{AWS_REGION}'. "
            "Please check network connectivity or confirm that Titan V2 is available in this AWS region."
        )
        logger.error(err_msg)
        raise RuntimeError(err_msg) from e

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        
        if error_code == "AccessDeniedException":
            msg = f"Access denied to Bedrock model '{BEDROCK_MODEL_ID}'. Ensure your AWS account has model access granted in region '{AWS_REGION}'."
        elif error_code == "ResourceNotFoundException":
            msg = f"Bedrock model '{BEDROCK_MODEL_ID}' not found in region '{AWS_REGION}'. Verify model ID and region configuration."
        elif error_code == "ThrottlingException":
            msg = f"Bedrock API rate limit / throttling exceeded for model '{BEDROCK_MODEL_ID}'."
        elif error_code == "ValidationException":
            msg = f"Validation error invoking Bedrock model '{BEDROCK_MODEL_ID}': {error_msg}"
        else:
            msg = f"Bedrock ClientError [{error_code}]: {error_msg}"
            
        logger.error(msg)
        raise RuntimeError(msg) from e

    except BotoCoreError as e:
        err_msg = f"BotoCore error invoking Bedrock embeddings: {e}"
        logger.error(err_msg)
        raise RuntimeError(err_msg) from e

    except Exception as e:
        err_msg = f"Unexpected error during embedding generation: {e}"
        logger.error(err_msg)
        raise RuntimeError(err_msg) from e
