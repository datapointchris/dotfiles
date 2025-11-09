#!/usr/bin/env python
"""
Markdown formatter for Claude Code PostToolUse hook.
Fixes missing language tags and spacing issues while preserving code content.
Reads JSON from stdin with file_path, only processes .md/.mdx files.
"""

import re
import sys
import io
import json
import os

# Regex to match fenced code blocks with backtick counting
# Matches ``` or ```` or ````` etc., capturing the backtick count
FENCE_START_RE = re.compile(r"^([ \t]{0,3})(`{3,})([^\n`]*)$")
FENCE_END_RE = re.compile(r"^([ \t]{0,3})(`{3,})[ \t]*$")


def detect_language(code):
    """Best-effort language detection from code content."""
    s = code.strip()

    # JSON detection (try parsing first)
    if re.search(r"^\s*[{\[]", s):
        try:
            json.loads(s)
            return "json"
        except (ValueError, json.JSONDecodeError):
            pass

    # XML/HTML detection
    if re.search(r"^\s*<!DOCTYPE html>|^\s*<html\b|^\s*<([a-zA-Z]+)(\s|>)", s):
        return "html"
    if re.search(r"^\s*<\?xml\b|^\s*<\w+[:>]", s):
        return "xml"

    # SQL detection
    if re.search(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE)\s+", s, re.I) and ";" in s:
        return "sql"

    # PowerShell detection (specific patterns to avoid false positives)
    if (
        re.search(r"\bfunction\s+\w+-\w+\b", s)
        or re.search(r"\b(Write-Host|Get-\w+|Set-\w+|New-\w+|Remove-\w+)\b", s)
        or re.search(r"\$\w+\s*=.*\s*-\w+", s)
    ):
        return "powershell"

    # Bash/shell detection
    if (
        re.search(r"^#!.*\b(bash|sh|zsh)\b", s, re.M)
        or re.search(r"\b(if|then|fi|elif|case|esac|for|in|do|done)\b", s)
        or re.search(r"^\s*export\s+\w+=", s, re.M)
    ):
        return "bash"

    # Python detection
    if (
        re.search(r"^\s*def\s+\w+\s*\(", s, re.M)
        or re.search(r"^\s*(import|from)\s+\w+", s, re.M)
        or re.search(r'\bif\s+__name__\s*==\s*["\']__main__["\']', s)
    ):
        return "python"

    # JavaScript/TypeScript detection
    if re.search(
        r"\b(function\s+\w+\s*\(|const\s+\w+\s*=|let\s+\w+\s*=|var\s+\w+\s*=)", s
    ) or re.search(r"=>|console\.(log|error|warn)", s):
        return "javascript"

    # CSS detection
    if re.search(r"[.#]\w+\s*\{[^}]*\}", s) or re.search(r"\w+\s*:\s*[^;]+;", s):
        return "css"

    # YAML detection (after JSON check to avoid conflicts)
    if re.search(r"(?m)^[ \t]*\w[^:\n]*:\s*\S", s) or re.search(
        r"(?m)^[ \t]*-\s+\S", s
    ):
        return "yaml"

    return "text"


def find_code_blocks(content):
    """Find all code blocks respecting nesting (4-backtick can contain 3-backtick)."""
    blocks = []
    lines = content.split('\n')
    i = 0

    while i < len(lines):
        match = FENCE_START_RE.match(lines[i])
        if match:
            indent, backticks, info = match.groups()
            fence_len = len(backticks)
            start_line = i
            info_str = info.strip()
            i += 1

            # Find matching closing fence
            body_lines = []
            found_close = False
            while i < len(lines):
                close_match = FENCE_END_RE.match(lines[i])
                if close_match:
                    close_indent, close_backticks = close_match.groups()
                    # Must be same backtick count and same indent
                    if len(close_backticks) == fence_len and close_indent == indent:
                        found_close = True
                        end_line = i
                        break
                body_lines.append(lines[i])
                i += 1

            if found_close:
                blocks.append({
                    'start': start_line,
                    'end': end_line,
                    'indent': indent,
                    'backticks': backticks,
                    'info': info_str,
                    'body': '\n'.join(body_lines)
                })
                i += 1
            else:
                i = start_line + 1
        else:
            i += 1

    return blocks


def add_lang_to_blocks(content):
    """Add language tags to code blocks that are missing them."""
    blocks = find_code_blocks(content)

    # Process blocks in reverse order to maintain line numbers
    lines = content.split('\n')

    for block in reversed(blocks):
        # Skip if language already present
        if block['info'] and re.match(r"^[A-Za-z0-9_+.-]+", block['info']):
            continue

        # Detect language
        lang = detect_language(block['body'])

        # Update the opening fence line
        lines[block['start']] = f"{block['indent']}{block['backticks']}{lang}"

    return '\n'.join(lines)


def fix_spacing_outside_code(text):
    """Apply markdown spacing fixes only outside fenced code blocks."""
    text = re.sub(r"\n{3,}", "\n\n", text)  # Collapse 3+ blank lines
    text = re.sub(
        r"(?m)^(#{1,6}\s+.+)\r?\n(?!\r?\n|$)", r"\1\n\n", text
    )  # Space after headings
    return text


def format_markdown(content):
    """Format markdown content with language detection and spacing fixes."""
    # Add language tags to unlabeled code fences
    content = add_lang_to_blocks(content)

    # Fix spacing only outside code blocks
    blocks = find_code_blocks(content)
    lines = content.split('\n')

    # Mark lines that are inside code blocks
    inside_block = [False] * len(lines)
    for block in blocks:
        for i in range(block['start'], block['end'] + 1):
            inside_block[i] = True

    # Apply spacing fixes only to lines outside blocks
    result_lines = []
    i = 0
    while i < len(lines):
        if inside_block[i]:
            # Inside code block, preserve as-is
            result_lines.append(lines[i])
            i += 1
        else:
            # Outside code block, collect consecutive non-block lines
            outside_chunk = []
            while i < len(lines) and not inside_block[i]:
                outside_chunk.append(lines[i])
                i += 1

            # Apply spacing fixes to this chunk
            chunk_text = '\n'.join(outside_chunk)
            fixed_chunk = fix_spacing_outside_code(chunk_text)
            result_lines.extend(fixed_chunk.split('\n'))

    result = '\n'.join(result_lines)
    return result.rstrip() + "\n"  # ensure single trailing newline


def main():
    """Main function for PostToolUse hook."""
    try:
        # Read JSON from stdin (PostToolUse hook data)
        hook_data = json.load(sys.stdin)

        # Extract file path from tool_input
        tool_input = hook_data.get("tool_input", {})
        filepath = tool_input.get("file_path")

        if not filepath:
            # No file path provided, exit silently
            sys.exit(0)

        # Only process markdown files
        _, ext = os.path.splitext(filepath)
        if ext.lower() not in [".md", ".mdx"]:
            # Not a markdown file, exit silently
            sys.exit(0)

        # Check if file exists
        if not os.path.isfile(filepath):
            sys.exit(0)

        # Read file content
        with io.open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Format the markdown
        formatted = format_markdown(content)

        # Only write if changes were made
        if formatted != content:
            with io.open(filepath, "w", encoding="utf-8") as f:
                f.write(formatted)
            print(f"✓ Formatted markdown: {os.path.basename(filepath)}", file=sys.stderr)

    except json.JSONDecodeError:
        # Not valid JSON input, exit silently (might be called directly)
        sys.exit(0)
    except Exception as e:
        # Log error but don't fail the hook
        print(f"Markdown formatter warning: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
