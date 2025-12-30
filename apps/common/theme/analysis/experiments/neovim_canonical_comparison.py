#!/usr/bin/env python3
"""Compare Neovim colorscheme palettes against canonical base16 schemes.

Answers: Do Neovim colorscheme authors follow the original base16 specifications,
or are they creating their own interpretations?
"""

import colorsys
import math
from pathlib import Path

import yaml


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#").upper()
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """Convert RGB to CIELAB for perceptual color difference."""
    r, g, b = [x / 255.0 for x in rgb]

    # sRGB to linear
    r = ((r + 0.055) / 1.055) ** 2.4 if r > 0.04045 else r / 12.92
    g = ((g + 0.055) / 1.055) ** 2.4 if g > 0.04045 else g / 12.92
    b = ((b + 0.055) / 1.055) ** 2.4 if b > 0.04045 else b / 12.92

    # Linear RGB to XYZ
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041

    # XYZ to Lab (D65 illuminant)
    x /= 0.95047
    y /= 1.00000
    z /= 1.08883

    x = x ** (1 / 3) if x > 0.008856 else (7.787 * x) + (16 / 116)
    y = y ** (1 / 3) if y > 0.008856 else (7.787 * y) + (16 / 116)
    z = z ** (1 / 3) if z > 0.008856 else (7.787 * z) + (16 / 116)

    return (116 * y - 16, 500 * (x - y), 200 * (y - z))


def delta_e(color1: str, color2: str) -> float:
    """Calculate Delta E (CIE76) between two hex colors.

    Delta E interpretation:
    - 0-1: Not perceptible
    - 1-2: Perceptible through close observation
    - 2-10: Perceptible at a glance
    - 11-49: Colors are more similar than opposite
    - 50-100: Colors are more opposite than similar
    """
    lab1 = rgb_to_lab(hex_to_rgb(color1))
    lab2 = rgb_to_lab(hex_to_rgb(color2))
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(lab1, lab2)))


def load_canonical_schemes(schemes_dir: Path) -> dict[str, dict]:
    """Load canonical base16 schemes from tinted-theming."""
    schemes = {}

    scheme_files = {
        "nord": "nord.yaml",
        "gruvbox-dark-hard": "gruvbox-dark-hard.yaml",
        "gruvbox-dark": "gruvbox-dark-medium.yaml",
        "gruvbox-dark-soft": "gruvbox-dark-soft.yaml",
        "gruvbox-light-hard": "gruvbox-light-hard.yaml",
        "gruvbox-light": "gruvbox-light-medium.yaml",
        "gruvbox-light-soft": "gruvbox-light-soft.yaml",
        "rose-pine": "rose-pine.yaml",
        "rose-pine-moon": "rose-pine-moon.yaml",
        "rose-pine-dawn": "rose-pine-dawn.yaml",
        "kanagawa": "kanagawa.yaml",
        "kanagawa-dragon": "kanagawa-dragon.yaml",
        "solarized-dark": "solarized-dark.yaml",
        "oceanicnext": "oceanicnext.yaml",
    }

    for name, filename in scheme_files.items():
        filepath = schemes_dir / filename
        if filepath.exists():
            with open(filepath) as f:
                data = yaml.safe_load(f)
                palette = data.get("palette", data)
                schemes[name] = {
                    k: v.upper() if isinstance(v, str) else v
                    for k, v in palette.items()
                    if k.startswith("base")
                }

    return schemes


def load_neovim_palettes(palettes_file: Path) -> dict[str, dict]:
    """Load extracted Neovim palettes."""
    with open(palettes_file) as f:
        data = yaml.safe_load(f)

    palettes = {}
    for name, palette in data.items():
        palettes[name] = {
            k: v.upper() if isinstance(v, str) and v.startswith("#") else v
            for k, v in palette.items()
            if k.startswith("base")
        }

    return palettes


def compare_palettes(
    neovim: dict[str, str], canonical: dict[str, str]
) -> dict[str, any]:
    """Compare two palettes and return detailed analysis."""
    results = {
        "exact_matches": 0,
        "close_matches": 0,  # Delta E < 5
        "moderate_diff": 0,  # Delta E 5-15
        "significant_diff": 0,  # Delta E > 15
        "details": {},
        "total_delta_e": 0,
    }

    base_slots = [f"base{i:02X}" for i in range(16)]

    for slot in base_slots:
        if slot not in neovim or slot not in canonical:
            continue

        nvim_color = neovim[slot]
        canon_color = canonical[slot]

        de = delta_e(nvim_color, canon_color)
        results["total_delta_e"] += de

        status = "exact" if nvim_color == canon_color else "different"

        if nvim_color == canon_color:
            results["exact_matches"] += 1
        elif de < 5:
            results["close_matches"] += 1
        elif de < 15:
            results["moderate_diff"] += 1
        else:
            results["significant_diff"] += 1

        results["details"][slot] = {
            "neovim": nvim_color,
            "canonical": canon_color,
            "delta_e": round(de, 1),
            "status": status,
        }

    results["avg_delta_e"] = results["total_delta_e"] / len(base_slots)
    return results


def main():
    schemes_dir = Path.home() / ".local/share/tinted-theming/tinty/repos/schemes/base16"
    palettes_file = Path(__file__).parent / "neovim_data/palettes.yaml"

    print("=" * 80)
    print("NEOVIM vs CANONICAL BASE16 COMPARISON")
    print("=" * 80)
    print()

    canonical = load_canonical_schemes(schemes_dir)
    neovim = load_neovim_palettes(palettes_file)

    # Define which Neovim themes map to which canonical schemes
    mappings = [
        ("nordic", "nord", "Nordic.nvim"),
        ("nightfox-nordfox", "nord", "Nightfox Nordfox"),
        ("gruvbox-dark_hard", "gruvbox-dark-hard", "Gruvbox.nvim (dark hard)"),
        ("gruvbox-dark", "gruvbox-dark", "Gruvbox.nvim (dark medium)"),
        ("gruvbox-dark_soft", "gruvbox-dark-soft", "Gruvbox.nvim (dark soft)"),
        ("gruvbox-light_hard", "gruvbox-light-hard", "Gruvbox.nvim (light hard)"),
        ("gruvbox-light", "gruvbox-light", "Gruvbox.nvim (light medium)"),
        ("gruvbox-light_soft", "gruvbox-light-soft", "Gruvbox.nvim (light soft)"),
        ("rose-pine-main", "rose-pine", "Rose-Pine.nvim (main)"),
        ("rose-pine-moon", "rose-pine-moon", "Rose-Pine.nvim (moon)"),
        ("rose-pine-dawn", "rose-pine-dawn", "Rose-Pine.nvim (dawn)"),
        ("kanagawa-wave", "kanagawa", "Kanagawa.nvim (wave)"),
        ("kanagawa-dragon", "kanagawa-dragon", "Kanagawa.nvim (dragon)"),
        ("solarized-osaka", "solarized-dark", "Solarized-Osaka.nvim"),
        ("oceanic-next", "oceanicnext", "Oceanic-Next (VimL)"),
    ]

    # Summary data
    summaries = []

    for nvim_name, canon_name, display_name in mappings:
        if nvim_name not in neovim:
            print(f"⚠️  {nvim_name} not found in extracted palettes")
            continue
        if canon_name not in canonical:
            print(f"⚠️  {canon_name} not found in canonical schemes")
            continue

        result = compare_palettes(neovim[nvim_name], canonical[canon_name])

        summaries.append(
            {
                "name": display_name,
                "nvim": nvim_name,
                "canon": canon_name,
                "exact": result["exact_matches"],
                "close": result["close_matches"],
                "moderate": result["moderate_diff"],
                "significant": result["significant_diff"],
                "avg_de": result["avg_delta_e"],
            }
        )

    # Print summary table
    print("## Summary: How closely do Neovim themes follow canonical base16?")
    print()
    print(
        "| Theme | Exact | Close | Moderate | Significant | Avg ΔE | Verdict |"
    )
    print(
        "|-------|-------|-------|----------|-------------|--------|---------|"
    )

    for s in sorted(summaries, key=lambda x: x["avg_de"]):
        total = s["exact"] + s["close"] + s["moderate"] + s["significant"]
        match_pct = ((s["exact"] + s["close"]) / total * 100) if total else 0

        if s["avg_de"] < 3:
            verdict = "✅ Identical"
        elif s["avg_de"] < 8:
            verdict = "🟡 Close"
        elif s["avg_de"] < 15:
            verdict = "🟠 Modified"
        else:
            verdict = "🔴 Different"

        print(
            f"| {s['name'][:30]:<30} | {s['exact']:>5} | {s['close']:>5} | "
            f"{s['moderate']:>8} | {s['significant']:>11} | {s['avg_de']:>6.1f} | {verdict} |"
        )

    print()
    print("Legend:")
    print("  - Exact: Colors match exactly")
    print("  - Close: Delta E < 5 (barely perceptible)")
    print("  - Moderate: Delta E 5-15 (noticeable difference)")
    print("  - Significant: Delta E > 15 (very different color)")
    print("  - Avg ΔE: Average Delta E across all 16 base colors")
    print()

    # Detailed comparison for themes with significant differences
    print("=" * 80)
    print("DETAILED COMPARISONS")
    print("=" * 80)

    for nvim_name, canon_name, display_name in mappings:
        if nvim_name not in neovim or canon_name not in canonical:
            continue

        result = compare_palettes(neovim[nvim_name], canonical[canon_name])

        # Only show detailed diff for themes with differences
        has_diff = any(
            d["delta_e"] > 3 for d in result["details"].values()
        )
        if not has_diff:
            continue

        print(f"\n### {display_name}")
        print(f"    Neovim: {nvim_name} vs Canonical: {canon_name}")
        print()
        print("    | Slot   | Neovim  | Canonical | ΔE   | Status |")
        print("    |--------|---------|-----------|------|--------|")

        for slot in sorted(result["details"].keys()):
            d = result["details"][slot]
            status_icon = "✓" if d["delta_e"] < 3 else "≠" if d["delta_e"] < 15 else "✗"
            print(
                f"    | {slot} | {d['neovim']} | {d['canonical']} | "
                f"{d['delta_e']:>4.1f} | {status_icon}      |"
            )

    # Key insights
    print()
    print("=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80)

    # Find perfectly matching themes
    perfect = [s for s in summaries if s["avg_de"] < 1]
    close = [s for s in summaries if 1 <= s["avg_de"] < 5]
    modified = [s for s in summaries if 5 <= s["avg_de"] < 15]
    different = [s for s in summaries if s["avg_de"] >= 15]

    print()
    if perfect:
        print(f"✅ IDENTICAL ({len(perfect)} themes):")
        for s in perfect:
            print(f"   - {s['name']}")

    if close:
        print(f"\n🟡 CLOSE ({len(close)} themes):")
        for s in close:
            print(f"   - {s['name']} (avg ΔE: {s['avg_de']:.1f})")

    if modified:
        print(f"\n🟠 MODIFIED ({len(modified)} themes):")
        for s in modified:
            print(f"   - {s['name']} (avg ΔE: {s['avg_de']:.1f})")

    if different:
        print(f"\n🔴 DIFFERENT ({len(different)} themes):")
        for s in different:
            print(f"   - {s['name']} (avg ΔE: {s['avg_de']:.1f})")

    print()
    print("=" * 80)
    print("CONCLUSIONS")
    print("=" * 80)
    print()

    total_themes = len(summaries)
    faithful = len([s for s in summaries if s["avg_de"] < 5])
    pct = faithful / total_themes * 100 if total_themes else 0

    print(f"Of {total_themes} comparable theme pairs:")
    print(f"  - {faithful} ({pct:.0f}%) faithfully follow canonical base16")
    print(f"  - {total_themes - faithful} ({100-pct:.0f}%) have significant modifications")
    print()

    # Per-slot analysis
    print("Most commonly modified slots across all themes:")
    slot_diffs = {}
    for nvim_name, canon_name, _ in mappings:
        if nvim_name not in neovim or canon_name not in canonical:
            continue
        result = compare_palettes(neovim[nvim_name], canonical[canon_name])
        for slot, d in result["details"].items():
            if slot not in slot_diffs:
                slot_diffs[slot] = []
            slot_diffs[slot].append(d["delta_e"])

    print()
    print("| Slot   | Role           | Avg ΔE | Max ΔE | Modified? |")
    print("|--------|----------------|--------|--------|-----------|")

    slot_roles = {
        "base00": "Background",
        "base01": "Lighter BG",
        "base02": "Selection",
        "base03": "Comments",
        "base04": "Dark FG",
        "base05": "Foreground",
        "base06": "Light FG",
        "base07": "Lightest",
        "base08": "Red",
        "base09": "Orange",
        "base0A": "Yellow",
        "base0B": "Green",
        "base0C": "Cyan",
        "base0D": "Blue",
        "base0E": "Purple",
        "base0F": "Brown/Pink",
    }

    for slot in sorted(slot_diffs.keys()):
        diffs = slot_diffs[slot]
        avg = sum(diffs) / len(diffs)
        max_diff = max(diffs)
        modified = "Yes" if avg > 5 else "No"
        role = slot_roles.get(slot, "Unknown")
        print(f"| {slot} | {role:<14} | {avg:>6.1f} | {max_diff:>6.1f} | {modified:<9} |")


if __name__ == "__main__":
    main()
