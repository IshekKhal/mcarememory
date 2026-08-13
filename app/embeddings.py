import json
import logging
import os
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError, BotoCoreError
from app.config import AWS_REGION, EMBEDDING_DIMENSION, EMBEDDING_MODE, get_sagemaker_endpoint_name

logger = logging.getLogger(__name__)

# Lazy-loaded singleton for local sentence-transformers model
_LOCAL_MODEL = None
LOCAL_MODEL_NAME = "BAAI/bge-large-en-v1.5"

def get_local_model():
    """
    Lazy-loads and returns the local SentenceTransformer model instance (singleton).
    Uses BAAI/bge-large-en-v1.5 which applies CLS pooling and L2 normalization by default.
    """
    global _LOCAL_MODEL
    if _LOCAL_MODEL is None:
        logger.info(f"Loading local SentenceTransformer model '{LOCAL_MODEL_NAME}'...")
        from sentence_transformers import SentenceTransformer
        _LOCAL_MODEL = SentenceTransformer(LOCAL_MODEL_NAME)
        logger.info(f"Local SentenceTransformer model '{LOCAL_MODEL_NAME}' loaded successfully.")
    return _LOCAL_MODEL

def _generate_embedding_local(text: str) -> list[float]:
    """Generates a 1024-dim embedding vector using local sentence-transformers model."""
    clean_text = text.strip()
    model = get_local_model()
    # encode() applies model's 1_Pooling config (CLS pooling + L2 normalization) automatically
    vector = model.encode(clean_text, convert_to_numpy=True)
    return [float(x) for x in vector]

def _generate_embeddings_batch_local(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """Generates 1024-dim embedding vectors for a batch of texts using local sentence-transformers model."""
    if not texts:
        return []
    clean_texts = [t.strip() if t and t.strip() else "general note" for t in texts]
    model = get_local_model()
    vectors = model.encode(clean_texts, batch_size=batch_size, convert_to_numpy=True)
    return [[float(x) for x in vec] for vec in vectors]

def get_sagemaker_runtime_client():
    """Returns a boto3 sagemaker-runtime client configured with app region."""
    config = Config(
        retries={
            "max_attempts": 5,
            "mode": "standard"
        }
    )
    return boto3.client("sagemaker-runtime", region_name=AWS_REGION, config=config)

def _generate_embedding_sagemaker(clean_text: str) -> list[float]:
    """Generates a 1024-dimensional embedding vector via SageMaker endpoint."""
    endpoint_name = get_sagemaker_endpoint_name()
    client = get_sagemaker_runtime_client()
    
    payloads_to_try = [
        {"inputs": clean_text},
        {"inputs": [clean_text]},
        {"text_inputs": [clean_text], "mode": "embedding"},
        {"text_inputs": clean_text, "mode": "embedding"}
    ]
    
    response_data = None
    last_exception = None

    for payload in payloads_to_try:
        try:
            response = client.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType="application/json",
                Accept="application/json",
                Body=json.dumps(payload)
            )
            raw_body = response["Body"].read().decode("utf-8")
            response_data = json.loads(raw_body)
            break
        except ClientError as e:
            last_exception = e
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "ModelError" or "400" in str(e):
                continue
            raise

    if response_data is None:
        if last_exception:
            error_code = last_exception.response.get("Error", {}).get("Code", "Unknown")
            error_msg = last_exception.response.get("Error", {}).get("Message", str(last_exception))
            msg = f"SageMaker model error during inference on endpoint '{endpoint_name}': {error_msg}"
            logger.error(msg)
            raise RuntimeError(msg) from last_exception
        raise RuntimeError(f"SageMaker endpoint '{endpoint_name}' returned no response data.")

    # Parse vector from SageMaker response
    embedding = None
    if isinstance(response_data, dict):
        for key in ["embedding", "vectors", "predictions", "embeddings"]:
            if key in response_data:
                response_data = response_data[key]
                break

    if isinstance(response_data, list):
        elem = response_data
        while isinstance(elem, list) and len(elem) > 0 and isinstance(elem[0], list):
            if len(elem[0]) == EMBEDDING_DIMENSION:
                elem = elem[0]
                break
            else:
                num_tokens = len(elem)
                dim = len(elem[0])
                mean_vec = [0.0] * dim
                for tok in elem:
                    for d_idx in range(dim):
                        mean_vec[d_idx] += tok[d_idx]
                elem = [val / num_tokens for val in mean_vec]
                break

        if isinstance(elem, list) and len(elem) == EMBEDDING_DIMENSION:
            embedding = elem
        elif isinstance(elem, list) and len(elem) > 0 and isinstance(elem[0], (float, int)):
            embedding = elem

    if embedding is None:
        raise RuntimeError(f"Could not parse embedding vector from SageMaker response. Raw output structure: {type(response_data)}")
        
    if len(embedding) != EMBEDDING_DIMENSION:
        raise RuntimeError(f"Expected embedding dimension of {EMBEDDING_DIMENSION}, but received {len(embedding)} dimensions.")
        
    return [float(x) for x in embedding]

def _generate_embeddings_batch_sagemaker(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """Generates 1024-dimensional embedding vectors for a batch of input texts using SageMaker."""
    if not texts:
        return []

    all_embeddings = []
    endpoint_name = get_sagemaker_endpoint_name()
    client = get_sagemaker_runtime_client()

    for i in range(0, len(texts), batch_size):
        chunk_raw = texts[i:i + batch_size]
        chunk = [t.strip() if t and t.strip() else "general note" for t in chunk_raw]

        payloads_to_try = [
            {"inputs": chunk},
            {"text_inputs": chunk, "mode": "embedding"}
        ]

        chunk_vectors = None
        for payload in payloads_to_try:
            try:
                response = client.invoke_endpoint(
                    EndpointName=endpoint_name,
                    ContentType="application/json",
                    Accept="application/json",
                    Body=json.dumps(payload)
                )
                raw_body = response["Body"].read().decode("utf-8")
                response_data = json.loads(raw_body)

                if isinstance(response_data, dict):
                    for key in ["embedding", "vectors", "predictions", "embeddings"]:
                        if key in response_data:
                            chunk_vectors = response_data[key]
                            break
                elif isinstance(response_data, list):
                    chunk_vectors = response_data
                break
            except Exception:
                continue

        if isinstance(chunk_vectors, list) and len(chunk_vectors) == len(chunk):
            all_embeddings.extend(chunk_vectors)
        else:
            for t in chunk:
                all_embeddings.append(_generate_embedding_sagemaker(t))

    return all_embeddings

def generate_embedding(text: str) -> list[float]:
    """
    Generates a 1024-dimensional embedding vector for input text.
    Uses local sentence-transformers or SageMaker endpoint based on EMBEDDING_MODE environment variable.
    
    Args:
        text (str): The note or text string to embed.
        
    Returns:
        list[float]: A list of 1024 floating point numbers representing the embedding.
    """
    if not text or not text.strip():
        raise ValueError("Input text for embedding cannot be empty or whitespace.")

    clean_text = text.strip()
    mode = os.getenv("EMBEDDING_MODE", EMBEDDING_MODE).lower().strip()

    if mode == "sagemaker":
        return _generate_embedding_sagemaker(clean_text)
    else:
        embedding = _generate_embedding_local(clean_text)
        if len(embedding) != EMBEDDING_DIMENSION:
            raise RuntimeError(f"Expected embedding dimension of {EMBEDDING_DIMENSION}, but received {len(embedding)} dimensions.")
        return embedding

def generate_embeddings_batch(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """
    Generates 1024-dimensional embedding vectors for a batch of input texts.
    Uses local sentence-transformers or SageMaker endpoint based on EMBEDDING_MODE environment variable.
    
    Args:
        texts (list[str]): List of note strings to embed.
        batch_size (int): Max texts per batch chunk.
        
    Returns:
        list[list[float]]: List of 1024-dim embedding float vectors matching order of input texts.
    """
    if not texts:
        return []

    mode = os.getenv("EMBEDDING_MODE", EMBEDDING_MODE).lower().strip()
    if mode == "sagemaker":
        return _generate_embeddings_batch_sagemaker(texts, batch_size=batch_size)
    else:
        return _generate_embeddings_batch_local(texts, batch_size=batch_size)


