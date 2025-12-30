#!/usr/bin/env python3
"""
Canonical vs Omarchy Theme Comparison Experiment

This script:
1. Stores canonical base16 palettes from official sources
2. Extracts colors from omarchy theme configs
3. Compares omarchy choices to canonical palettes
4. Analyzes patterns in color selection
5. Runs ML models on canonical data
"""

import json
import math
import re
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

# Canonical Base16 palettes from tinted-theming/schemes
CANONICAL_BASE16 = {
    "catppuccin-mocha": {
        "base00": "#1e1e2e",  # base
        "base01": "#181825",  # mantle
        "base02": "#313244",  # surface0
        "base03": "#45475a",  # surface1
        "base04": "#585b70",  # surface2
        "base05": "#cdd6f4",  # text
        "base06": "#f5e0dc",  # rosewater
        "base07": "#b4befe",  # lavender
        "base08": "#f38ba8",  # red
        "base09": "#fab387",  # peach
        "base0A": "#f9e2af",  # yellow
        "base0B": "#a6e3a1",  # green
        "base0C": "#94e2d5",  # teal
        "base0D": "#89b4fa",  # blue
        "base0E": "#cba6f7",  # mauve
        "base0F": "#f2cdcd",  # flamingo
    },
    "nord": {
        "base00": "#2E3440",  # polar night 0
        "base01": "#3B4252",  # polar night 1
        "base02": "#434C5E",  # polar night 2
        "base03": "#4C566A",  # polar night 3
        "base04": "#D8DEE9",  # snow storm 0
        "base05": "#E5E9F0",  # snow storm 1
        "base06": "#ECEFF4",  # snow storm 2
        "base07": "#8FBCBB",  # frost 0
        "base08": "#BF616A",  # aurora red
        "base09": "#D08770",  # aurora orange
        "base0A": "#EBCB8B",  # aurora yellow
        "base0B": "#A3BE8C",  # aurora green
        "base0C": "#88C0D0",  # frost 2
        "base0D": "#81A1C1",  # frost 1
        "base0E": "#B48EAD",  # aurora purple
        "base0F": "#5E81AC",  # frost 3
    },
    "gruvbox-dark-hard": {
        "base00": "#1d2021",
        "base01": "#3c3836",
        "base02": "#504945",
        "base03": "#665c54",
        "base04": "#bdae93",
        "base05": "#d5c4a1",
        "base06": "#ebdbb2",
        "base07": "#fbf1c7",
        "base08": "#fb4934",
        "base09": "#fe8019",
        "base0A": "#fabd2f",
        "base0B": "#b8bb26",
        "base0C": "#8ec07c",
        "base0D": "#83a598",
        "base0E": "#d3869b",
        "base0F": "#d65d0e",
    },
    "rose-pine": {
        "base00": "#191724",  # base
        "base01": "#1f1d2e",  # surface
        "base02": "#26233a",  # overlay
        "base03": "#6e6a86",  # muted
        "base04": "#908caa",  # subtle
        "base05": "#e0def4",  # text
        "base06": "#e0def4",  # text (duplicate)
        "base07": "#524f67",  # highlight high
        "base08": "#eb6f92",  # love
        "base09": "#f6c177",  # gold
        "base0A": "#ebbcba",  # rose
        "base0B": "#31748f",  # pine
        "base0C": "#9ccfd8",  # foam
        "base0D": "#c4a7e7",  # iris
        "base0E": "#f6c177",  # gold (duplicate)
        "base0F": "#524f67",  # highlight high (duplicate)
    },
    "rose-pine-dawn": {
        "base00": "#faf4ed",  # base
        "base01": "#fffaf3",  # surface
        "base02": "#f2e9e1",  # overlay
        "base03": "#9893a5",  # muted
        "base04": "#797593",  # subtle
        "base05": "#575279",  # text
        "base06": "#575279",  # text
        "base07": "#cecacd",  # highlight high
        "base08": "#b4637a",  # love
        "base09": "#ea9d34",  # gold
        "base0A": "#d7827e",  # rose
        "base0B": "#286983",  # pine
        "base0C": "#56949f",  # foam
        "base0D": "#907aa9",  # iris
        "base0E": "#ea9d34",  # gold
        "base0F": "#cecacd",  # highlight high
    },
    "tokyo-night-storm": {
        "base00": "#24283B",
        "base01": "#16161E",
        "base02": "#343A52",
        "base03": "#444B6A",
        "base04": "#787C99",
        "base05": "#A9B1D6",
        "base06": "#CBCCD1",
        "base07": "#D5D6DB",
        "base08": "#C0CAF5",
        "base09": "#A9B1D6",
        "base0A": "#0DB9D7",
        "base0B": "#9ECE6A",
        "base0C": "#B4F9F8",
        "base0D": "#2AC3DE",
        "base0E": "#BB9AF7",
        "base0F": "#F7768E",
    },
    "kanagawa": {
        "base00": "#1F1F28",  # sumiInk3
        "base01": "#16161D",  # sumiInk0
        "base02": "#223249",  # waveBlue1
        "base03": "#54546D",  # sumiInk6
        "base04": "#727169",  # fujiGray
        "base05": "#DCD7BA",  # fujiWhite
        "base06": "#C8C093",  # oldWhite
        "base07": "#717C7C",  # katanaGray
        "base08": "#C34043",  # autumnRed
        "base09": "#FFA066",  # surimiOrange
        "base0A": "#C0A36E",  # boatYellow2
        "base0B": "#76946A",  # autumnGreen
        "base0C": "#6A9589",  # waveAqua1
        "base0D": "#7E9CD8",  # crystalBlue
        "base0E": "#957FB8",  # oniViolet
        "base0F": "#D27E99",  # sakuraPink
    },
    "everforest": {
        "base00": "#2d353b",
        "base01": "#343f44",
        "base02": "#475258",
        "base03": "#859289",
        "base04": "#9da9a0",
        "base05": "#d3c6aa",
        "base06": "#e6e2cc",
        "base07": "#fdf6e3",
        "base08": "#e67e80",
        "base09": "#e69875",
        "base0A": "#dbbc7f",
        "base0B": "#a7c080",
        "base0C": "#83c092",
        "base0D": "#7fbbb3",
        "base0E": "#d699b6",
        "base0F": "#9da9a0",
    },
}

# Extended Catppuccin palette (all 26 colors per flavor)
CATPPUCCIN_EXTENDED = {
    "mocha": {
        "rosewater": "#f5e0dc",
        "flamingo": "#f2cdcd",
        "pink": "#f5c2e7",
        "mauve": "#cba6f7",
        "red": "#f38ba8",
        "maroon": "#eba0ac",
        "peach": "#fab387",
        "yellow": "#f9e2af",
        "green": "#a6e3a1",
        "teal": "#94e2d5",
        "sky": "#89dceb",
        "sapphire": "#74c7ec",
        "blue": "#89b4fa",
        "lavender": "#b4befe",
        "text": "#cdd6f4",
        "subtext1": "#bac2de",
        "subtext0": "#a6adc8",
        "overlay2": "#9399b2",
        "overlay1": "#7f849c",
        "overlay0": "#6c7086",
        "surface2": "#585b70",
        "surface1": "#45475a",
        "surface0": "#313244",
        "base": "#1e1e2e",
        "mantle": "#181825",
        "crust": "#11111b",
    },
    "latte": {
        "rosewater": "#dc8a78",
        "flamingo": "#dd7878",
        "pink": "#ea76cb",
        "mauve": "#8839ef",
        "red": "#d20f39",
        "maroon": "#e64553",
        "peach": "#fe640b",
        "yellow": "#df8e1d",
        "green": "#40a02b",
        "teal": "#179299",
        "sky": "#04a5e5",
        "sapphire": "#209fb5",
        "blue": "#1e66f5",
        "lavender": "#7287fd",
        "text": "#4c4f69",
        "subtext1": "#5c5f77",
        "subtext0": "#6c6f85",
        "overlay2": "#7c7f93",
        "overlay1": "#8c8fa1",
        "overlay0": "#9ca0b0",
        "surface2": "#acb0be",
        "surface1": "#bcc0cc",
        "surface0": "#ccd0da",
        "base": "#eff1f5",
        "mantle": "#e6e9ef",
        "crust": "#dce0e8",
    },
}

# Original theme palettes (not base16 mapped)
ORIGINAL_PALETTES = {
    "nord": {
        # Polar Night (backgrounds)
        "nord0": "#2e3440",
        "nord1": "#3b4252",
        "nord2": "#434c5e",
        "nord3": "#4c566a",
        # Snow Storm (foregrounds)
        "nord4": "#d8dee9",
        "nord5": "#e5e9f0",
        "nord6": "#eceff4",
        # Frost (accents - blues/teals)
        "nord7": "#8fbcbb",
        "nord8": "#88c0d0",
        "nord9": "#81a1c1",
        "nord10": "#5e81ac",
        # Aurora (syntax colors)
        "nord11": "#bf616a",  # red
        "nord12": "#d08770",  # orange
        "nord13": "#ebcb8b",  # yellow
        "nord14": "#a3be8c",  # green
        "nord15": "#b48ead",  # purple
    },
    "rose-pine-main": {
        "base": "#191724",
        "surface": "#1f1d2e",
        "overlay": "#26233a",
        "muted": "#6e6a86",
        "subtle": "#908caa",
        "text": "#e0def4",
        "love": "#eb6f92",
        "gold": "#f6c177",
        "rose": "#ebbcba",
        "pine": "#31748f",
        "foam": "#9ccfd8",
        "iris": "#c4a7e7",
        "highlight_low": "#21202e",
        "highlight_med": "#403d52",
        "highlight_high": "#524f67",
    },
    "tokyo-night-storm": {
        "bg": "#24283b",
        "bg_dark": "#1f2335",
        "bg_highlight": "#292e42",
        "fg": "#c0caf5",
        "fg_dark": "#a9b1d6",
        "comment": "#565f89",
        "red": "#f7768e",
        "orange": "#ff9e64",
        "yellow": "#e0af68",
        "green": "#9ece6a",
        "cyan": "#7dcfff",
        "blue": "#7aa2f7",
        "magenta": "#bb9af7",
        "teal": "#1abc9c",
        "purple": "#9d7cd8",
    },
}


@dataclass
class ColorMatch:
    """Represents how well a color matches a palette color."""
    palette_key: str
    palette_hex: str
    distance: float
    is_exact: bool


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#").upper()
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def rgb_to_lab(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert RGB to CIELAB for perceptual comparison."""
    # Normalize RGB
    r, g, b = r / 255.0, g / 255.0, b / 255.0

    # Apply gamma correction
    def gamma(c):
        return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92

    r, g, b = gamma(r), gamma(g), gamma(b)

    # Convert to XYZ
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041

    # Normalize for D65 illuminant
    x, y, z = x / 0.95047, y / 1.0, z / 1.08883

    # Convert to Lab
    def f(t):
        return t ** (1/3) if t > 0.008856 else (7.787 * t) + (16/116)

    L = (116 * f(y)) - 16
    a = 500 * (f(x) - f(y))
    b_val = 200 * (f(y) - f(z))

    return (L, a, b_val)


def delta_e(color1: str, color2: str) -> float:
    """Calculate perceptual color difference (CIE76 Delta E)."""
    rgb1 = hex_to_rgb(color1)
    rgb2 = hex_to_rgb(color2)
    lab1 = rgb_to_lab(*rgb1)
    lab2 = rgb_to_lab(*rgb2)
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(lab1, lab2)))


def color_distance_rgb(color1: str, color2: str) -> float:
    """Calculate Euclidean distance in RGB space (normalized to 0-1)."""
    rgb1 = hex_to_rgb(color1)
    rgb2 = hex_to_rgb(color2)
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(rgb1, rgb2))) / 441.67


def find_closest_palette_match(hex_color: str, palette: dict[str, str]) -> ColorMatch:
    """Find the closest matching color in a palette."""
    best_key = None
    best_hex = None
    best_dist = float("inf")

    hex_color = hex_color.upper().lstrip("#")

    for key, pal_hex in palette.items():
        pal_hex_clean = pal_hex.upper().lstrip("#")
        if hex_color == pal_hex_clean:
            return ColorMatch(key, pal_hex, 0.0, True)

        dist = color_distance_rgb(f"#{hex_color}", pal_hex)
        if dist < best_dist:
            best_dist = dist
            best_key = key
            best_hex = pal_hex

    return ColorMatch(best_key, best_hex, best_dist, best_dist < 0.001)


def extract_colors_from_kitty(filepath: Path) -> dict[str, str]:
    """Extract all color definitions from a kitty.conf file."""
    colors = {}
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            # Match patterns like: foreground #CDD6F4 or color0 #43465A
            match = re.match(r"(\w+)\s+(#[0-9A-Fa-f]{6})", line)
            if match:
                colors[match.group(1)] = match.group(2).upper()
    return colors


def extract_colors_from_alacritty(filepath: Path) -> dict[str, str]:
    """Extract all color definitions from an alacritty.toml file."""
    colors = {}
    current_section = ""
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            # Track section headers
            if line.startswith("["):
                current_section = line.strip("[]").replace(".", "_")
                continue
            # Match color assignments (both single and double quotes)
            match = re.match(r'(\w+)\s*=\s*["\']?(#[0-9A-Fa-f]{6})["\']?', line)
            if match:
                key = f"{current_section}_{match.group(1)}" if current_section else match.group(1)
                colors[key] = match.group(2).upper()
    return colors


def analyze_omarchy_theme(theme_name: str, theme_dir: Path) -> dict:
    """Analyze an omarchy theme against canonical palettes."""
    results = {
        "theme": theme_name,
        "colors_extracted": {},
        "palette_matches": {},
        "patterns": [],
    }

    # Try to determine which canonical palette this corresponds to
    canonical_key = None
    for key in CANONICAL_BASE16:
        # Skip dawn/light variants in first pass
        if "dawn" in key or "latte" in key or "light" in key:
            continue
        if key.replace("-", "").lower() in theme_name.replace("-", "").lower():
            canonical_key = key
            break

    # Check if this might be a light theme by sampling a config file
    if canonical_key == "rose-pine":
        kitty_path = theme_dir / "kitty.conf"
        if kitty_path.exists():
            kitty_colors = extract_colors_from_kitty(kitty_path)
            bg = kitty_colors.get("background", "")
            if bg:
                rgb = hex_to_rgb(bg)
                lab = rgb_to_lab(*rgb)
                # If background is light (L > 50), it's probably dawn
                if lab[0] > 50:
                    canonical_key = "rose-pine-dawn"

    # Extract colors from available config files
    kitty_path = theme_dir / "kitty.conf"
    if kitty_path.exists():
        results["colors_extracted"]["kitty"] = extract_colors_from_kitty(kitty_path)

    alacritty_path = theme_dir / "alacritty.toml"
    if alacritty_path.exists():
        results["colors_extracted"]["alacritty"] = extract_colors_from_alacritty(alacritty_path)

    # Compare to canonical palette if we have one
    if canonical_key:
        canonical = CANONICAL_BASE16[canonical_key]
        results["canonical_palette"] = canonical_key

        # Analyze each extracted color
        for source, colors in results["colors_extracted"].items():
            results["palette_matches"][source] = {}
            for prop, hex_val in colors.items():
                match = find_closest_palette_match(hex_val, canonical)
                results["palette_matches"][source][prop] = {
                    "color": hex_val,
                    "closest_base": match.palette_key,
                    "closest_hex": match.palette_hex,
                    "distance": match.distance,
                    "is_exact": match.is_exact,
                    "delta_e": delta_e(hex_val, match.palette_hex),
                }

    return results


def analyze_catppuccin_patterns():
    """Deep dive into Catppuccin's color mapping patterns."""
    print("\n" + "=" * 60)
    print("CATPPUCCIN PATTERN ANALYSIS")
    print("=" * 60)

    mocha = CATPPUCCIN_EXTENDED["mocha"]
    base16 = CANONICAL_BASE16["catppuccin-mocha"]

    print("\n1. BASE16 MAPPING CHOICES:")
    print("-" * 40)

    # Show how Catppuccin maps its 26 colors to 16 base16 slots
    mappings = [
        ("base00", "base", "Background"),
        ("base01", "mantle", "Darker bg"),
        ("base02", "surface0", "Selection bg"),
        ("base03", "surface1", "Comments"),
        ("base04", "surface2", "Dark fg"),
        ("base05", "text", "Main text"),
        ("base06", "rosewater", "Light fg"),
        ("base07", "lavender", "Lightest"),
        ("base08", "red", "Variables"),
        ("base09", "peach", "Numbers"),
        ("base0A", "yellow", "Classes"),
        ("base0B", "green", "Strings"),
        ("base0C", "teal", "Constants"),
        ("base0D", "blue", "Functions"),
        ("base0E", "mauve", "Keywords"),
        ("base0F", "flamingo", "Deprecated"),
    ]

    for base_key, cat_name, role in mappings:
        base_hex = base16[base_key]
        cat_hex = mocha.get(cat_name, "N/A")
        match = "✓" if base_hex.upper() == cat_hex.upper() else "≠"
        print(f"  {base_key} → {cat_name:12} ({role:12}) {match}")

    print("\n2. EXCLUDED COLORS (not in base16):")
    print("-" * 40)
    base16_colors = set(h.upper() for h in base16.values())
    for name, hex_val in mocha.items():
        if hex_val.upper() not in base16_colors:
            print(f"  {name:12} {hex_val}")

    print("\n3. COLOR RELATIONSHIPS:")
    print("-" * 40)

    # Analyze lightness progression
    from_base = ["base00", "base01", "base02", "base03", "base04", "base05", "base06", "base07"]
    print("  Background → Foreground lightness progression:")
    for key in from_base:
        hex_val = base16[key]
        rgb = hex_to_rgb(hex_val)
        lab = rgb_to_lab(*rgb)
        print(f"    {key}: L={lab[0]:.1f}")


def compare_omarchy_to_canonical():
    """Compare omarchy themes to their canonical base16 equivalents."""
    print("\n" + "=" * 60)
    print("OMARCHY vs CANONICAL COMPARISON")
    print("=" * 60)

    omarchy_dir = Path.home() / "code/hypr/omarchy/themes"
    themes_to_analyze = [
        "catppuccin",
        "nord",
        "gruvbox",
        "rose-pine",
        "tokyo-night",
        "kanagawa",
        "everforest",
    ]

    all_results = {}

    for theme_name in themes_to_analyze:
        theme_dir = omarchy_dir / theme_name
        if not theme_dir.exists():
            print(f"\n⚠️  Theme not found: {theme_name}")
            continue

        results = analyze_omarchy_theme(theme_name, theme_dir)
        all_results[theme_name] = results

        print(f"\n{'─' * 40}")
        print(f"Theme: {theme_name}")
        print(f"{'─' * 40}")

        if "canonical_palette" in results:
            print(f"Canonical: {results['canonical_palette']}")

            # Summarize matches
            for source, matches in results["palette_matches"].items():
                exact = sum(1 for m in matches.values() if m["is_exact"])
                close = sum(1 for m in matches.values() if m["delta_e"] < 5 and not m["is_exact"])
                far = sum(1 for m in matches.values() if m["delta_e"] >= 5)
                total = len(matches)

                print(f"\n  {source}:")
                if total == 0:
                    print(f"    No colors extracted")
                    continue
                print(f"    Exact matches: {exact}/{total} ({100*exact/total:.0f}%)")
                print(f"    Close (ΔE<5):  {close}/{total} ({100*close/total:.0f}%)")
                print(f"    Far (ΔE≥5):    {far}/{total} ({100*far/total:.0f}%)")

                # Show non-exact matches
                if far > 0:
                    print(f"    Non-matching colors:")
                    for prop, m in sorted(matches.items(), key=lambda x: -x[1]["delta_e"]):
                        if m["delta_e"] >= 5:
                            print(f"      {prop}: {m['color']} → {m['closest_base']} (ΔE={m['delta_e']:.1f})")

    return all_results


def analyze_semantic_patterns(all_results: dict):
    """Analyze patterns in how properties map to palette colors."""
    print("\n" + "=" * 60)
    print("SEMANTIC MAPPING PATTERNS")
    print("=" * 60)

    # Aggregate property → base16 mappings across all themes
    property_to_base = defaultdict(list)

    for theme_name, results in all_results.items():
        for source, matches in results.get("palette_matches", {}).items():
            for prop, match in matches.items():
                if match["is_exact"] or match["delta_e"] < 5:
                    # Normalize property name
                    prop_normalized = prop.lower().replace("_", "")
                    property_to_base[prop_normalized].append(match["closest_base"])

    print("\nConsistent property → base16 mappings:")
    print("-" * 40)

    for prop, bases in sorted(property_to_base.items()):
        if len(bases) >= 2:
            from collections import Counter
            counts = Counter(bases)
            most_common = counts.most_common(1)[0]
            consistency = most_common[1] / len(bases)
            if consistency >= 0.5:
                print(f"  {prop:30} → {most_common[0]:8} ({100*consistency:.0f}% of {len(bases)} themes)")


def generate_experiment_report(all_results: dict):
    """Generate a markdown report of experiment findings."""
    report_path = Path(__file__).parent / "CANONICAL_COMPARISON_RESULTS.md"

    with open(report_path, "w") as f:
        f.write("# Canonical vs Omarchy Theme Comparison\n\n")
        f.write("## Overview\n\n")
        f.write("This experiment compares omarchy themes to their canonical base16 equivalents\n")
        f.write("to understand color selection patterns.\n\n")

        f.write("## Key Findings\n\n")

        # Calculate aggregate statistics
        total_exact = 0
        total_colors = 0
        total_close = 0

        for theme_name, results in all_results.items():
            for source, matches in results.get("palette_matches", {}).items():
                for prop, match in matches.items():
                    total_colors += 1
                    if match["is_exact"]:
                        total_exact += 1
                    elif match["delta_e"] < 5:
                        total_close += 1

        if total_colors > 0:
            f.write(f"- **Exact matches**: {total_exact}/{total_colors} ({100*total_exact/total_colors:.1f}%)\n")
            f.write(f"- **Close matches (ΔE<5)**: {total_close}/{total_colors} ({100*total_close/total_colors:.1f}%)\n")
            f.write(f"- **Total acceptable**: {total_exact + total_close}/{total_colors} ({100*(total_exact + total_close)/total_colors:.1f}%)\n\n")

        f.write("## Theme-by-Theme Analysis\n\n")

        for theme_name, results in all_results.items():
            f.write(f"### {theme_name}\n\n")
            if "canonical_palette" in results:
                f.write(f"Canonical palette: `{results['canonical_palette']}`\n\n")

                for source, matches in results.get("palette_matches", {}).items():
                    exact = sum(1 for m in matches.values() if m["is_exact"])
                    close = sum(1 for m in matches.values() if m["delta_e"] < 5 and not m["is_exact"])
                    total = len(matches)

                    f.write(f"**{source}**: {exact} exact, {close} close out of {total} colors\n\n")

                    # Table of non-matching colors
                    non_matches = [(p, m) for p, m in matches.items() if m["delta_e"] >= 5]
                    if non_matches:
                        f.write("| Property | Color | Closest Base | ΔE |\n")
                        f.write("|----------|-------|--------------|----|\n")
                        for prop, m in sorted(non_matches, key=lambda x: -x[1]["delta_e"]):
                            f.write(f"| {prop} | {m['color']} | {m['closest_base']} | {m['delta_e']:.1f} |\n")
                        f.write("\n")
            f.write("\n")

        f.write("## Catppuccin Pattern Analysis\n\n")
        f.write("Catppuccin uses 26 named colors but maps them to 16 base16 slots:\n\n")
        f.write("| Base16 | Catppuccin Name | Semantic Role |\n")
        f.write("|--------|-----------------|---------------|\n")
        f.write("| base00 | base | Background |\n")
        f.write("| base01 | mantle | Darker background |\n")
        f.write("| base02 | surface0 | Selection background |\n")
        f.write("| base03 | surface1 | Comments |\n")
        f.write("| base04 | surface2 | Dark foreground |\n")
        f.write("| base05 | text | Main text |\n")
        f.write("| base06 | rosewater | Light foreground |\n")
        f.write("| base07 | lavender | Lightest |\n")
        f.write("| base08 | red | Variables/Errors |\n")
        f.write("| base09 | peach | Numbers |\n")
        f.write("| base0A | yellow | Classes |\n")
        f.write("| base0B | green | Strings |\n")
        f.write("| base0C | teal | Constants |\n")
        f.write("| base0D | blue | Functions |\n")
        f.write("| base0E | mauve | Keywords |\n")
        f.write("| base0F | flamingo | Deprecated |\n\n")

        f.write("**Excluded from base16**: pink, maroon, sky, sapphire, subtext0/1, overlay0/1/2, crust\n\n")

    print(f"\nReport saved to: {report_path}")


def main():
    print("=" * 60)
    print("CANONICAL vs OMARCHY THEME COMPARISON EXPERIMENT")
    print("=" * 60)

    # Analyze Catppuccin's patterns in detail
    analyze_catppuccin_patterns()

    # Compare omarchy themes to canonical
    all_results = compare_omarchy_to_canonical()

    # Analyze semantic patterns
    if all_results:
        analyze_semantic_patterns(all_results)

    # Generate report
    if all_results:
        generate_experiment_report(all_results)

    print("\n" + "=" * 60)
    print("EXPERIMENT COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
