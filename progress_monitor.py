#!/usr/bin/env python3
"""
Universal Progress Bar Monitor
Reads /tmp/claude_progress.json and renders a live progress bar.

Usage:
    python3 progress_monitor.py [progress_file] [poll_interval]

Progress file format:
    {"current": 726, "total": 2056, "label": "Processing leads", "started_at": 1234567890.0}

Optional fields:
    "status": "running" | "done" | "error"
    "message": "Current item info"
"""

import json
import sys
import time
import os

PROGRESS_FILE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude_progress.json"
POLL_INTERVAL = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0

BAR_WIDTH = 30

def render_bar(current, total, label, started_at, message=""):
    pct = current / total if total > 0 else 0
    filled = int(BAR_WIDTH * pct)
    empty = BAR_WIDTH - filled

    bar = "━" * filled + "░" * empty

    # Speed & ETA
    elapsed = time.time() - started_at
    speed = current / elapsed if elapsed > 0 else 0
    remaining = (total - current) / speed if speed > 0 else 0

    # Format ETA
    if remaining > 3600:
        eta = f"{remaining/3600:.1f}h"
    elif remaining > 60:
        eta = f"{int(remaining//60)}m {int(remaining%60)}s"
    else:
        eta = f"{int(remaining)}s"

    # Format elapsed
    if elapsed > 60:
        elapsed_str = f"{int(elapsed//60)}m {int(elapsed%60)}s"
    else:
        elapsed_str = f"{int(elapsed)}s"

    print(f"\n{'='*50}")
    print(f"  {label}")
    print(f"  {bar}  {current}/{total} ({pct*100:.1f}%)")
    print(f"  Speed: {speed:.1f}/sec | ETA: {eta} | Elapsed: {elapsed_str}")
    if message:
        print(f"  {message}")
    print(f"{'='*50}")
    sys.stdout.flush()


def main():
    print(f"Monitoring: {PROGRESS_FILE}")
    print(f"Waiting for progress data...")
    sys.stdout.flush()

    last_current = -1

    while True:
        try:
            if not os.path.exists(PROGRESS_FILE):
                time.sleep(POLL_INTERVAL)
                continue

            with open(PROGRESS_FILE, "r") as f:
                data = json.load(f)

            current = data.get("current", 0)
            total = data.get("total", 1)
            label = data.get("label", "Processing")
            started_at = data.get("started_at", time.time())
            status = data.get("status", "running")
            message = data.get("message", "")

            # Only render if progress changed
            if current != last_current:
                render_bar(current, total, label, started_at, message)
                last_current = current

            # Check completion
            if status == "done" or current >= total:
                elapsed = time.time() - started_at
                if elapsed > 60:
                    elapsed_str = f"{int(elapsed//60)}m {int(elapsed%60)}s"
                else:
                    elapsed_str = f"{int(elapsed)}s"
                print(f"\n  COMPLETE — {total} items in {elapsed_str}")
                sys.stdout.flush()
                break

            if status == "error":
                print(f"\n  ERROR — {message}")
                sys.stdout.flush()
                break

        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"Monitor error: {e}")
            sys.stdout.flush()

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
