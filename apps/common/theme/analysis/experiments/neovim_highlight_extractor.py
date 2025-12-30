#!/usr/bin/env python3
"""
Neovim Highlight Extractor (Experiment 2)

Extracts highlight group definitions from Neovim colorschemes by:
1. Running Neovim with each colorscheme
2. Using nvim_get_hl() API to dump all highlight groups
3. Parsing the output to build a mapping database

This approach is more reliable than parsing Lua code because we get
the actual resolved color values.
"""

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HighlightGroup:
    """Represents a single highlight group definition."""

    name: str
    fg: str | None = None
    bg: str | None = None
    sp: str | None = None  # special (for underline color)
    bold: bool = False
    italic: bool = False
    underline: bool = False
    undercurl: bool = False
    strikethrough: bool = False
    link: str | None = None  # linked group name


@dataclass
class ThemeHighlights:
    """All highlight definitions for a theme."""

    theme_name: str
    variant: str = "default"
    highlights: dict[str, HighlightGroup] = field(default_factory=dict)


# Key treesitter and syntax groups to analyze
KEY_HIGHLIGHT_GROUPS = [
    # Variables
    "@variable",
    "@variable.builtin",
    "@variable.parameter",
    "@variable.member",
    # Functions
    "@function",
    "@function.builtin",
    "@function.call",
    "@function.method",
    # Keywords
    "@keyword",
    "@keyword.function",
    "@keyword.return",
    "@keyword.conditional",
    "@keyword.repeat",
    "@keyword.exception",
    "@keyword.operator",
    "@keyword.import",
    # Strings
    "@string",
    "@string.escape",
    "@string.regexp",
    "@string.special",
    # Types
    "@type",
    "@type.builtin",
    "@constructor",
    # Comments
    "@comment",
    "@comment.todo",
    "@comment.warning",
    "@comment.error",
    "@comment.note",
    # Operators & Punctuation
    "@operator",
    "@punctuation.delimiter",
    "@punctuation.bracket",
    "@punctuation.special",
    # Constants
    "@constant",
    "@constant.builtin",
    "@number",
    "@boolean",
    # Tags
    "@tag",
    "@tag.attribute",
    "@tag.delimiter",
    # Markup
    "@markup.heading",
    "@markup.strong",
    "@markup.italic",
    "@markup.link",
    "@markup.raw",
    # Diff
    "@diff.plus",
    "@diff.minus",
    "@diff.delta",
    # Module/Namespace
    "@module",
    "@label",
    # Legacy Vim groups
    "Normal",
    "Comment",
    "Constant",
    "String",
    "Character",
    "Number",
    "Boolean",
    "Float",
    "Identifier",
    "Function",
    "Statement",
    "Conditional",
    "Repeat",
    "Label",
    "Operator",
    "Keyword",
    "Exception",
    "PreProc",
    "Include",
    "Define",
    "Macro",
    "PreCondit",
    "Type",
    "StorageClass",
    "Structure",
    "Typedef",
    "Special",
    "SpecialChar",
    "Tag",
    "Delimiter",
    "SpecialComment",
    "Debug",
    "Underlined",
    "Ignore",
    "Error",
    "Todo",
    # UI groups
    "CursorLine",
    "CursorColumn",
    "Visual",
    "VisualNOS",
    "Search",
    "IncSearch",
    "LineNr",
    "CursorLineNr",
    "SignColumn",
    "Folded",
    "FoldColumn",
    "VertSplit",
    "WinSeparator",
    "StatusLine",
    "StatusLineNC",
    "TabLine",
    "TabLineFill",
    "TabLineSel",
    "Pmenu",
    "PmenuSel",
    "PmenuSbar",
    "PmenuThumb",
    "NormalFloat",
    "FloatBorder",
    # Diagnostic groups
    "DiagnosticError",
    "DiagnosticWarn",
    "DiagnosticInfo",
    "DiagnosticHint",
    "DiagnosticOk",
    # Git groups
    "DiffAdd",
    "DiffChange",
    "DiffDelete",
    "DiffText",
]

# Colorschemes to extract (matching what's available in user's config)
COLORSCHEMES = [
    # Third-party themes
    "kanagawa-wave",
    "kanagawa-dragon",
    "kanagawa-lotus",
    "rose-pine",
    "rose-pine-moon",
    "rose-pine-dawn",
    "gruvbox",
    "terafox",
    "carbonfox",
    "nightfox",
    "nordfox",
    "nordic",
    "solarized-osaka",
    "github_dark_default",
    "github_dark_dimmed",
    "OceanicNext",
    "slate",
    "retrobox",
    # User's flexoki-moon themes
    "flexoki-moon-black",
    "flexoki-moon-purple",
    "flexoki-moon-green",
    "flexoki-moon-red",
    "flexoki-moon-toddler",
]


def create_extraction_script() -> str:
    """Create a Lua script to extract highlight definitions."""
    return '''
-- Extract highlight definitions from current colorscheme
local function get_all_highlights()
    local result = {}

    -- Get all highlight groups
    local hl_groups = vim.api.nvim_get_hl(0, {})

    for name, hl in pairs(hl_groups) do
        local entry = { name = name }

        -- Convert integer colors to hex
        if hl.fg then
            entry.fg = string.format("#%06x", hl.fg)
        end
        if hl.bg then
            entry.bg = string.format("#%06x", hl.bg)
        end
        if hl.sp then
            entry.sp = string.format("#%06x", hl.sp)
        end

        -- Style attributes
        entry.bold = hl.bold or false
        entry.italic = hl.italic or false
        entry.underline = hl.underline or false
        entry.undercurl = hl.undercurl or false
        entry.strikethrough = hl.strikethrough or false

        -- Link
        if hl.link then
            entry.link = hl.link
        end

        result[name] = entry
    end

    return result
end

-- Output as JSON
local highlights = get_all_highlights()
print(vim.json.encode(highlights))
'''


def extract_colorscheme_highlights(colorscheme: str, timeout: int = 10) -> dict | None:
    """Extract highlights from a colorscheme by running Neovim."""
    lua_script = create_extraction_script()

    # Create the Neovim command
    # Use --headless and --clean to avoid user config interference
    # But we need plugins to be loaded for the colorschemes
    cmd = [
        "nvim",
        "--headless",
        "-u",
        "NORC",  # No vimrc
        "-c",
        f"colorscheme {colorscheme}",
        "-c",
        f'lua {lua_script}',
        "-c",
        "qall!",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Parse the JSON output from stdout
        output = result.stdout.strip()
        if output:
            # Find the JSON part (may have other output before it)
            json_start = output.find("{")
            if json_start >= 0:
                json_str = output[json_start:]
                return json.loads(json_str)

        return None
    except subprocess.TimeoutExpired:
        print(f"  Timeout extracting {colorscheme}")
        return None
    except json.JSONDecodeError as e:
        print(f"  JSON decode error for {colorscheme}: {e}")
        return None
    except Exception as e:
        print(f"  Error extracting {colorscheme}: {e}")
        return None


def find_nvim() -> str:
    """Find the nvim executable."""
    import shutil

    # Check common locations
    locations = [
        shutil.which("nvim"),
        str(Path.home() / ".local/bin/nvim"),
        "/usr/local/bin/nvim",
        "/opt/homebrew/bin/nvim",
    ]

    for loc in locations:
        if loc and Path(loc).exists():
            return loc

    return "nvim"  # Fall back to hoping it's in PATH


def extract_with_user_config(colorscheme: str, timeout: int = 15) -> dict | None:
    """Extract highlights using user's Neovim config (has all plugins)."""
    lua_script = create_extraction_script()

    nvim_path = find_nvim()

    # Use a simpler approach: write a temp Lua file and execute it
    script = f"""
vim.cmd('colorscheme {colorscheme}')
{lua_script}
vim.cmd('qall!')
"""

    cmd = [
        nvim_path,
        "--headless",
        "-c",
        f"colorscheme {colorscheme}",
        "+lua print(vim.json.encode((function() local r={} for n,h in pairs(vim.api.nvim_get_hl(0,{})) do local e={{name=n}} if h.fg then e.fg=string.format('#%06x',h.fg) end if h.bg then e.bg=string.format('#%06x',h.bg) end if h.sp then e.sp=string.format('#%06x',h.sp) end e.bold=h.bold or false e.italic=h.italic or false e.underline=h.underline or false e.undercurl=h.undercurl or false e.strikethrough=h.strikethrough or false if h.link then e.link=h.link end r[n]=e end return r end)()))",
        "+qall!",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={"HOME": str(Path.home())},  # Ensure home is set
        )

        # Parse the JSON output
        output = result.stdout.strip()
        if output:
            # Find the JSON part
            json_start = output.find("{")
            if json_start >= 0:
                json_str = output[json_start:]
                # Find the end of the JSON (last })
                brace_count = 0
                json_end = json_start
                for i, c in enumerate(json_str):
                    if c == "{":
                        brace_count += 1
                    elif c == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                json_str = json_str[:json_end]
                return json.loads(json_str)

        if result.stderr:
            # Check if it's just a "colorscheme not found" error
            if "Cannot find color scheme" in result.stderr:
                print(f"  Colorscheme not found: {colorscheme}")
            else:
                print(f"  Stderr: {result.stderr[:200]}")

        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def filter_key_highlights(all_highlights: dict) -> dict:
    """Filter to only key highlight groups we care about."""
    filtered = {}
    for group in KEY_HIGHLIGHT_GROUPS:
        if group in all_highlights:
            filtered[group] = all_highlights[group]
    return filtered


def resolve_links(highlights: dict, group_name: str, visited: set = None) -> dict | None:
    """Resolve linked highlight groups to get actual colors."""
    if visited is None:
        visited = set()

    if group_name in visited:
        return None  # Circular link

    visited.add(group_name)

    if group_name not in highlights:
        return None

    hl = highlights[group_name]
    if hl.get("link"):
        return resolve_links(highlights, hl["link"], visited)

    return hl


def extract_all_themes() -> dict[str, dict]:
    """Extract highlights from all configured colorschemes."""
    all_themes = {}

    print("Extracting highlights from colorschemes...")
    print("(This requires Neovim with plugins installed)")
    print()

    for colorscheme in COLORSCHEMES:
        print(f"  Extracting: {colorscheme}...")
        highlights = extract_with_user_config(colorscheme)

        if highlights:
            # Filter to key groups
            key_highlights = filter_key_highlights(highlights)
            all_themes[colorscheme] = {
                "all_highlights": highlights,
                "key_highlights": key_highlights,
                "total_groups": len(highlights),
                "key_groups": len(key_highlights),
            }
            print(f"    Found {len(highlights)} groups, {len(key_highlights)} key groups")
        else:
            print(f"    Failed to extract")

    return all_themes


def analyze_highlight_patterns(themes: dict) -> dict:
    """Analyze patterns across themes for key highlight groups."""
    patterns = {}

    for group in KEY_HIGHLIGHT_GROUPS:
        patterns[group] = {
            "themes": {},
            "fg_colors": set(),
            "bg_colors": set(),
            "styles": {"bold": 0, "italic": 0, "underline": 0},
        }

        for theme_name, theme_data in themes.items():
            all_hl = theme_data.get("all_highlights", {})

            # Resolve the highlight (follow links)
            resolved = resolve_links(all_hl, group)

            if resolved:
                fg = resolved.get("fg")
                bg = resolved.get("bg")

                patterns[group]["themes"][theme_name] = {
                    "fg": fg,
                    "bg": bg,
                    "bold": resolved.get("bold", False),
                    "italic": resolved.get("italic", False),
                    "underline": resolved.get("underline", False),
                }

                if fg:
                    patterns[group]["fg_colors"].add(fg)
                if bg:
                    patterns[group]["bg_colors"].add(bg)
                if resolved.get("bold"):
                    patterns[group]["styles"]["bold"] += 1
                if resolved.get("italic"):
                    patterns[group]["styles"]["italic"] += 1
                if resolved.get("underline"):
                    patterns[group]["styles"]["underline"] += 1

        # Convert sets to lists for JSON serialization
        patterns[group]["fg_colors"] = list(patterns[group]["fg_colors"])
        patterns[group]["bg_colors"] = list(patterns[group]["bg_colors"])
        patterns[group]["theme_count"] = len(patterns[group]["themes"])

    return patterns


def main():
    print("Neovim Highlight Extractor - Experiment 2")
    print("=" * 50)
    print()

    # Extract highlights
    themes = extract_all_themes()
    print()

    if not themes:
        print("No themes extracted. Make sure Neovim and colorschemes are installed.")
        sys.exit(1)

    print(f"Successfully extracted {len(themes)} themes")

    # Analyze patterns
    print()
    print("Analyzing highlight patterns...")
    patterns = analyze_highlight_patterns(themes)

    # Save results
    output_dir = Path(__file__).parent / "neovim_data"
    output_dir.mkdir(exist_ok=True)

    # Save raw highlights
    raw_path = output_dir / "highlights_raw.json"
    with open(raw_path, "w") as f:
        json.dump(themes, f, indent=2, default=str)
    print(f"Saved raw highlights: {raw_path}")

    # Save patterns
    patterns_path = output_dir / "highlight_patterns.json"
    with open(patterns_path, "w") as f:
        json.dump(patterns, f, indent=2, default=str)
    print(f"Saved patterns: {patterns_path}")

    # Print summary
    print()
    print("Highlight Pattern Summary:")
    print("-" * 60)

    # Find groups with most consistency
    print("\nMost consistent highlight groups (same style across themes):")
    for group, data in sorted(patterns.items(), key=lambda x: -x[1]["theme_count"])[:10]:
        if data["theme_count"] > 0:
            bold_pct = data["styles"]["bold"] / data["theme_count"] * 100
            italic_pct = data["styles"]["italic"] / data["theme_count"] * 100
            print(f"  {group:30} - {data['theme_count']:2} themes, "
                  f"bold={bold_pct:3.0f}%, italic={italic_pct:3.0f}%, "
                  f"{len(data['fg_colors'])} fg colors")


if __name__ == "__main__":
    main()
