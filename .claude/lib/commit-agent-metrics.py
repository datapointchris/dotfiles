#!/usr/bin/env python3
"""
Helper script for commit agent to report metrics.
Called with metrics as command-line arguments.
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from metrics import create_base_entry, write_metric


def main():
    if len(sys.argv) < 2:
        print("Usage: commit-agent-metrics.py <json-metrics>", file=sys.stderr)
        sys.exit(1)

    try:
        # Parse metrics JSON from argument
        metrics_data = json.loads(sys.argv[1])

        # Get session ID
        session_id = metrics_data.get("session_id", "unknown")

        # Create entry
        entry = create_base_entry(session_id, "commit-agent")

        # Remove session_id from metrics_data to avoid duplication
        if "session_id" in metrics_data:
            del metrics_data["session_id"]

        # Merge with additional metrics
        entry.update(metrics_data)

        # Write metric
        if write_metric(entry):
            print("📊 Commit agent metrics logged", file=sys.stderr)
        else:
            print("⚠️ Failed to log commit agent metrics", file=sys.stderr)
            sys.exit(1)

    except json.JSONDecodeError as e:
        print(f"⚠️ Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"⚠️ Commit agent metrics failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
