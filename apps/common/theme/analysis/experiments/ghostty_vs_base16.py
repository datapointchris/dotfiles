#!/usr/bin/env python3
"""Compare Ghostty terminal themes to base16 canonical schemes.

ANSI Terminal Palette (Ghostty format):
  0=black, 1=red, 2=green, 3=yellow, 4=blue, 5=magenta, 6=cyan, 7=white
  8-15 = bright variants

Base16 Palette:
  base00-03: background shades (darkest to lighter)
  base04-07: foreground shades (dark to light)
  base08-0F: accent colors (red, orange, yellow, green, cyan, blue, purple, brown)

Standard mapping (base16 → ANSI):
  base00 → background
  base05 → foreground
  base08 → ANSI 1/9 (red)
  base0A → ANSI 3/11 (yellow)
  base0B → ANSI 2/10 (green)
  base0C → ANSI 6/14 (cyan)
  base0D → ANSI 4/12 (blue)
  base0E → ANSI 5/13 (magenta/purple)
"""

import math
from pathlib import Path
import re

import yaml


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#").upper()
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """Convert RGB to CIELAB."""
    r, g, b = [x / 255.0 for x in rgb]
    r = ((r + 0.055) / 1.055) ** 2.4 if r > 0.04045 else r / 12.92
    g = ((g + 0.055) / 1.055) ** 2.4 if g > 0.04045 else g / 12.92
    b = ((b + 0.055) / 1.055) ** 2.4 if b > 0.04045 else b / 12.92
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    x /= 0.95047
    y /= 1.00000
    z /= 1.08883
    x = x ** (1 / 3) if x > 0.008856 else (7.787 * x) + (16 / 116)
    y = y ** (1 / 3) if y > 0.008856 else (7.787 * y) + (16 / 116)
    z = z ** (1 / 3) if z > 0.008856 else (7.787 * z) + (16 / 116)
    return (116 * y - 16, 500 * (x - y), 200 * (y - z))


def delta_e(color1: str, color2: str) -> float:
    """Calculate Delta E between two hex colors."""
    lab1 = rgb_to_lab(hex_to_rgb(color1))
    lab2 = rgb_to_lab(hex_to_rgb(color2))
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(lab1, lab2)))


def parse_ghostty_theme(filepath: Path) -> dict:
    """Parse a ghostty theme file."""
    theme = {"palette": {}}
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line.startswith("palette = "):
                parts = line.replace("palette = ", "").split("=")
                if len(parts) == 2:
                    idx, color = parts
                    theme["palette"][int(idx)] = color.upper()
            elif line.startswith("background = "):
                theme["background"] = line.split("=")[1].strip().upper()
            elif line.startswith("foreground = "):
                theme["foreground"] = line.split("=")[1].strip().upper()
    return theme


def load_base16_scheme(filepath: Path) -> dict:
    """Load a base16 scheme."""
    with open(filepath) as f:
        data = yaml.safe_load(f)
    palette = data.get("palette", data)
    return {k: v.upper() for k, v in palette.items() if k.startswith("base")}


def compare_themes(ghostty: dict, base16: dict) -> dict:
    """Compare ghostty theme to base16 scheme."""
    # Standard mapping: base16 slot -> (ghostty key, description)
    mappings = [
        ("base00", "background", "Background"),
        ("base05", "foreground", "Foreground"),
        ("base08", 1, "Red (ANSI 1)"),
        ("base08", 9, "Bright Red (ANSI 9)"),
        ("base0A", 3, "Yellow (ANSI 3)"),
        ("base0A", 11, "Bright Yellow (ANSI 11)"),
        ("base0B", 2, "Green (ANSI 2)"),
        ("base0B", 10, "Bright Green (ANSI 10)"),
        ("base0C", 6, "Cyan (ANSI 6)"),
        ("base0C", 14, "Bright Cyan (ANSI 14)"),
        ("base0D", 4, "Blue (ANSI 4)"),
        ("base0D", 12, "Bright Blue (ANSI 12)"),
        ("base0E", 5, "Magenta (ANSI 5)"),
        ("base0E", 13, "Bright Magenta (ANSI 13)"),
    ]

    results = []
    for base_slot, ghostty_key, desc in mappings:
        base_color = base16.get(base_slot)
        if isinstance(ghostty_key, int):
            ghostty_color = ghostty.get("palette", {}).get(ghostty_key)
        else:
            ghostty_color = ghostty.get(ghostty_key)

        if base_color and ghostty_color:
            de = delta_e(base_color, ghostty_color)
            match = "✓" if de < 1 else "≈" if de < 5 else "≠" if de < 15 else "✗"
            results.append({
                "base_slot": base_slot,
                "ghostty_key": ghostty_key,
                "description": desc,
                "base16": base_color,
                "ghostty": ghostty_color,
                "delta_e": de,
                "match": match,
            })

    return results


def main():
    ghostty_dir = Path("/Applications/Ghostty.app/Contents/Resources/ghostty/themes")
    base16_dir = Path.home() / ".local/share/tinted-theming/tinty/repos/schemes/base16"

    print("=" * 90)
    print("GHOSTTY THEMES vs BASE16 CANONICAL SCHEMES")
    print("=" * 90)
    print()
    print("Comparing whether Ghostty and base16 use the same source colors.")
    print()

    # Theme mappings: (ghostty_name, base16_file)
    theme_pairs = [
        ("Nord", "nord.yaml"),
        ("Gruvbox Dark Hard", "gruvbox-dark-hard.yaml"),
        ("Gruvbox Dark", "gruvbox-dark-medium.yaml"),
        ("Gruvbox Light", "gruvbox-light-medium.yaml"),
        ("Rose Pine", "rose-pine.yaml"),
        ("Rose Pine Moon", "rose-pine-moon.yaml"),
        ("Rose Pine Dawn", "rose-pine-dawn.yaml"),
        ("Kanagawa Wave", "kanagawa.yaml"),
        ("Kanagawa Dragon", "kanagawa-dragon.yaml"),
        ("Oceanic Next", "oceanicnext.yaml"),
    ]

    summaries = []

    for ghostty_name, base16_file in theme_pairs:
        ghostty_path = ghostty_dir / ghostty_name
        base16_path = base16_dir / base16_file

        if not ghostty_path.exists():
            print(f"⚠️  Ghostty theme not found: {ghostty_name}")
            continue
        if not base16_path.exists():
            print(f"⚠️  Base16 scheme not found: {base16_file}")
            continue

        ghostty = parse_ghostty_theme(ghostty_path)
        base16 = load_base16_scheme(base16_path)
        results = compare_themes(ghostty, base16)

        avg_de = sum(r["delta_e"] for r in results) / len(results) if results else 0
        exact = sum(1 for r in results if r["delta_e"] < 1)
        close = sum(1 for r in results if 1 <= r["delta_e"] < 5)
        diff = sum(1 for r in results if r["delta_e"] >= 5)

        summaries.append({
            "name": ghostty_name,
            "avg_de": avg_de,
            "exact": exact,
            "close": close,
            "diff": diff,
            "results": results,
        })

    # Print summary
    print("## Summary: Do Ghostty themes match base16 canonical schemes?")
    print()
    print("| Theme                | Exact | Close | Different | Avg ΔE | Verdict |")
    print("|----------------------|-------|-------|-----------|--------|---------|")

    for s in sorted(summaries, key=lambda x: x["avg_de"]):
        if s["avg_de"] < 1:
            verdict = "✅ Same source"
        elif s["avg_de"] < 5:
            verdict = "🟡 Very close"
        elif s["avg_de"] < 15:
            verdict = "🟠 Different"
        else:
            verdict = "🔴 Very different"

        print(
            f"| {s['name']:<20} | {s['exact']:>5} | {s['close']:>5} | "
            f"{s['diff']:>9} | {s['avg_de']:>6.1f} | {verdict} |"
        )

    print()
    print("Legend: Exact = ΔE < 1, Close = ΔE 1-5, Different = ΔE > 5")
    print()

    # Detailed analysis for themes with differences
    print("=" * 90)
    print("DETAILED COMPARISONS (showing themes with differences)")
    print("=" * 90)

    for s in summaries:
        if s["avg_de"] < 1:
            continue

        print(f"\n### {s['name']}")
        print()
        print("| Role          | Base16  | Ghostty | ΔE   | Match |")
        print("|---------------|---------|---------|------|-------|")

        for r in s["results"]:
            print(
                f"| {r['description']:<13} | {r['base16']} | {r['ghostty']} | "
                f"{r['delta_e']:>4.1f} | {r['match']:>5} |"
            )

    # Conclusions
    print()
    print("=" * 90)
    print("CONCLUSIONS")
    print("=" * 90)
    print()

    same_source = sum(1 for s in summaries if s["avg_de"] < 5)
    different = len(summaries) - same_source

    print(f"Of {len(summaries)} theme pairs compared:")
    print(f"  - {same_source} appear to use the same/similar source colors")
    print(f"  - {different} have notable differences")
    print()

    # Find patterns
    if different > 0:
        print("Common differences observed:")
        print()

        # Check if bright variants are consistently different
        bright_diffs = []
        for s in summaries:
            for r in s["results"]:
                if "Bright" in r["description"] and r["delta_e"] > 5:
                    bright_diffs.append((s["name"], r["description"], r["delta_e"]))

        if bright_diffs:
            print("  - Bright color variants often differ (normal vs bright ANSI)")
            for name, desc, de in bright_diffs[:5]:
                print(f"    - {name}: {desc} (ΔE={de:.1f})")


if __name__ == "__main__":
    main()
