import sys
import os
import math
import numpy as np

# Ensure app module is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.embeddings import _generate_embedding_local, _generate_embedding_sagemaker

TEST_SENTENCE = "Patient took 50mg Lisinopril at 8:00 AM with water and reported blood pressure reading of 120/80 mmHg."

def cosine_similarity(v1, v2):
    arr1 = np.array(v1, dtype=np.float64)
    arr2 = np.array(v2, dtype=np.float64)
    norm1 = np.linalg.norm(arr1)
    norm2 = np.linalg.norm(arr2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(arr1, arr2) / (norm1 * norm2))

def run_parity_check():
    print("=" * 70)
    print("EMBEDDING NUMERICAL PARITY CHECK (Local vs SageMaker)")
    print(f"Test Sentence: '{TEST_SENTENCE}'")
    print("=" * 70)

    print("\n1. Generating embedding via Local SentenceTransformer (BAAI/bge-large-en-v1.5)...")
    vec_local = _generate_embedding_local(TEST_SENTENCE)
    print(f"   Local Vector Dimension: {len(vec_local)}")
    print(f"   First 5 elements (local): {vec_local[:5]}")

    print("\n2. Generating embedding via SageMaker Endpoint...")
    vec_sagemaker = _generate_embedding_sagemaker(TEST_SENTENCE)
    print(f"   SageMaker Vector Dimension: {len(vec_sagemaker)}")
    print(f"   First 5 elements (sagemaker): {vec_sagemaker[:5]}")

    # Convert to numpy arrays for precision calculations
    arr_local = np.array(vec_local, dtype=np.float64)
    arr_sm = np.array(vec_sagemaker, dtype=np.float64)

    cos_sim = cosine_similarity(arr_local, arr_sm)
    max_abs_diff = float(np.max(np.abs(arr_local - arr_sm)))
    mean_abs_diff = float(np.mean(np.abs(arr_local - arr_sm)))
    l2_dist = float(np.linalg.norm(arr_local - arr_sm))

    print("\n" + "=" * 70)
    print("PARITY COMPARISON RESULTS:")
    print(f"  Cosine Similarity:       {cos_sim:.8f}")
    print(f"  Max Absolute Difference: {max_abs_diff:.8e}")
    print(f"  Mean Absolute Diff:      {mean_abs_diff:.8e}")
    print(f"  Euclidean L2 Distance:   {l2_dist:.8e}")
    print("=" * 70)

    if cos_sim >= 0.999:
        print("SUCCESS: Local embeddings match SageMaker embeddings with near-perfect parity! (Cosine Sim ~ 1.0)")
    else:
        print("WARNING: Cosine similarity is below 0.999. Check preprocessing or model configuration.")

    return cos_sim

if __name__ == "__main__":
    run_parity_check()
