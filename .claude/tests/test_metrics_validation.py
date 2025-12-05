"""
Validation tests for metrics extraction completeness and accuracy.

These tests verify that metrics files contain valid, complete data
and that extraction is working correctly for real agent runs.
"""

import json
from pathlib import Path
from datetime import datetime

try:
    import pytest
except ImportError:
    # Allow tests to run without pytest for manual execution
    class MockPytest:
        @staticmethod
        def skip(msg):
            raise Exception(f"SKIPPED: {msg}")
        @staticmethod
        def fail(msg):
            raise AssertionError(msg)
    pytest = MockPytest()


def get_metrics_file(date_str=None):
    """Get metrics file path for a specific date (or today)."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    return Path.home() / "dotfiles/.claude/metrics" / f"commit-metrics-{date_str}.jsonl"


def load_metrics_entries(metrics_file):
    """Load all metrics entries from a JSONL file."""
    if not metrics_file.exists():
        return []

    entries = []
    with open(metrics_file) as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))
    return entries


class TestMetricsFileStructure:
    """Test that metrics files exist and are properly formatted."""

    def test_metrics_directory_exists(self):
        """Metrics directory should exist."""
        metrics_dir = Path.home() / "dotfiles/.claude/metrics"
        assert metrics_dir.exists(), "Metrics directory not found"
        assert metrics_dir.is_dir(), "Metrics path is not a directory"

    def test_metrics_file_is_jsonl(self):
        """Metrics file should be valid JSONL format."""
        metrics_file = get_metrics_file()
        if not metrics_file.exists():
            pytest.skip("No metrics file for today yet")

        entries = load_metrics_entries(metrics_file)
        assert len(entries) > 0, "Metrics file is empty"

        # Each entry should be valid JSON
        for i, entry in enumerate(entries):
            assert isinstance(entry, dict), f"Entry {i} is not a dict"

    def test_no_duplicate_agent_ids(self):
        """Each agent_id should appear only once per file."""
        metrics_file = get_metrics_file()
        if not metrics_file.exists():
            pytest.skip("No metrics file for today yet")

        entries = load_metrics_entries(metrics_file)
        agent_ids = [e["agent_id"] for e in entries]

        # Check for duplicates
        seen = set()
        duplicates = set()
        for aid in agent_ids:
            if aid in seen:
                duplicates.add(aid)
            seen.add(aid)

        assert len(duplicates) == 0, f"Duplicate agent_ids found: {duplicates}"


class TestMetricsSchemaCompliance:
    """Test that metrics entries conform to expected schema."""

    def test_required_top_level_fields(self):
        """All entries should have required top-level fields."""
        metrics_file = get_metrics_file()
        if not metrics_file.exists():
            pytest.skip("No metrics file for today yet")

        entries = load_metrics_entries(metrics_file)
        required_fields = [
            "agent_id",
            "session_id",
            "timestamp",
            "tokens",
            "execution",
            "git",
            "pre_commit",
            "quality",
            "model"
        ]

        for entry in entries:
            for field in required_fields:
                assert field in entry, f"Missing field: {field} in agent {entry.get('agent_id')}"

    def test_token_metrics_structure(self):
        """Token metrics should have expected fields."""
        metrics_file = get_metrics_file()
        if not metrics_file.exists():
            pytest.skip("No metrics file for today yet")

        entries = load_metrics_entries(metrics_file)
        token_fields = [
            "total_tokens",
            "input_tokens",
            "output_tokens",
            "cache_creation_tokens",
            "cache_read_tokens",
            "cache_hit_rate"
        ]

        for entry in entries:
            tokens = entry["tokens"]
            for field in token_fields:
                assert field in tokens, f"Missing token field: {field}"
                assert isinstance(tokens[field], (int, float)), \
                    f"Token field {field} should be numeric"

    def test_git_metrics_structure(self):
        """Git metrics should have expected fields."""
        metrics_file = get_metrics_file()
        if not metrics_file.exists():
            pytest.skip("No metrics file for today yet")

        entries = load_metrics_entries(metrics_file)
        git_fields = [
            "commits_created",
            "commit_hashes",
            "files_changed",
            "git_commands"
        ]

        for entry in entries:
            git = entry["git"]
            for field in git_fields:
                assert field in git, f"Missing git field: {field}"


class TestMetricsDataValidity:
    """Test that metrics data values are valid and reasonable."""

    def test_token_counts_non_negative(self):
        """Token counts should be non-negative."""
        metrics_file = get_metrics_file()
        if not metrics_file.exists():
            pytest.skip("No metrics file for today yet")

        entries = load_metrics_entries(metrics_file)

        for entry in entries:
            tokens = entry["tokens"]
            assert tokens["total_tokens"] >= 0
            assert tokens["input_tokens"] >= 0
            assert tokens["output_tokens"] >= 0
            assert tokens["cache_creation_tokens"] >= 0
            assert tokens["cache_read_tokens"] >= 0

    def test_cache_hit_rate_range(self):
        """Cache hit rate should be between 0 and 1."""
        metrics_file = get_metrics_file()
        if not metrics_file.exists():
            pytest.skip("No metrics file for today yet")

        entries = load_metrics_entries(metrics_file)

        for entry in entries:
            cache_hit_rate = entry["tokens"]["cache_hit_rate"]
            assert 0.0 <= cache_hit_rate <= 1.0, \
                f"Cache hit rate {cache_hit_rate} out of range for agent {entry['agent_id']}"

    def test_commits_match_hashes(self):
        """Number of commits should match number of commit hashes (excluding placeholder)."""
        metrics_file = get_metrics_file()
        if not metrics_file.exists():
            pytest.skip("No metrics file for today yet")

        entries = load_metrics_entries(metrics_file)

        for entry in entries:
            commits_created = entry["git"]["commits_created"]
            commit_hashes = entry["git"]["commit_hashes"]

            # Filter out placeholder hashes
            real_hashes = [h for h in commit_hashes if h != "0000000"]

            if commits_created > 0:
                assert len(real_hashes) >= commits_created, \
                    f"Agent {entry['agent_id']}: {commits_created} commits but only {len(real_hashes)} real hashes"

    def test_agent_id_format(self):
        """Agent IDs should be 8-character hex strings."""
        metrics_file = get_metrics_file()
        if not metrics_file.exists():
            pytest.skip("No metrics file for today yet")

        entries = load_metrics_entries(metrics_file)

        for entry in entries:
            agent_id = entry["agent_id"]
            assert len(agent_id) == 8, f"Agent ID {agent_id} is not 8 characters"
            # Should be hexadecimal
            try:
                int(agent_id, 16)
            except ValueError:
                pytest.fail(f"Agent ID {agent_id} is not valid hex")

    def test_model_name_populated(self):
        """Model name should not be 'unknown'."""
        metrics_file = get_metrics_file()
        if not metrics_file.exists():
            pytest.skip("No metrics file for today yet")

        entries = load_metrics_entries(metrics_file)

        for entry in entries:
            model_name = entry["model"]["model_name"]
            assert model_name != "unknown", \
                f"Agent {entry['agent_id']} has unknown model name"
            assert "claude" in model_name.lower(), \
                f"Model name {model_name} doesn't contain 'claude'"


class TestMetricsCompleteness:
    """Test that metrics contain meaningful data for commit-agent runs."""

    def test_commit_agents_have_git_data(self):
        """Agents that created commits should have git data."""
        metrics_file = get_metrics_file()
        if not metrics_file.exists():
            pytest.skip("No metrics file for today yet")

        entries = load_metrics_entries(metrics_file)

        for entry in entries:
            commits = entry["git"]["commits_created"]
            if commits > 0:
                # Should have git commands
                assert len(entry["git"]["git_commands"]) > 0, \
                    f"Agent {entry['agent_id']} created commits but no git commands recorded"

                # Should have status/diff checks
                assert entry["git"]["git_status_checks"] > 0 or \
                       entry["git"]["git_diff_checks"] > 0, \
                    f"Agent {entry['agent_id']} created commits but no status/diff checks"

    def test_agents_have_tool_usage(self):
        """All agents should have tool usage recorded."""
        metrics_file = get_metrics_file()
        if not metrics_file.exists():
            pytest.skip("No metrics file for today yet")

        entries = load_metrics_entries(metrics_file)

        for entry in entries:
            total_tools = entry["execution"]["total_tool_uses"]
            assert total_tools > 0, \
                f"Agent {entry['agent_id']} has no tool usage recorded"

            tool_types = entry["execution"]["tool_types"]
            assert len(tool_types) > 0, \
                f"Agent {entry['agent_id']} has no tool types recorded"

    def test_token_totals_sum_correctly(self):
        """Total tokens should reasonably match sum of components."""
        metrics_file = get_metrics_file()
        if not metrics_file.exists():
            pytest.skip("No metrics file for today yet")

        entries = load_metrics_entries(metrics_file)

        for entry in entries:
            tokens = entry["tokens"]
            total = tokens["total_tokens"]

            # Total should be at least input + output
            # (cache tokens are subsets of input)
            minimum = tokens["input_tokens"] + tokens["output_tokens"]

            assert total >= minimum, \
                f"Agent {entry['agent_id']}: total {total} < input+output {minimum}"


class TestMetricsExtraction:
    """Test specific extraction patterns."""

    def test_pre_commit_detection(self):
        """Pre-commit runs should be detected when present."""
        metrics_file = get_metrics_file()
        if not metrics_file.exists():
            pytest.skip("No metrics file for today yet")

        entries = load_metrics_entries(metrics_file)

        # At least some entries should have pre-commit runs
        # (assuming we've run commit-agent which uses pre-commit)
        has_pre_commit = any(e["pre_commit"]["total_runs"] > 0 for e in entries)

        assert has_pre_commit, "No entries have pre-commit runs detected"

    def test_logsift_detection(self):
        """Logsift invocations should be detected when used."""
        metrics_file = get_metrics_file()
        if not metrics_file.exists():
            pytest.skip("No metrics file for today yet")

        entries = load_metrics_entries(metrics_file)

        # Check for logsift in quality metrics
        for entry in entries:
            logsift_invocations = entry["quality"]["logsift_invocations"]
            logsift_runs = entry["pre_commit"]["logsift_runs"]

            # If logsift ran for pre-commit, should be in quality metrics too
            if logsift_runs > 0:
                assert logsift_invocations > 0, \
                    f"Agent {entry['agent_id']}: logsift_runs={logsift_runs} but invocations=0"


def test_validate_most_recent_entry():
    """Comprehensive validation of the most recent metrics entry."""
    metrics_file = get_metrics_file()
    if not metrics_file.exists():
        pytest.skip("No metrics file for today yet")

    entries = load_metrics_entries(metrics_file)
    if not entries:
        pytest.skip("Metrics file is empty")

    latest = entries[-1]

    print(f"\n=== Validating Latest Entry ===")
    print(f"Agent ID: {latest['agent_id']}")
    print(f"Tokens: {latest['tokens']['total_tokens']:,}")
    print(f"Commits: {latest['git']['commits_created']}")
    print(f"Tool Uses: {latest['execution']['total_tool_uses']}")
    print(f"Cache Hit Rate: {latest['tokens']['cache_hit_rate']:.2%}")

    # Comprehensive checks
    assert latest["tokens"]["total_tokens"] > 0, "No tokens recorded"
    assert latest["execution"]["total_tool_uses"] > 0, "No tools used"
    assert latest["model"]["model_name"] != "unknown", "Model name unknown"
    assert len(latest["git"]["git_commands"]) > 0, "No git commands"

    print("✅ All validations passed")
