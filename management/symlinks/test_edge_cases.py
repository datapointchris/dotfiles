#!/usr/bin/env python3
"""Test edge cases for exclusion patterns."""
from pathlib import Path
from symlinks.utils import should_exclude

# Test cases that should NOT be excluded (regression tests)
edge_cases = [
    # .git patterns
    (".gitconfig", False, ".gitconfig should NOT be excluded"),
    (".gitignore", False, ".gitignore should NOT be excluded"),
    (".github/workflows/ci.yml", False, ".github directory should NOT be excluded"),
    (".gitattributes", False, ".gitattributes should NOT be excluded"),
    (".git/config", True, ".git directory SHOULD be excluded"),
    ("foo/.git/hooks", True, ".git directory SHOULD be excluded"),

    # .DS patterns
    (".DS_Store", True, ".DS_Store SHOULD be excluded"),
    (".DSConfig", False, ".DSConfig should NOT be excluded (not exact match)"),

    # .pytest patterns
    (".pytest_cache/foo", True, ".pytest_cache SHOULD be excluded"),
    (".pytest.ini", False, ".pytest.ini should NOT be excluded"),

    # node_modules
    ("node_modules/foo", True, "node_modules SHOULD be excluded"),
    ("node_modules.txt", False, "node_modules.txt should NOT be excluded"),

    # tmux patterns
    ("tmux/plugins/foo", True, "tmux/plugins SHOULD be excluded"),
    (".tmux/plugins/bar", True, ".tmux/plugins SHOULD be excluded"),
    ("tmux/tmux.conf", False, "tmux/tmux.conf should NOT be excluded"),
    ("tmux.conf", False, "tmux.conf should NOT be excluded"),

    # tmp patterns
    ("file.tmp", True, ".tmp files SHOULD be excluded"),
    ("file.temp", True, ".temp files SHOULD be excluded"),
    ("template.txt", False, "template.txt should NOT be excluded"),
    ("tmp_file.txt", False, "tmp_file.txt should NOT be excluded"),
]

print("Testing exclusion patterns...")
print("=" * 60)

failed = []
for path, should_be_excluded, description in edge_cases:
    result = should_exclude(Path(path))
    status = "✓" if result == should_be_excluded else "✗"

    if result != should_be_excluded:
        failed.append((path, should_be_excluded, result, description))
        print(f"{status} FAIL: {description}")
        print(f"   Path: {path}")
        print(f"   Expected: {should_be_excluded}, Got: {result}")
    else:
        print(f"{status} PASS: {description}")

print("=" * 60)
if failed:
    print(f"\n✗ {len(failed)} tests FAILED:")
    for path, expected, got, desc in failed:
        print(f"  - {path}: expected {expected}, got {got}")
    exit(1)
else:
    print(f"\n✓ All {len(edge_cases)} edge case tests PASSED!")
