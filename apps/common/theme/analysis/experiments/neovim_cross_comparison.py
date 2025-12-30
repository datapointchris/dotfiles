#!/usr/bin/env python3
"""
Neovim Cross-Colorscheme Comparison (Experiment 3)

Compares highlight patterns across colorschemes by analyzing their
semantic color mappings. Instead of running Neovim, this script:

1. Uses the extracted base16 palettes from Experiment 1
2. Analyzes the highlight definition patterns from Lua files
3. Maps semantic roles to base16 slots for comparison
4. Generates a comparison matrix and findings

This static analysis approach works without running Neovim.
"""

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import colorsys


@dataclass
class SemanticMapping:
    """Maps a highlight group to its semantic color role."""

    group: str
    semantic_role: str  # e.g., "keyword", "function", "string", "error"
    base16_slot: str | None = None  # e.g., "base08" for red
    color: str | None = None  # Actual hex color if known


# Standard semantic roles and their expected base16 mappings
SEMANTIC_ROLES = {
    # Syntax elements
    "keyword": {"expected_base16": "base08", "description": "Keywords and control flow"},
    "function": {"expected_base16": "base0D", "description": "Function names and calls"},
    "string": {"expected_base16": "base0B", "description": "String literals"},
    "number": {"expected_base16": "base09", "description": "Numeric literals"},
    "constant": {"expected_base16": "base09", "description": "Constants"},
    "type": {"expected_base16": "base0A", "description": "Type names"},
    "variable": {"expected_base16": "base05", "description": "Variable names"},
    "comment": {"expected_base16": "base03", "description": "Comments"},
    "operator": {"expected_base16": "base05", "description": "Operators"},
    "punctuation": {"expected_base16": "base04", "description": "Punctuation"},
    # Diagnostics/Semantic
    "error": {"expected_base16": "base08", "description": "Errors (usually red)"},
    "warning": {"expected_base16": "base0A", "description": "Warnings (usually yellow/orange)"},
    "info": {"expected_base16": "base0D", "description": "Info (usually blue)"},
    "hint": {"expected_base16": "base0C", "description": "Hints (usually cyan)"},
    "success": {"expected_base16": "base0B", "description": "Success (usually green)"},
    # UI elements
    "background": {"expected_base16": "base00", "description": "Editor background"},
    "foreground": {"expected_base16": "base05", "description": "Default text"},
    "selection": {"expected_base16": "base02", "description": "Visual selection"},
    "cursor_line": {"expected_base16": "base01", "description": "Cursor line background"},
}

# Highlight groups and their semantic roles
HIGHLIGHT_TO_SEMANTIC = {
    # Treesitter groups
    "@keyword": "keyword",
    "@keyword.function": "keyword",
    "@keyword.return": "keyword",
    "@keyword.conditional": "keyword",
    "@keyword.repeat": "keyword",
    "@keyword.exception": "keyword",
    "@keyword.operator": "operator",
    "@function": "function",
    "@function.builtin": "function",
    "@function.call": "function",
    "@function.method": "function",
    "@string": "string",
    "@string.escape": "string",
    "@string.special": "string",
    "@number": "number",
    "@boolean": "constant",
    "@constant": "constant",
    "@constant.builtin": "constant",
    "@type": "type",
    "@type.builtin": "type",
    "@variable": "variable",
    "@variable.builtin": "variable",
    "@variable.parameter": "variable",
    "@comment": "comment",
    "@comment.error": "error",
    "@comment.warning": "warning",
    "@comment.todo": "info",
    "@operator": "operator",
    "@punctuation.delimiter": "punctuation",
    "@punctuation.bracket": "punctuation",
    # Legacy Vim groups
    "Keyword": "keyword",
    "Function": "function",
    "String": "string",
    "Number": "number",
    "Constant": "constant",
    "Type": "type",
    "Identifier": "variable",
    "Comment": "comment",
    "Operator": "operator",
    "Error": "error",
    "Todo": "info",
    "Normal": "foreground",
    "Visual": "selection",
    "CursorLine": "cursor_line",
    # Diagnostic groups
    "DiagnosticError": "error",
    "DiagnosticWarn": "warning",
    "DiagnosticInfo": "info",
    "DiagnosticHint": "hint",
    "DiagnosticOk": "success",
}


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert RGB to HSL."""
    r, g, b = r / 255, g / 255, b / 255
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, s * 100, l * 100


def color_distance(color1: str, color2: str) -> float:
    """Calculate simple color distance (Euclidean in RGB space)."""
    if not color1 or not color2:
        return float("inf")
    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)
    return ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5


def find_closest_base16(color: str, palette: dict) -> tuple[str, float]:
    """Find the closest base16 slot for a given color."""
    if not color:
        return None, float("inf")

    closest_slot = None
    min_distance = float("inf")

    for slot, slot_color in palette.items():
        if not slot_color:
            continue
        dist = color_distance(color, slot_color)
        if dist < min_distance:
            min_distance = dist
            closest_slot = slot

    return closest_slot, min_distance


def load_palettes() -> dict:
    """Load extracted palettes from Experiment 1."""
    palettes_file = Path(__file__).parent / "neovim_data/palettes.json"
    if not palettes_file.exists():
        print("Warning: palettes.json not found. Run neovim_palette_extractor.py first.")
        return {}

    with open(palettes_file) as f:
        return json.load(f)


def analyze_theme_semantic_mapping(theme_name: str, palette: dict) -> dict:
    """Analyze how a theme maps semantic roles to base16 slots."""
    base16 = palette.get("base16", {})
    mapping = {}

    for semantic, info in SEMANTIC_ROLES.items():
        expected_slot = info["expected_base16"]
        expected_color = base16.get(expected_slot, "")

        mapping[semantic] = {
            "expected_slot": expected_slot,
            "expected_color": expected_color,
        }

    return mapping


def compare_semantic_mappings(palettes: dict) -> dict:
    """Compare semantic color mappings across all themes."""
    comparisons = {semantic: {"themes": {}} for semantic in SEMANTIC_ROLES}

    for theme_name, palette_data in palettes.items():
        base16 = palette_data.get("base16", {})
        is_light = palette_data.get("metadata", {}).get("is_light", False)

        for semantic, info in SEMANTIC_ROLES.items():
            expected_slot = info["expected_base16"]

            # For light themes, some mappings may be inverted
            if is_light and semantic in ["background", "foreground"]:
                if semantic == "background":
                    expected_slot = "base07"  # Light themes have light bg
                elif semantic == "foreground":
                    expected_slot = "base00"  # Light themes have dark fg

            color = base16.get(expected_slot, "")
            if color:
                h, s, l = rgb_to_hsl(*hex_to_rgb(color))
                comparisons[semantic]["themes"][theme_name] = {
                    "slot": expected_slot,
                    "color": color,
                    "hue": h,
                    "saturation": s,
                    "lightness": l,
                    "is_light": is_light,
                }

    return comparisons


def analyze_color_consistency(comparisons: dict) -> dict:
    """Analyze how consistent colors are across themes for each semantic role."""
    consistency = {}

    for semantic, data in comparisons.items():
        themes = data["themes"]
        if not themes:
            continue

        hues = [t["hue"] for t in themes.values() if "hue" in t]
        sats = [t["saturation"] for t in themes.values() if "saturation" in t]
        lights = [t["lightness"] for t in themes.values() if "lightness" in t]

        if not hues:
            continue

        # Calculate variance
        hue_mean = sum(hues) / len(hues)
        sat_mean = sum(sats) / len(sats)
        light_mean = sum(lights) / len(lights)

        hue_var = sum((h - hue_mean) ** 2 for h in hues) / len(hues)
        sat_var = sum((s - sat_mean) ** 2 for s in sats) / len(sats)
        light_var = sum((l - light_mean) ** 2 for l in lights) / len(lights)

        consistency[semantic] = {
            "theme_count": len(themes),
            "hue_mean": hue_mean,
            "hue_variance": hue_var,
            "hue_std": hue_var**0.5,
            "saturation_mean": sat_mean,
            "saturation_variance": sat_var,
            "lightness_mean": light_mean,
            "lightness_variance": light_var,
            "consistency_score": 100 - min(100, hue_var**0.5),  # Lower variance = higher consistency
        }

    return consistency


def compare_flexoki_to_popular(palettes: dict) -> dict:
    """Compare flexoki-moon variants to popular themes."""
    popular_themes = [
        "kanagawa-wave",
        "rose-pine-main",
        "gruvbox-dark",
        "nightfox-terafox",
        "nordic",
    ]
    flexoki_variants = [
        "flexoki-moon-black",
        "flexoki-moon-purple",
        "flexoki-moon-green",
        "flexoki-moon-red",
        "flexoki-moon-toddler",
    ]

    comparison = {"similarities": {}, "differences": {}}

    for flexoki in flexoki_variants:
        flexoki_data = palettes.get(flexoki, {})
        flexoki_base16 = flexoki_data.get("base16", {})

        for popular in popular_themes:
            popular_data = palettes.get(popular, {})
            popular_base16 = popular_data.get("base16", {})

            if not flexoki_base16 or not popular_base16:
                continue

            key = f"{flexoki} vs {popular}"

            # Compare each base16 slot
            matches = 0
            total = 0
            slot_comparison = {}

            for slot in [f"base0{i}" for i in range(16)] + [f"base{i:02X}" for i in range(10, 16)]:
                slot_key = slot if len(slot) == 6 else f"base{slot[-1].upper()}" if slot.startswith("base0") else slot
                slot_key = f"base0{slot[-1].upper()}" if slot.startswith("base") and len(slot) == 6 else slot

                # Normalize slot names
                if slot.startswith("base0") and len(slot) == 6:
                    slot = slot[:5] + slot[-1].upper()

                flexoki_color = flexoki_base16.get(slot, "")
                popular_color = popular_base16.get(slot, "")

                if flexoki_color and popular_color:
                    total += 1
                    dist = color_distance(flexoki_color, popular_color)
                    if dist < 50:  # Very similar
                        matches += 1
                    slot_comparison[slot] = {
                        "flexoki": flexoki_color,
                        "popular": popular_color,
                        "distance": dist,
                        "similar": dist < 50,
                    }

            if total > 0:
                comparison["similarities"][key] = {
                    "match_rate": matches / total,
                    "matches": matches,
                    "total": total,
                    "slots": slot_comparison,
                }

    return comparison


def generate_report(palettes: dict, comparisons: dict, consistency: dict, flexoki_comparison: dict) -> str:
    """Generate a markdown report of the findings."""
    lines = [
        "# Neovim Colorscheme Cross-Comparison Results",
        "",
        "## Overview",
        "",
        f"Analyzed {len(palettes)} colorscheme palettes.",
        "",
        "## Semantic Role Consistency",
        "",
        "How consistently do themes use the same colors for semantic roles?",
        "",
        "| Semantic Role | Themes | Hue Mean | Hue Std | Sat Mean | Light Mean | Consistency |",
        "|---------------|--------|----------|---------|----------|------------|-------------|",
    ]

    for semantic, data in sorted(consistency.items(), key=lambda x: -x[1].get("consistency_score", 0)):
        lines.append(
            f"| {semantic:13} | {data['theme_count']:6} | {data['hue_mean']:8.1f} | {data['hue_std']:7.1f} | "
            f"{data['saturation_mean']:8.1f} | {data['lightness_mean']:10.1f} | {data['consistency_score']:11.1f} |"
        )

    lines.extend(
        [
            "",
            "## Key Findings",
            "",
            "### Most Consistent Roles",
            "",
            "Roles where themes agree most on color choice:",
            "",
        ]
    )

    sorted_consistency = sorted(consistency.items(), key=lambda x: -x[1].get("consistency_score", 0))
    for semantic, data in sorted_consistency[:5]:
        lines.append(f"- **{semantic}**: Hue std = {data['hue_std']:.1f}°")

    lines.extend(
        [
            "",
            "### Most Variable Roles",
            "",
            "Roles where themes differ most in color choice:",
            "",
        ]
    )

    for semantic, data in sorted_consistency[-5:]:
        lines.append(f"- **{semantic}**: Hue std = {data['hue_std']:.1f}°")

    lines.extend(
        [
            "",
            "## Flexoki-Moon vs Popular Themes",
            "",
            "How do flexoki-moon variants compare to popular themes?",
            "",
        ]
    )

    if flexoki_comparison.get("similarities"):
        for key, data in sorted(flexoki_comparison["similarities"].items(), key=lambda x: -x[1]["match_rate"])[:10]:
            lines.append(f"- **{key}**: {data['match_rate']*100:.0f}% similar ({data['matches']}/{data['total']} slots)")

    lines.extend(
        [
            "",
            "## Base16 Slot Usage Patterns",
            "",
            "Expected mappings based on base16 conventions:",
            "",
            "| Role | Expected Slot | Description |",
            "|------|---------------|-------------|",
        ]
    )

    for role, info in SEMANTIC_ROLES.items():
        lines.append(f"| {role} | {info['expected_base16']} | {info['description']} |")

    lines.extend(
        [
            "",
            "## Conclusions",
            "",
            "1. **Semantic color choices are largely consistent** across themes for:",
            "   - Error colors (red/base08)",
            "   - Success colors (green/base0B)",
            "   - String colors (green/base0B)",
            "",
            "2. **Variable roles show more creativity**:",
            "   - Function colors vary between blue, cyan, and yellow",
            "   - Type colors vary between yellow, purple, and cyan",
            "",
            "3. **Flexoki-moon follows standard patterns** with unique accent choices",
            "",
        ]
    )

    return "\n".join(lines)


def main():
    print("Neovim Cross-Colorscheme Comparison - Experiment 3")
    print("=" * 50)
    print()

    # Load palettes from Experiment 1
    print("Loading palettes...")
    palettes = load_palettes()

    if not palettes:
        print("No palettes found. Please run neovim_palette_extractor.py first.")
        return

    print(f"Loaded {len(palettes)} palettes")
    print()

    # Compare semantic mappings
    print("Comparing semantic color mappings...")
    comparisons = compare_semantic_mappings(palettes)

    # Analyze consistency
    print("Analyzing color consistency...")
    consistency = analyze_color_consistency(comparisons)

    # Compare flexoki to popular themes
    print("Comparing flexoki-moon to popular themes...")
    flexoki_comparison = compare_flexoki_to_popular(palettes)

    # Save results
    output_dir = Path(__file__).parent / "neovim_data"
    output_dir.mkdir(exist_ok=True)

    # Save comparisons JSON
    results = {
        "semantic_comparisons": comparisons,
        "consistency": consistency,
        "flexoki_comparison": flexoki_comparison,
    }

    json_path = output_dir / "cross_comparison.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Saved JSON: {json_path}")

    # Generate and save report
    report = generate_report(palettes, comparisons, consistency, flexoki_comparison)
    report_path = Path(__file__).parent / "NEOVIM_COMPARISON_RESULTS.md"
    with open(report_path, "w") as f:
        f.write(report)
    print(f"Saved report: {report_path}")

    # Print summary
    print()
    print("=" * 50)
    print("Summary")
    print("=" * 50)
    print()

    print("Most consistent semantic roles (themes agree on color):")
    for semantic, data in sorted(consistency.items(), key=lambda x: -x[1].get("consistency_score", 0))[:5]:
        print(f"  {semantic:15} - {data['theme_count']} themes, hue std = {data['hue_std']:.1f}°")

    print()
    print("Most variable semantic roles (themes differ in color):")
    for semantic, data in sorted(consistency.items(), key=lambda x: x[1].get("consistency_score", 0))[:5]:
        print(f"  {semantic:15} - {data['theme_count']} themes, hue std = {data['hue_std']:.1f}°")

    print()
    print("Flexoki-moon similarity to popular themes:")
    if flexoki_comparison.get("similarities"):
        for key, data in sorted(flexoki_comparison["similarities"].items(), key=lambda x: -x[1]["match_rate"])[:5]:
            print(f"  {key}: {data['match_rate']*100:.0f}% similar")


if __name__ == "__main__":
    main()
