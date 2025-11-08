#!/usr/bin/env python
"""
Markdown formatter for Claude Code output.
Fixes missing language tags and spacing issues while preserving code content.
"""

import re
import sys
import io
import json

# Regex to match fenced code blocks with proper indentation handling
CODE_FENCE_RE = re.compile(r"(?ms)^([ \t]{0,3})```([^\n]*)\n(.*?)(\n\1```)[ \t]*\r?\n?")


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


def add_lang_to_fence(match):
    """Add language tag to fenced code block if missing."""
    indent, info, body, closing = match.groups()
    info_str = info.strip()

    # If language already present, leave as-is
    if info_str and re.match(r"^[A-Za-z0-9_+.-]+", info_str):
        return match.group(0)

    lang = detect_language(body)
    return f"{indent}```{lang}\n{body}{closing}\n"


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
    content = CODE_FENCE_RE.sub(add_lang_to_fence, content)

    # Fix spacing only outside code blocks
    parts = []
    last_end = 0

    for match in CODE_FENCE_RE.finditer(content):
        outside_text = content[last_end : match.start()]
        parts.append(fix_spacing_outside_code(outside_text))
        parts.append(match.group(0))  # preserve code fence
        last_end = match.end()

    parts.append(fix_spacing_outside_code(content[last_end:]))
    result = "".join(parts)

    return result.rstrip() + "\n"  # ensure single trailing newline


def main():
    """Main function with proper error handling."""
    if len(sys.argv) < 2:
        print("Usage: python markdown_formatter.py <file.md> [--in-place]")
        sys.exit(1)

    in_place = "--in-place" in sys.argv
    filepath = next((arg for arg in sys.argv[1:] if not arg.startswith("-")), None)

    if not filepath:
        print("Error: No input file specified")
        sys.exit(1)

    try:
        with io.open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        formatted = format_markdown(content)

        if formatted == content:
            print(f"No changes needed for '{filepath}'")
            return

        if in_place:
            with io.open(filepath, "w", encoding="utf-8") as f:
                f.write(formatted)
            print(f"Formatted '{filepath}' in place")
        else:
            sys.stdout.write(formatted)

    except Exception as e:
        print(f"Error processing file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
