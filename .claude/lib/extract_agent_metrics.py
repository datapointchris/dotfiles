#!/usr/bin/env python3
"""
Extract comprehensive metrics from Claude Code agent transcripts.

This library parses agent transcripts to extract all available metrics including:
- Token usage (input, output, cache)
- Execution timing and performance
- Tool usage patterns
- Git/commit specific metrics
- Quality indicators

Usage:
    # From hook context (recommended)
    python extract_agent_metrics.py --context-file /tmp/claude-agent-context-{session_id}.json

    # From known agent transcript
    python extract_agent_metrics.py --agent-transcript ~/.claude/projects/.../agent-xyz.jsonl

    # Output to specific file
    python extract_agent_metrics.py --context-file ... --output metrics.jsonl
"""

import json
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any
from datetime import datetime
import re
import subprocess


@dataclass
class TokenMetrics:
    """Token usage metrics."""
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0

    # Cache breakdown by tier
    cache_5m_tokens: int = 0
    cache_1h_tokens: int = 0

    # Calculated metrics
    cache_hit_rate: float = 0.0
    cache_creation_rate: float = 0.0

    # Per-message statistics
    max_input_tokens: int = 0
    max_output_tokens: int = 0
    avg_input_tokens: float = 0.0
    avg_output_tokens: float = 0.0


@dataclass
class ExecutionMetrics:
    """Execution timing and performance metrics."""
    total_duration_ms: Optional[int] = None
    start_timestamp: Optional[str] = None
    end_timestamp: Optional[str] = None

    # Tool usage
    total_tool_uses: int = 0
    tool_types: Dict[str, int] = field(default_factory=dict)

    # Message counts
    assistant_messages: int = 0
    user_messages: int = 0
    tool_result_messages: int = 0
    thinking_blocks: int = 0

    # API metrics
    total_requests: int = 0
    unique_request_ids: List[str] = field(default_factory=list)

    # Stop reasons
    stop_reasons: Dict[str, int] = field(default_factory=dict)


@dataclass
class GitMetrics:
    """Git and commit-specific metrics."""
    commits_created: int = 0
    commit_hashes: List[str] = field(default_factory=list)
    commit_messages: List[str] = field(default_factory=list)

    # File changes
    files_changed: int = 0
    files_created: int = 0
    files_modified: int = 0
    files_deleted: int = 0
    files_renamed: int = 0

    # Git operations
    git_commands: List[str] = field(default_factory=list)
    git_status_checks: int = 0
    git_diff_checks: int = 0
    git_log_checks: int = 0


@dataclass
class PreCommitMetrics:
    """Pre-commit hook metrics."""
    total_runs: int = 0
    background_runs: int = 0
    logsift_runs: int = 0

    # Success/failure tracking
    successful_runs: int = 0
    failed_runs: int = 0

    # Errors found
    total_errors: int = 0
    total_warnings: int = 0

    # Iterations
    max_iterations: int = 0


@dataclass
class QualityMetrics:
    """Quality and compliance indicators."""
    # Phase execution (commit-agent specific)
    phases_executed: List[str] = field(default_factory=list)

    # Instruction compliance
    read_own_instructions: bool = False

    # Error patterns
    error_messages: List[str] = field(default_factory=list)
    warning_messages: List[str] = field(default_factory=list)

    # Retry patterns
    retried_tools: Dict[str, int] = field(default_factory=dict)

    # Logsift usage
    logsift_invocations: int = 0
    logsift_errors_found: int = 0
    logsift_warnings_found: int = 0


@dataclass
class ModelMetrics:
    """Model and API details."""
    model_name: str = "unknown"
    model_version: str = "unknown"
    service_tier: str = "standard"

    # Context management
    context_edits_applied: int = 0
    auto_compaction_occurred: bool = False


@dataclass
class AgentMetrics:
    """Complete metrics for an agent execution."""
    # Identity (required fields)
    agent_id: str
    session_id: str
    timestamp: str

    # Context (optional fields with defaults)
    agent_slug: str = "unknown"
    cwd: str = "unknown"
    git_branch: str = "unknown"
    claude_version: str = "unknown"

    # Transcript locations
    agent_transcript_path: str = "unknown"
    parent_transcript_path: str = "unknown"

    # Metric categories
    tokens: TokenMetrics = field(default_factory=TokenMetrics)
    execution: ExecutionMetrics = field(default_factory=ExecutionMetrics)
    git: GitMetrics = field(default_factory=GitMetrics)
    pre_commit: PreCommitMetrics = field(default_factory=PreCommitMetrics)
    quality: QualityMetrics = field(default_factory=QualityMetrics)
    model: ModelMetrics = field(default_factory=ModelMetrics)

    # Raw data for advanced analysis
    raw_tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    raw_usage_data: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary, handling nested dataclasses."""
        result = {}
        for key, value in asdict(self).items():
            if key.startswith('raw_'):
                # Skip raw data in output (too verbose)
                continue
            result[key] = value
        return result


class TranscriptParser:
    """Parse JSONL transcript files."""

    def __init__(self, transcript_path: Path):
        self.transcript_path = transcript_path
        self.messages: List[dict] = []

    def parse(self) -> List[dict]:
        """Parse transcript file into list of messages."""
        if not self.transcript_path.exists():
            raise FileNotFoundError(f"Transcript not found: {self.transcript_path}")

        messages = []
        with open(self.transcript_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    msg = json.loads(line)
                    messages.append(msg)
                except json.JSONDecodeError as e:
                    print(f"Warning: Failed to parse line {line_num}: {e}", file=sys.stderr)
                    continue

        self.messages = messages
        return messages


class MetricsExtractor:
    """Extract metrics from parsed transcript messages."""

    def __init__(self, messages: List[dict], agent_id: str, session_id: str):
        self.messages = messages
        self.agent_id = agent_id
        self.session_id = session_id

    def extract(self) -> AgentMetrics:
        """Extract all available metrics."""
        metrics = AgentMetrics(
            agent_id=self.agent_id,
            session_id=self.session_id,
            timestamp=datetime.now().isoformat()
        )

        # Extract from first message (contains metadata)
        if self.messages:
            first_msg = self.messages[0]
            metrics.agent_slug = first_msg.get('slug', 'unknown')
            metrics.cwd = first_msg.get('cwd', 'unknown')
            metrics.git_branch = first_msg.get('gitBranch', 'unknown')
            metrics.claude_version = first_msg.get('version', 'unknown')

        # Process all messages
        self._extract_token_metrics(metrics)
        self._extract_execution_metrics(metrics)
        self._extract_git_metrics(metrics)
        self._extract_pre_commit_metrics(metrics)
        self._extract_quality_metrics(metrics)
        self._extract_model_metrics(metrics)

        # Calculate derived metrics
        self._calculate_token_rates(metrics)
        self._calculate_timing_metrics(metrics)

        return metrics

    def _extract_token_metrics(self, metrics: AgentMetrics):
        """Extract token usage from all messages."""
        token_counts = []
        input_tokens_list = []
        output_tokens_list = []

        for msg in self.messages:
            usage = msg.get('message', {}).get('usage', {})
            if not usage:
                # Try toolUseResult for final summary
                usage = msg.get('toolUseResult', {}).get('usage', {})

            if usage:
                metrics.raw_usage_data.append(usage)

                # Accumulate tokens
                input_tok = usage.get('input_tokens', 0)
                output_tok = usage.get('output_tokens', 0)
                cache_create = usage.get('cache_creation_input_tokens', 0)
                cache_read = usage.get('cache_read_input_tokens', 0)

                metrics.tokens.input_tokens += input_tok
                metrics.tokens.output_tokens += output_tok
                metrics.tokens.cache_creation_tokens += cache_create
                metrics.tokens.cache_read_tokens += cache_read

                input_tokens_list.append(input_tok)
                output_tokens_list.append(output_tok)

                # Cache tier breakdown
                cache_creation = usage.get('cache_creation', {})
                metrics.tokens.cache_5m_tokens += cache_creation.get('ephemeral_5m_input_tokens', 0)
                metrics.tokens.cache_1h_tokens += cache_creation.get('ephemeral_1h_input_tokens', 0)

        # Total tokens
        metrics.tokens.total_tokens = (
            metrics.tokens.input_tokens +
            metrics.tokens.output_tokens +
            metrics.tokens.cache_creation_tokens +
            metrics.tokens.cache_read_tokens
        )

        # Statistics
        if input_tokens_list:
            metrics.tokens.max_input_tokens = max(input_tokens_list)
            metrics.tokens.avg_input_tokens = sum(input_tokens_list) / len(input_tokens_list)

        if output_tokens_list:
            metrics.tokens.max_output_tokens = max(output_tokens_list)
            metrics.tokens.avg_output_tokens = sum(output_tokens_list) / len(output_tokens_list)

    def _calculate_token_rates(self, metrics: AgentMetrics):
        """Calculate cache hit rates and other derived metrics."""
        total_input = metrics.tokens.input_tokens + metrics.tokens.cache_read_tokens
        if total_input > 0:
            metrics.tokens.cache_hit_rate = metrics.tokens.cache_read_tokens / total_input

        total_cache = metrics.tokens.cache_creation_tokens + metrics.tokens.cache_read_tokens
        if total_cache > 0:
            metrics.tokens.cache_creation_rate = metrics.tokens.cache_creation_tokens / total_cache

    def _extract_execution_metrics(self, metrics: AgentMetrics):
        """Extract execution timing and tool usage."""
        timestamps = []

        for msg in self.messages:
            # Timestamp
            ts = msg.get('timestamp')
            if ts:
                timestamps.append(ts)

            # Message type
            msg_type = msg.get('type')
            if msg_type == 'assistant':
                metrics.execution.assistant_messages += 1
            elif msg_type == 'user':
                metrics.execution.user_messages += 1

            # Request ID
            req_id = msg.get('requestId')
            if req_id and req_id not in metrics.execution.unique_request_ids:
                metrics.execution.unique_request_ids.append(req_id)
                metrics.execution.total_requests += 1

            # Tool usage
            message_content = msg.get('message', {})
            if isinstance(message_content, dict):
                content = message_content.get('content', [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            # Tool use
                            if item.get('type') == 'tool_use':
                                tool_name = item.get('name', 'unknown')
                                metrics.execution.tool_types[tool_name] = \
                                    metrics.execution.tool_types.get(tool_name, 0) + 1
                                metrics.execution.total_tool_uses += 1

                                # Store raw tool call
                                metrics.raw_tool_calls.append({
                                    'tool': tool_name,
                                    'input': item.get('input', {}),
                                    'timestamp': ts
                                })

                            # Thinking blocks
                            elif item.get('type') == 'thinking':
                                metrics.execution.thinking_blocks += 1

                # Stop reason
                stop_reason = message_content.get('stop_reason')
                if stop_reason:
                    metrics.execution.stop_reasons[stop_reason] = \
                        metrics.execution.stop_reasons.get(stop_reason, 0) + 1

            # Tool results count
            if msg.get('toolUseResult'):
                metrics.execution.tool_result_messages += 1

                # Duration from toolUseResult
                duration = msg.get('toolUseResult', {}).get('totalDurationMs')
                if duration and not metrics.execution.total_duration_ms:
                    metrics.execution.total_duration_ms = duration

        # Start/end timestamps
        if timestamps:
            metrics.execution.start_timestamp = min(timestamps)
            metrics.execution.end_timestamp = max(timestamps)

    def _calculate_timing_metrics(self, metrics: AgentMetrics):
        """Calculate timing-based metrics."""
        # Could add: duration between first and last message
        # Could add: average time per tool call
        # Could add: slowest tool calls
        pass

    def _extract_git_metrics(self, metrics: AgentMetrics):
        """Extract git and commit specific metrics."""
        for msg in self.messages:
            # Look for tool calls
            message_content = msg.get('message', {})
            if isinstance(message_content, dict):
                content = message_content.get('content', [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'tool_use':
                            if item.get('name') == 'Bash':
                                command = item.get('input', {}).get('command', '')

                                # Track git commands
                                if 'git ' in command:
                                    metrics.git.git_commands.append(command)

                                    # Count specific operations
                                    if 'git status' in command:
                                        metrics.git.git_status_checks += 1
                                    elif 'git diff' in command:
                                        metrics.git.git_diff_checks += 1
                                    elif 'git log' in command:
                                        metrics.git.git_log_checks += 1
                                    elif 'git commit' in command:
                                        metrics.git.commits_created += 1

            # Look for tool results with git output
            tool_result = msg.get('toolUseResult', {})
            if tool_result:
                stdout = tool_result.get('stdout', '')

                # Extract commit hashes (40 char hex)
                commit_hash_pattern = r'\b[0-9a-f]{40}\b'
                commit_short_pattern = r'\b[0-9a-f]{7}\b'

                full_hashes = re.findall(commit_hash_pattern, stdout)
                short_hashes = re.findall(commit_short_pattern, stdout)

                for h in full_hashes:
                    if h not in metrics.git.commit_hashes:
                        metrics.git.commit_hashes.append(h[:7])  # Store short form

                for h in short_hashes:
                    if h not in metrics.git.commit_hashes and len(h) == 7:
                        metrics.git.commit_hashes.append(h)

                # Parse git diff --name-status output
                if 'A\t' in stdout or 'M\t' in stdout or 'D\t' in stdout or 'R\t' in stdout:
                    for line in stdout.split('\n'):
                        if line.startswith('A\t'):
                            metrics.git.files_created += 1
                        elif line.startswith('M\t'):
                            metrics.git.files_modified += 1
                        elif line.startswith('D\t'):
                            metrics.git.files_deleted += 1
                        elif line.startswith('R'):
                            metrics.git.files_renamed += 1

                # Total files changed
                metrics.git.files_changed = (
                    metrics.git.files_created +
                    metrics.git.files_modified +
                    metrics.git.files_deleted +
                    metrics.git.files_renamed
                )

    def _extract_pre_commit_metrics(self, metrics: AgentMetrics):
        """Extract pre-commit hook metrics."""
        for msg in self.messages:
            # Look for pre-commit commands
            message_content = msg.get('message', {})
            if isinstance(message_content, dict):
                content = message_content.get('content', [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'tool_use':
                            if item.get('name') == 'Bash':
                                command = item.get('input', {}).get('command', '')

                                if 'pre-commit run' in command:
                                    metrics.pre_commit.total_runs += 1

                                    # Background run (suppressed output)
                                    if '> /dev/null 2>&1' in command or '|| true' in command:
                                        metrics.pre_commit.background_runs += 1

                                # Logsift runs
                                if 'logsift' in command and 'pre-commit' in command:
                                    metrics.pre_commit.logsift_runs += 1

            # Parse logsift output for errors/warnings
            tool_result = msg.get('toolUseResult', {})
            if tool_result:
                stdout = tool_result.get('stdout', '')

                if 'total_errors:' in stdout:
                    # Parse logsift YAML output
                    error_match = re.search(r'total_errors:\s*(\d+)', stdout)
                    warning_match = re.search(r'total_warnings:\s*(\d+)', stdout)

                    if error_match:
                        errors = int(error_match.group(1))
                        metrics.pre_commit.total_errors += errors
                        if errors == 0:
                            metrics.pre_commit.successful_runs += 1
                        else:
                            metrics.pre_commit.failed_runs += 1

                    if warning_match:
                        metrics.pre_commit.total_warnings += int(warning_match.group(1))

        # Calculate max iterations
        metrics.pre_commit.max_iterations = max(
            metrics.pre_commit.total_runs,
            metrics.pre_commit.max_iterations
        )

    def _extract_quality_metrics(self, metrics: AgentMetrics):
        """Extract quality and compliance metrics."""
        # Track phases (commit-agent specific)
        phases_seen = set()

        for msg in self.messages:
            message_content = msg.get('message', {})
            if isinstance(message_content, dict):
                content = message_content.get('content', [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            text = item.get('text', '')

                            # Detect phases
                            if 'Phase 1:' in text or 'Phase 1 -' in text:
                                phases_seen.add('phase_1')
                            if 'Phase 2:' in text or 'Phase 2 -' in text:
                                phases_seen.add('phase_2')
                            if 'Phase 3:' in text or 'Phase 3 -' in text:
                                phases_seen.add('phase_3')
                            if 'Phase 4:' in text or 'Phase 4 -' in text:
                                phases_seen.add('phase_4')
                            if 'Phase 5:' in text or 'Phase 5 -' in text:
                                phases_seen.add('phase_5')
                            if 'Phase 6:' in text or 'Phase 6 -' in text:
                                phases_seen.add('phase_6')
                            if 'Phase 7:' in text or 'Phase 7 -' in text:
                                phases_seen.add('phase_7')

                        # Check if agent read its own instructions
                        if isinstance(item, dict) and item.get('type') == 'tool_use':
                            if item.get('name') == 'Read':
                                file_path = item.get('input', {}).get('file_path', '')
                                if 'commit-agent.md' in file_path:
                                    metrics.quality.read_own_instructions = True

                        # Logsift usage
                        if isinstance(item, dict) and item.get('type') == 'tool_use':
                            if item.get('name') == 'Bash':
                                command = item.get('input', {}).get('command', '')
                                if 'logsift' in command:
                                    metrics.quality.logsift_invocations += 1

            # Extract errors from tool results
            tool_result = msg.get('toolUseResult', {})
            if tool_result:
                stderr = tool_result.get('stderr', '')
                if stderr:
                    # Check for error patterns
                    if 'error' in stderr.lower():
                        metrics.quality.error_messages.append(stderr[:200])  # Truncate
                    if 'warning' in stderr.lower():
                        metrics.quality.warning_messages.append(stderr[:200])

        metrics.quality.phases_executed = sorted(list(phases_seen))

    def _extract_model_metrics(self, metrics: AgentMetrics):
        """Extract model and API details."""
        for msg in self.messages:
            message_content = msg.get('message', {})
            if isinstance(message_content, dict):
                model = message_content.get('model')
                if model:
                    metrics.model.model_name = model
                    # Extract version from model string
                    if 'sonnet' in model.lower():
                        metrics.model.model_version = 'sonnet-4.5'
                    elif 'opus' in model.lower():
                        metrics.model.model_version = 'opus-4'

                usage = message_content.get('usage', {})
                if usage:
                    tier = usage.get('service_tier', 'standard')
                    if metrics.model.service_tier == 'standard':
                        metrics.model.service_tier = tier

                # Context management
                context_mgmt = message_content.get('context_management', {})
                if context_mgmt:
                    edits = context_mgmt.get('applied_edits', [])
                    metrics.model.context_edits_applied += len(edits)


def get_agent_id_from_parent(parent_transcript: Path) -> Optional[str]:
    """
    Extract agentId from parent transcript using fast tail + grep.

    Args:
        parent_transcript: Path to parent session transcript

    Returns:
        Agent ID string or None if not found
    """
    try:
        # Use tail + grep -o to extract just the agentId value
        cmd = f'tail -200 "{parent_transcript}" | grep -o \'"agentId":"[^"]*"\' | tail -1 | cut -d\'"\' -f4'
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )

        agent_id = result.stdout.strip()
        if agent_id and len(agent_id) == 8:  # Agent IDs are 8 chars
            return agent_id

        # Fallback: parse last few lines manually
        with open(parent_transcript, 'r') as f:
            lines = f.readlines()
            # Check last 200 lines (more than before)
            for line in reversed(lines[-200:]):
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line)
                    # Check for agentId in message
                    if 'agentId' in msg:
                        aid = msg['agentId']
                        if aid and len(str(aid)) == 8:
                            return str(aid)
                    # Check in toolUseResult
                    tool_result = msg.get('toolUseResult', {})
                    if isinstance(tool_result, dict) and 'agentId' in tool_result:
                        aid = tool_result['agentId']
                        if aid and len(str(aid)) == 8:
                            return str(aid)
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

        return None

    except Exception as e:
        print(f"Warning: Failed to extract agentId: {e}", file=sys.stderr)
        return None


def extract_from_hook_context(context_file: Path) -> Optional[AgentMetrics]:
    """
    Extract metrics using PostToolUse hook context.

    This is the recommended approach:
    1. Read hook context to get parent transcript path
    2. Extract agentId from parent transcript
    3. Construct agent transcript path
    4. Parse agent transcript and extract metrics

    Args:
        context_file: Path to /tmp/claude-agent-context-{session_id}.json

    Returns:
        AgentMetrics or None if extraction fails
    """
    if not context_file.exists():
        print(f"Error: Hook context file not found: {context_file}", file=sys.stderr)
        return None

    # Read hook context
    try:
        with open(context_file, 'r') as f:
            context = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse hook context: {e}", file=sys.stderr)
        return None

    session_id = context.get('session_id')
    parent_transcript_path = context.get('transcript_path')

    if not session_id or not parent_transcript_path:
        print("Error: Hook context missing session_id or transcript_path", file=sys.stderr)
        return None

    parent_transcript = Path(parent_transcript_path)
    if not parent_transcript.exists():
        print(f"Error: Parent transcript not found: {parent_transcript}", file=sys.stderr)
        return None

    # Extract agentId from parent transcript
    agent_id = get_agent_id_from_parent(parent_transcript)
    if not agent_id:
        print("Error: Could not find agentId in parent transcript", file=sys.stderr)
        return None

    # Construct agent transcript path
    project_dir = parent_transcript.parent
    agent_transcript = project_dir / f"agent-{agent_id}.jsonl"

    if not agent_transcript.exists():
        print(f"Error: Agent transcript not found: {agent_transcript}", file=sys.stderr)
        return None

    # Parse and extract metrics
    parser = TranscriptParser(agent_transcript)
    messages = parser.parse()

    extractor = MetricsExtractor(messages, agent_id, session_id)
    metrics = extractor.extract()

    # Set transcript paths
    metrics.agent_transcript_path = str(agent_transcript)
    metrics.parent_transcript_path = str(parent_transcript)

    return metrics


def extract_from_agent_transcript(agent_transcript: Path) -> Optional[AgentMetrics]:
    """
    Extract metrics directly from known agent transcript.

    Args:
        agent_transcript: Path to agent-{id}.jsonl file

    Returns:
        AgentMetrics or None if extraction fails
    """
    if not agent_transcript.exists():
        print(f"Error: Agent transcript not found: {agent_transcript}", file=sys.stderr)
        return None

    # Parse transcript
    parser = TranscriptParser(agent_transcript)
    messages = parser.parse()

    if not messages:
        print("Error: No messages found in transcript", file=sys.stderr)
        return None

    # Extract IDs from first message
    first_msg = messages[0]
    agent_id = first_msg.get('agentId', 'unknown')
    session_id = first_msg.get('sessionId', 'unknown')

    # Extract metrics
    extractor = MetricsExtractor(messages, agent_id, session_id)
    metrics = extractor.extract()

    metrics.agent_transcript_path = str(agent_transcript)

    return metrics


def write_metrics_jsonl(metrics: AgentMetrics, output_file: Path):
    """
    Write metrics to JSONL file (append mode).

    Args:
        metrics: AgentMetrics to write
        output_file: Path to output JSONL file
    """
    # Ensure parent directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict and add type field
    data = metrics.to_dict()
    data['type'] = 'commit-agent'  # Could be parameterized for other agent types

    # Append to file
    with open(output_file, 'a') as f:
        json.dump(data, f, separators=(',', ':'))
        f.write('\n')

    print(f"✓ Metrics written to: {output_file}", file=sys.stderr)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Extract comprehensive metrics from Claude Code agent transcripts'
    )

    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--context-file',
        type=Path,
        help='PostToolUse hook context file (recommended): /tmp/claude-agent-context-{session_id}.json'
    )
    input_group.add_argument(
        '--agent-transcript',
        type=Path,
        help='Direct path to agent transcript: ~/.claude/projects/.../agent-{id}.jsonl'
    )

    # Output options
    parser.add_argument(
        '--output',
        type=Path,
        help='Output JSONL file (default: .claude/metrics/commit-metrics-YYYY-MM-DD.jsonl)'
    )
    parser.add_argument(
        '--print-only',
        action='store_true',
        help='Print metrics to stdout instead of writing to file'
    )

    args = parser.parse_args()

    # Extract metrics
    if args.context_file:
        metrics = extract_from_hook_context(args.context_file)
    else:
        metrics = extract_from_agent_transcript(args.agent_transcript)

    if not metrics:
        print("Error: Failed to extract metrics", file=sys.stderr)
        sys.exit(1)

    # Output
    if args.print_only:
        print(json.dumps(metrics.to_dict(), indent=2))
    else:
        # Determine output file
        if args.output:
            output_file = args.output
        else:
            # Default: .claude/metrics/commit-metrics-YYYY-MM-DD.jsonl
            date_str = datetime.now().strftime('%Y-%m-%d')
            output_file = Path.cwd() / '.claude' / 'metrics' / f'commit-metrics-{date_str}.jsonl'

        write_metrics_jsonl(metrics, output_file)

        # Print summary
        print(f"\n=== Metrics Summary ===", file=sys.stderr)
        print(f"Agent ID: {metrics.agent_id}", file=sys.stderr)
        print(f"Session ID: {metrics.session_id}", file=sys.stderr)
        print(f"Total Tokens: {metrics.tokens.total_tokens:,}", file=sys.stderr)
        print(f"  Input: {metrics.tokens.input_tokens:,}", file=sys.stderr)
        print(f"  Output: {metrics.tokens.output_tokens:,}", file=sys.stderr)
        print(f"  Cache Read: {metrics.tokens.cache_read_tokens:,}", file=sys.stderr)
        print(f"  Cache Hit Rate: {metrics.tokens.cache_hit_rate:.1%}", file=sys.stderr)
        print(f"Tool Uses: {metrics.execution.total_tool_uses}", file=sys.stderr)
        print(f"Commits Created: {metrics.git.commits_created}", file=sys.stderr)
        print(f"Files Changed: {metrics.git.files_changed}", file=sys.stderr)
        print(f"Pre-commit Runs: {metrics.pre_commit.total_runs}", file=sys.stderr)
        print(f"Phases Executed: {', '.join(metrics.quality.phases_executed)}", file=sys.stderr)


if __name__ == '__main__':
    main()
