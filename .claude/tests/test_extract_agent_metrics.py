#!/usr/bin/env python3
"""
Comprehensive tests for extract_agent_metrics.py

Tests cover:
- Transcript parsing
- Metrics extraction (all categories)
- Hook context workflow
- Error handling
- Edge cases
"""

import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime
import sys

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / '.claude' / 'lib'))

from extract_agent_metrics import (
    TranscriptParser,
    MetricsExtractor,
    AgentMetrics,
    TokenMetrics,
    ExecutionMetrics,
    GitMetrics,
    PreCommitMetrics,
    QualityMetrics,
    ModelMetrics,
    get_agent_id_from_parent,
    extract_from_hook_context,
    extract_from_agent_transcript,
)


# ============================================================================
# Fixtures - Sample Transcript Data
# ============================================================================

@pytest.fixture
def sample_agent_message():
    """Sample agent message with usage data."""
    return {
        "parentUuid": None,
        "isSidechain": True,
        "sessionId": "test-session-123",
        "agentId": "test-agent",
        "slug": "test-slug",
        "cwd": "/test/dir",
        "gitBranch": "main",
        "version": "2.0.59",
        "type": "assistant",
        "timestamp": "2025-12-05T10:00:00.000Z",
        "message": {
            "model": "claude-sonnet-4-5-20250929",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "Starting task"
                }
            ],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_input_tokens": 200,
                "cache_read_input_tokens": 1000,
                "cache_creation": {
                    "ephemeral_5m_input_tokens": 200,
                    "ephemeral_1h_input_tokens": 0
                },
                "service_tier": "standard"
            },
            "stop_reason": "end_turn"
        },
        "requestId": "req_123"
    }


@pytest.fixture
def sample_tool_use_message():
    """Sample message with tool use."""
    return {
        "type": "assistant",
        "sessionId": "test-session-123",
        "agentId": "test-agent",
        "timestamp": "2025-12-05T10:00:01.000Z",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "tool_123",
                    "name": "Bash",
                    "input": {
                        "command": "git status",
                        "description": "Check git status"
                    }
                }
            ],
            "usage": {
                "input_tokens": 50,
                "output_tokens": 100
            }
        }
    }


@pytest.fixture
def sample_tool_result_message():
    """Sample tool result with git output."""
    return {
        "type": "user",
        "sessionId": "test-session-123",
        "agentId": "test-agent",
        "timestamp": "2025-12-05T10:00:02.000Z",
        "toolUseResult": {
            "stdout": "On branch main\nnothing to commit",
            "stderr": "",
            "totalDurationMs": 5000,
            "totalTokens": 15000,
            "totalToolUseCount": 5,
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5
            }
        }
    }


@pytest.fixture
def sample_git_commit_message():
    """Sample message with git commit."""
    return {
        "type": "assistant",
        "timestamp": "2025-12-05T10:00:03.000Z",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "Bash",
                    "input": {
                        "command": "git commit -m 'test commit'"
                    }
                }
            ]
        }
    }


@pytest.fixture
def sample_git_output_message():
    """Sample message with git commit hash output."""
    return {
        "type": "user",
        "timestamp": "2025-12-05T10:00:04.000Z",
        "toolUseResult": {
            "stdout": "ae9c5d8fcae18c25e2d0ca51078cb0a9902a0e58\n"
        }
    }


@pytest.fixture
def sample_phase_message():
    """Sample message with phase markers."""
    return {
        "type": "assistant",
        "timestamp": "2025-12-05T10:00:05.000Z",
        "message": {
            "content": [
                {
                    "type": "text",
                    "text": "## Phase 1: Analyze Changes\n\nStarting phase 1"
                }
            ]
        }
    }


@pytest.fixture
def sample_logsift_message():
    """Sample message with logsift output."""
    return {
        "type": "user",
        "timestamp": "2025-12-05T10:00:06.000Z",
        "toolUseResult": {
            "stdout": "summary:\n  status: success\n  exit_code: 0\nstats:\n  total_errors: 3\n  total_warnings: 2\n"
        }
    }


@pytest.fixture
def sample_thinking_message():
    """Sample message with thinking block."""
    return {
        "type": "assistant",
        "timestamp": "2025-12-05T10:00:07.000Z",
        "message": {
            "content": [
                {
                    "type": "thinking",
                    "thinking": "Let me think about this..."
                }
            ]
        }
    }


# ============================================================================
# Fixtures - Temporary Files
# ============================================================================

@pytest.fixture
def temp_agent_transcript(
    sample_agent_message,
    sample_tool_use_message,
    sample_tool_result_message
):
    """Create temporary agent transcript file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        f.write(json.dumps(sample_agent_message) + '\n')
        f.write(json.dumps(sample_tool_use_message) + '\n')
        f.write(json.dumps(sample_tool_result_message) + '\n')
        temp_path = Path(f.name)

    yield temp_path
    temp_path.unlink()


@pytest.fixture
def temp_parent_transcript():
    """Create temporary parent transcript with agentId."""
    messages = [
        {
            "type": "assistant",
            "timestamp": "2025-12-05T10:00:00.000Z"
        },
        {
            "type": "user",
            "agentId": "test-agent",
            "timestamp": "2025-12-05T10:00:01.000Z"
        },
        {
            "type": "assistant",
            "toolUseResult": {
                "agentId": "abc12345",
                "status": "completed"
            }
        }
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')
        temp_path = Path(f.name)

    yield temp_path
    temp_path.unlink()


@pytest.fixture
def temp_hook_context(temp_parent_transcript):
    """Create temporary hook context file."""
    context = {
        "session_id": "test-session-123",
        "transcript_path": str(temp_parent_transcript)
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(context, f)
        temp_path = Path(f.name)

    yield temp_path
    temp_path.unlink()


# ============================================================================
# Test: TranscriptParser
# ============================================================================

class TestTranscriptParser:
    """Test transcript parsing."""

    def test_parse_valid_transcript(self, temp_agent_transcript):
        """Test parsing valid JSONL transcript."""
        parser = TranscriptParser(temp_agent_transcript)
        messages = parser.parse()

        assert len(messages) == 3
        assert messages[0]['type'] == 'assistant'
        assert messages[1]['type'] == 'assistant'
        assert messages[2]['type'] == 'user'

    def test_parse_nonexistent_file(self):
        """Test parsing nonexistent file raises error."""
        parser = TranscriptParser(Path('/nonexistent/file.jsonl'))
        with pytest.raises(FileNotFoundError):
            parser.parse()

    def test_parse_empty_lines(self, tmp_path):
        """Test parser skips empty lines."""
        transcript = tmp_path / 'test.jsonl'
        transcript.write_text(
            '{"type": "assistant"}\n'
            '\n'
            '{"type": "user"}\n'
        )

        parser = TranscriptParser(transcript)
        messages = parser.parse()

        assert len(messages) == 2

    def test_parse_invalid_json(self, tmp_path, capsys):
        """Test parser handles invalid JSON gracefully."""
        transcript = tmp_path / 'test.jsonl'
        transcript.write_text(
            '{"type": "assistant"}\n'
            'invalid json line\n'
            '{"type": "user"}\n'
        )

        parser = TranscriptParser(transcript)
        messages = parser.parse()

        # Should parse valid lines and warn about invalid
        assert len(messages) == 2
        captured = capsys.readouterr()
        assert 'Warning' in captured.err


# ============================================================================
# Test: TokenMetrics Extraction
# ============================================================================

class TestTokenMetricsExtraction:
    """Test token metrics extraction."""

    def test_extract_basic_tokens(self, sample_agent_message):
        """Test basic token extraction from usage data."""
        messages = [sample_agent_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.tokens.input_tokens == 100
        assert metrics.tokens.output_tokens == 50
        assert metrics.tokens.cache_creation_tokens == 200
        assert metrics.tokens.cache_read_tokens == 1000
        assert metrics.tokens.total_tokens == 1350

    def test_cache_hit_rate_calculation(self, sample_agent_message):
        """Test cache hit rate calculation."""
        messages = [sample_agent_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        # cache_read / (input + cache_read) = 1000 / 1100 = 0.909
        assert abs(metrics.tokens.cache_hit_rate - 0.909) < 0.01

    def test_cache_tier_breakdown(self, sample_agent_message):
        """Test cache tier token breakdown."""
        messages = [sample_agent_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.tokens.cache_5m_tokens == 200
        assert metrics.tokens.cache_1h_tokens == 0

    def test_token_statistics(self, sample_agent_message):
        """Test token statistics (max, avg)."""
        # Create multiple messages with different token counts
        msg1 = sample_agent_message.copy()
        msg1['message']['usage']['input_tokens'] = 100

        msg2 = sample_agent_message.copy()
        msg2['message']['usage']['input_tokens'] = 200

        messages = [msg1, msg2]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.tokens.max_input_tokens == 200
        assert metrics.tokens.avg_input_tokens == 150.0


# ============================================================================
# Test: ExecutionMetrics Extraction
# ============================================================================

class TestExecutionMetricsExtraction:
    """Test execution metrics extraction."""

    def test_tool_usage_tracking(self, sample_tool_use_message):
        """Test tool usage is tracked by type."""
        messages = [sample_tool_use_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.execution.total_tool_uses == 1
        assert metrics.execution.tool_types['Bash'] == 1

    def test_message_type_counts(self, sample_agent_message, sample_tool_result_message):
        """Test message type counting."""
        messages = [sample_agent_message, sample_tool_result_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.execution.assistant_messages == 1
        assert metrics.execution.user_messages == 1
        assert metrics.execution.tool_result_messages == 1

    def test_duration_extraction(self, sample_tool_result_message):
        """Test duration extraction from toolUseResult."""
        messages = [sample_tool_result_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.execution.total_duration_ms == 5000

    def test_timestamp_tracking(self, sample_agent_message, sample_tool_result_message):
        """Test start/end timestamp tracking."""
        messages = [sample_agent_message, sample_tool_result_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.execution.start_timestamp == "2025-12-05T10:00:00.000Z"
        assert metrics.execution.end_timestamp == "2025-12-05T10:00:02.000Z"

    def test_thinking_blocks_counted(self, sample_thinking_message):
        """Test thinking blocks are counted."""
        messages = [sample_thinking_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.execution.thinking_blocks == 1

    def test_stop_reasons_tracked(self, sample_agent_message):
        """Test stop reasons are tracked."""
        messages = [sample_agent_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.execution.stop_reasons['end_turn'] == 1


# ============================================================================
# Test: GitMetrics Extraction
# ============================================================================

class TestGitMetricsExtraction:
    """Test git metrics extraction."""

    def test_git_commands_tracked(self, sample_tool_use_message):
        """Test git commands are tracked."""
        messages = [sample_tool_use_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert len(metrics.git.git_commands) == 1
        assert 'git status' in metrics.git.git_commands[0]
        assert metrics.git.git_status_checks == 1

    def test_commit_creation_tracked(self, sample_git_commit_message):
        """Test git commits are counted."""
        messages = [sample_git_commit_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.git.commits_created == 1

    def test_commit_hash_extraction(self, sample_git_output_message):
        """Test commit hashes are extracted from output."""
        messages = [sample_git_output_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert 'ae9c5d8' in metrics.git.commit_hashes

    def test_file_change_parsing(self):
        """Test parsing git diff --name-status output."""
        msg = {
            "type": "user",
            "toolUseResult": {
                "stdout": "A\tfile1.txt\nM\tfile2.txt\nD\tfile3.txt\nR100\told.txt\tnew.txt\n"
            }
        }
        messages = [msg]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.git.files_created == 1
        assert metrics.git.files_modified == 1
        assert metrics.git.files_deleted == 1
        assert metrics.git.files_renamed == 1
        assert metrics.git.files_changed == 4


# ============================================================================
# Test: PreCommitMetrics Extraction
# ============================================================================

class TestPreCommitMetricsExtraction:
    """Test pre-commit metrics extraction."""

    def test_pre_commit_run_counted(self):
        """Test pre-commit runs are counted."""
        msg = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {
                            "command": "pre-commit run --all-files"
                        }
                    }
                ]
            }
        }
        messages = [msg]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.pre_commit.total_runs == 1

    def test_background_run_detected(self):
        """Test background pre-commit runs are detected."""
        msg = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {
                            "command": "pre-commit run > /dev/null 2>&1 || true"
                        }
                    }
                ]
            }
        }
        messages = [msg]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.pre_commit.background_runs == 1

    def test_logsift_run_detected(self):
        """Test logsift pre-commit runs are detected."""
        msg = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {
                            "command": "logsift monitor -- pre-commit run"
                        }
                    }
                ]
            }
        }
        messages = [msg]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.pre_commit.logsift_runs == 1

    def test_logsift_errors_parsed(self, sample_logsift_message):
        """Test errors/warnings parsed from logsift output."""
        messages = [sample_logsift_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.pre_commit.total_errors == 3
        assert metrics.pre_commit.total_warnings == 2
        assert metrics.pre_commit.successful_runs == 0
        assert metrics.pre_commit.failed_runs == 1


# ============================================================================
# Test: QualityMetrics Extraction
# ============================================================================

class TestQualityMetricsExtraction:
    """Test quality metrics extraction."""

    def test_phases_detected(self, sample_phase_message):
        """Test phase execution is detected."""
        messages = [sample_phase_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert 'phase_1' in metrics.quality.phases_executed

    def test_all_phases_detected(self):
        """Test all 7 phases can be detected."""
        messages = []
        for i in range(1, 8):
            messages.append({
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": f"## Phase {i}: Test"}
                    ]
                }
            })

        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert len(metrics.quality.phases_executed) == 7
        for i in range(1, 8):
            assert f'phase_{i}' in metrics.quality.phases_executed

    def test_read_own_instructions_detected(self):
        """Test detection of reading own instructions."""
        msg = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {
                            "file_path": "/path/to/commit-agent.md"
                        }
                    }
                ]
            }
        }
        messages = [msg]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.quality.read_own_instructions is True

    def test_logsift_invocations_counted(self):
        """Test logsift invocations are counted."""
        msg = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {
                            "command": "logsift monitor -- some command"
                        }
                    }
                ]
            }
        }
        messages = [msg]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.quality.logsift_invocations == 1


# ============================================================================
# Test: ModelMetrics Extraction
# ============================================================================

class TestModelMetricsExtraction:
    """Test model metrics extraction."""

    def test_model_name_extracted(self, sample_agent_message):
        """Test model name extraction."""
        messages = [sample_agent_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.model.model_name == "claude-sonnet-4-5-20250929"
        assert metrics.model.model_version == "sonnet-4.5"

    def test_service_tier_extracted(self, sample_agent_message):
        """Test service tier extraction."""
        messages = [sample_agent_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.model.service_tier == "standard"


# ============================================================================
# Test: Metadata Extraction
# ============================================================================

class TestMetadataExtraction:
    """Test metadata extraction from first message."""

    def test_metadata_from_first_message(self, sample_agent_message):
        """Test metadata extracted from first message."""
        messages = [sample_agent_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        assert metrics.agent_slug == "test-slug"
        assert metrics.cwd == "/test/dir"
        assert metrics.git_branch == "main"
        assert metrics.claude_version == "2.0.59"


# ============================================================================
# Test: Helper Functions
# ============================================================================

class TestHelperFunctions:
    """Test helper functions."""

    def test_get_agent_id_from_parent(self, temp_parent_transcript):
        """Test extracting agentId from parent transcript."""
        agent_id = get_agent_id_from_parent(temp_parent_transcript)
        assert agent_id == "abc12345"

    def test_extract_from_agent_transcript(self, temp_agent_transcript):
        """Test extracting metrics from agent transcript."""
        metrics = extract_from_agent_transcript(temp_agent_transcript)

        assert metrics is not None
        assert metrics.agent_id == "test-agent"
        assert metrics.session_id == "test-session-123"

    def test_extract_from_nonexistent_transcript(self):
        """Test extracting from nonexistent file returns None."""
        metrics = extract_from_agent_transcript(Path('/nonexistent/file.jsonl'))
        assert metrics is None


# ============================================================================
# Test: Error Handling
# ============================================================================

class TestErrorHandling:
    """Test error handling."""

    def test_missing_usage_data_handled(self):
        """Test messages without usage data don't crash."""
        msg = {
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "test"}]
                # No usage field
            }
        }
        messages = [msg]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        # Should have zero tokens
        assert metrics.tokens.total_tokens == 0

    def test_missing_tool_input_handled(self):
        """Test tool use without input doesn't crash."""
        msg = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Bash"
                        # No input field
                    }
                ]
            }
        }
        messages = [msg]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        # Should still count the tool use
        assert metrics.execution.total_tool_uses == 1


# ============================================================================
# Test: JSONL Output
# ============================================================================

class TestJSONLOutput:
    """Test JSONL output format."""

    def test_to_dict_excludes_raw_data(self, sample_agent_message):
        """Test to_dict() excludes raw_* fields."""
        messages = [sample_agent_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        data = metrics.to_dict()

        assert 'raw_tool_calls' not in data
        assert 'raw_usage_data' not in data

    def test_to_dict_includes_all_metrics(self, sample_agent_message):
        """Test to_dict() includes all metric categories."""
        messages = [sample_agent_message]
        extractor = MetricsExtractor(messages, "test-agent", "test-session")
        metrics = extractor.extract()

        data = metrics.to_dict()

        assert 'agent_id' in data
        assert 'tokens' in data
        assert 'execution' in data
        assert 'git' in data
        assert 'pre_commit' in data
        assert 'quality' in data
        assert 'model' in data


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
