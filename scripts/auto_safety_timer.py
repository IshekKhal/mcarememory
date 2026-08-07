import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import time
import argparse

# Ensure app module is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import AWS_REGION
from scripts.teardown_embedding_endpoint import teardown_endpoint, get_target_endpoint_name

def start_safety_timer(minutes: float = None, endpoint_name: str = None):
    """
    Runs a safety countdown timer.
    When expired, automatically triggers teardown of the active SageMaker embedding endpoint if it exists.
    """
    if minutes is None:
        raw_timer_env = os.getenv("SAFETY_TIMER_MINUTES")
        if raw_timer_env:
            try:
                minutes = float(raw_timer_env)
            except ValueError:
                minutes = 60.0
        else:
            minutes = 60.0

    target_ep = get_target_endpoint_name(endpoint_name)
    total_seconds = int(minutes * 60)
    start_time = time.time()

    mins_display = f"{int(minutes)}" if minutes == int(minutes) else f"{minutes}"

    print("=" * 70)
    print("SAGEMAKER AUTO-TEARDOWN SAFETY TIMER")
    print(f"  Target Endpoint: {target_ep}")
    print(f"  AWS Region:      {AWS_REGION}")
    print(f"  Timer Duration:  {mins_display} minutes ({total_seconds} seconds)")
    print(f"  Started At:      {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")
    print(f"  Auto-Teardown At:{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time + total_seconds))}")
    print("=" * 70)
    print("\nSafety timer active in background. Will teardown SageMaker endpoint when timer expires.\n")

    # Periodic status log interval
    check_interval = max(2, min(60, total_seconds // 10))

    try:
        while True:
            elapsed = time.time() - start_time
            remaining = total_seconds - elapsed

            if remaining <= 0:
                print("\n" * 2 + "!" * 70)
                print(f"SAFETY TIMER EXPIRED ({mins_display} minutes elapsed).")
                print(f"Initiating automatic teardown of SageMaker endpoint '{target_ep}'...")
                print("!" * 70 + "\n")

                teardown_endpoint(endpoint_name=target_ep)

                print("\n" + "=" * 60)
                print(f"SAFETY TIMER: Endpoint '{target_ep}' has been")
                print(f"automatically torn down after {mins_display} minutes. Nothing is running.")
                print("No further AWS charges will be incurred from this endpoint.")
                print("=" * 60 + "\n")
                break

            rem_mins = int(remaining // 60)
            rem_secs = int(remaining % 60)
            print(f"[{time.strftime('%H:%M:%S')}] Safety Timer: {rem_mins}m {rem_secs}s remaining before auto-teardown...")
            time.sleep(min(remaining, check_interval))

    except KeyboardInterrupt:
        print("\nSafety timer cancelled by user (KeyboardInterrupt). Teardown aborted.")
        sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Auto-teardown safety timer for SageMaker embedding endpoint.")
    parser.add_argument("--minutes", type=float, default=None, help="Timer duration in minutes (default: env SAFETY_TIMER_MINUTES or 60).")
    parser.add_argument("--endpoint-name", type=str, default=None, help="Specific endpoint name to target.")
    args = parser.parse_args()

    start_safety_timer(minutes=args.minutes, endpoint_name=args.endpoint_name)

if __name__ == "__main__":
    main()

