import sys
import os
import time
import argparse

# Ensure app module is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import AWS_REGION, SAGEMAKER_ENDPOINT_NAME
from scripts.teardown_embedding_endpoint import teardown_endpoint

def start_safety_timer(minutes: float = 60.0):
    """
    Runs a safety countdown timer.
    When expired, automatically triggers teardown of the active SageMaker embedding endpoint if it exists.
    """
    total_seconds = int(minutes * 60)
    start_time = time.time()
    endpoint_name = SAGEMAKER_ENDPOINT_NAME

    print("=" * 70)
    print("SAGEMAKER AUTO-TEARDOWN SAFETY TIMER")
    print(f"  Target Endpoint: {endpoint_name}")
    print(f"  AWS Region:      {AWS_REGION}")
    print(f"  Timer Duration:  {minutes:.1f} minutes ({total_seconds} seconds)")
    print(f"  Started At:      {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")
    print(f"  Auto-Teardown At:{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time + total_seconds))}")
    print("=" * 70)
    print("\nSafety timer active in background. Will teardown SageMaker endpoint when timer expires.\n")

    # Periodic status log interval
    check_interval = max(5, min(60, total_seconds // 10))

    try:
        while True:
            elapsed = time.time() - start_time
            remaining = total_seconds - elapsed

            if remaining <= 0:
                print("\n" * 2 + "!" * 70)
                print(f"SAFETY TIMER EXPIRED ({minutes} minutes elapsed).")
                print(f"Initiating automatic teardown of SageMaker endpoint '{endpoint_name}'...")
                print("!" * 70 + "\n")
                teardown_endpoint(endpoint_name=endpoint_name)
                break

            print(f"[{time.strftime('%H:%M:%S')}] Safety Timer: {int(remaining // 60)}m {int(remaining % 60)}s remaining before auto-teardown...")
            time.sleep(min(remaining, check_interval))

    except KeyboardInterrupt:
        print("\nSafety timer cancelled by user (KeyboardInterrupt). Teardown aborted.")
        sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Auto-teardown safety timer for SageMaker embedding endpoint.")
    parser.add_argument("--minutes", type=float, default=60.0, help="Timer duration in minutes (default: 60).")
    args = parser.parse_args()

    start_safety_timer(minutes=args.minutes)

if __name__ == "__main__":
    main()
