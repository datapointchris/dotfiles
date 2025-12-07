#!/usr/bin/env python3
"""Unit tests for refcheck resolve_path() method"""

import sys
from pathlib import Path

def resolve_path(path_str: str, symbol_table: dict) -> str:
    """Resolve a path containing shell variables."""
    resolved = path_str

    # Substitute known variables from symbol table
    for var_name, var_value in symbol_table.items():
        # Handle both $VAR and ${VAR} syntax
        resolved = resolved.replace(f"${var_name}", var_value)
        resolved = resolved.replace(f"${{{var_name}}}", var_value)

    # Check if there are still unresolved variables
    if '$' in resolved:
        raise ValueError(f"Cannot resolve variables in: {path_str}")

    return resolved

def test_simple_variable():
    """Test simple $VAR substitution"""
    symbol_table = {'SCRIPT_DIR': '/tmp/test/subdir'}
    path = "$SCRIPT_DIR/helpers.sh"

    result = resolve_path(path, symbol_table)
    expected = "/tmp/test/subdir/helpers.sh"

    assert result == expected, f"Expected {expected}, got {result}"
    print(f"✅ Simple variable: {path} → {result}")

def test_braced_variable():
    """Test ${VAR} substitution"""
    symbol_table = {'DOTFILES_DIR': '/home/user/dotfiles'}
    path = "${DOTFILES_DIR}/platforms/common/.local/shell/logging.sh"

    result = resolve_path(path, symbol_table)
    expected = "/home/user/dotfiles/platforms/common/.local/shell/logging.sh"

    assert result == expected, f"Expected {expected}, got {result}"
    print(f"✅ Braced variable: {path} → {result}")

def test_multiple_variables():
    """Test path with multiple variables"""
    symbol_table = {
        'SCRIPT_DIR': '/tmp/tests/install/integration',
        'DOTFILES_DIR': '/tmp'
    }
    path = "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

    result = resolve_path(path, symbol_table)
    expected = "/tmp/management/common/lib/failure-logging.sh"

    assert result == expected, f"Expected {expected}, got {result}"
    print(f"✅ Multiple variables: {path} → {result}")

def test_unresolvable_variable():
    """Test that unresolvable variables raise ValueError"""
    symbol_table = {'SCRIPT_DIR': '/tmp/test'}
    path = "$UNKNOWN_VAR/file.sh"

    try:
        resolve_path(path, symbol_table)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Cannot resolve" in str(e)
        print(f"✅ Unresolvable variable correctly raises ValueError: {e}")

def test_no_variables():
    """Test path with no variables"""
    symbol_table = {'SCRIPT_DIR': '/tmp/test'}
    path = "/absolute/path/to/file.sh"

    result = resolve_path(path, symbol_table)
    expected = "/absolute/path/to/file.sh"

    assert result == expected, f"Expected {expected}, got {result}"
    print(f"✅ No variables: {path} → {result}")

def test_mixed_syntax():
    """Test mixing $VAR and ${VAR} syntax"""
    symbol_table = {
        'SCRIPT_DIR': '/tmp/script',
        'FILE': 'helpers.sh'
    }
    path = "${SCRIPT_DIR}/$FILE"

    result = resolve_path(path, symbol_table)
    expected = "/tmp/script/helpers.sh"

    assert result == expected, f"Expected {expected}, got {result}"
    print(f"✅ Mixed syntax: {path} → {result}")

# Run all tests
print("Testing resolve_path() method...\n")

tests = [
    test_simple_variable,
    test_braced_variable,
    test_multiple_variables,
    test_unresolvable_variable,
    test_no_variables,
    test_mixed_syntax,
]

for test in tests:
    try:
        test()
    except AssertionError as e:
        print(f"❌ {test.__name__} FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ {test.__name__} ERROR: {e}")
        sys.exit(1)

print(f"\n{'='*50}")
print("✅ All resolve_path tests passed!")
