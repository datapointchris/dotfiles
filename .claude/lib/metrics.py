#!/usr/bin/env python3
"""
Shared metrics library for Claude Code workflows.
Provides functions to write metrics to unified JSONL files.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def get_repo_root() -> Path:
    """Get git repository root directory."""
    import subprocess
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False
    )
    if result.returncode != 0:
        return Path.home() / "dotfiles"
    return Path(result.stdout.strip())


def get_metrics_file() -> Path:
    """Get today's metrics file path."""
    repo_root = get_repo_root()
    metrics_dir = repo_root / ".claude/metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    return metrics_dir / f"command-metrics-{date_str}.jsonl"


def write_metric(entry: dict) -> bool:
    """
    Append metric entry to today's JSONL file.

    Args:
        entry: Metric dictionary (must include timestamp, session_id, type, cwd)

    Returns:
        True if successful, False otherwise (never raises)
    """
    try:
        # Validate required fields
        required = ["timestamp", "session_id", "type", "cwd"]
        for field in required:
            if field not in entry:
                print(f"⚠️ Metric missing required field: {field}", file=sys.stderr)
                return False

        metrics_file = get_metrics_file()

        with open(metrics_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')

        return True

    except Exception as e:
        print(f"⚠️ Failed to write metric: {e}", file=sys.stderr)
        return False


def create_base_entry(session_id: str, metric_type: str) -> dict:
    """
    Create base metric entry with common fields.

    Args:
        session_id: Claude Code session ID
        metric_type: Type of metric (logsift, commit-agent, etc)

    Returns:
        Dictionary with timestamp, session_id, type, cwd
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "type": metric_type,
        "cwd": os.getcwd()
    }
