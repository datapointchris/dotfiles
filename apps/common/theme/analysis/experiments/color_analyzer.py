#!/usr/bin/env python3
"""
Color Scheme Analysis Tool

Analyzes omarchy's hand-crafted color schemes to discover patterns
that can be used to algorithmically generate cohesive themes.

Uses OKLCH color space for perceptually uniform comparisons.
"""

import colorsys
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Color:
    """RGB color with conversion utilities."""
    r: int
    g: int
    b: int

    @classmethod
    def from_hex(cls, hex_str: str) -> "Color":
        """Parse hex color string (#RRGGBB or #RGB)."""
        h = hex_str.lstrip("#").lower()
        if len(h) == 3:
            h = "".join([c * 2 for c in h])
        return cls(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    def to_hex(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

    def to_rgb_normalized(self) -> tuple[float, float, float]:
        return (self.r / 255.0, self.g / 255.0, self.b / 255.0)

    def to_hsl(self) -> tuple[float, float, float]:
        """Convert to HSL (hue 0-360, sat 0-100, light 0-100)."""
        r, g, b = self.to_rgb_normalized()
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        return (h * 360, s * 100, l * 100)

    def to_oklab(self) -> tuple[float, float, float]:
        """Convert to OKLab color space for perceptual uniformity."""
        r, g, b = self.to_rgb_normalized()

        # Linear RGB
        def to_linear(c):
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

        lr, lg, lb = to_linear(r), to_linear(g), to_linear(b)

        # XYZ
        l = 0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb
        m = 0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb
        s = 0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb

        l_, m_, s_ = l ** (1/3), m ** (1/3), s ** (1/3)

        L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
        a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
        b_ = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_

        return (L, a, b_)

    def to_oklch(self) -> tuple[float, float, float]:
        """Convert to OKLCH (Lightness, Chroma, Hue)."""
        L, a, b = self.to_oklab()
        C = math.sqrt(a * a + b * b)
        H = math.degrees(math.atan2(b, a)) % 360
        return (L * 100, C * 100, H)  # Scale for readability

    def perceptual_distance(self, other: "Color") -> float:
        """Calculate perceptual distance using OKLab deltaE."""
        L1, a1, b1 = self.to_oklab()
        L2, a2, b2 = other.to_oklab()
        return math.sqrt((L1 - L2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2)

    def lightness_diff(self, other: "Color") -> float:
        """Lightness difference in OKLCH."""
        L1, _, _ = self.to_oklch()
        L2, _, _ = other.to_oklch()
        return L2 - L1

    def chroma_diff(self, other: "Color") -> float:
        """Chroma difference in OKLCH."""
        _, C1, _ = self.to_oklch()
        _, C2, _ = other.to_oklch()
        return C2 - C1

    def hue_diff(self, other: "Color") -> float:
        """Hue difference in OKLCH (shortest arc)."""
        _, _, H1 = self.to_oklch()
        _, _, H2 = other.to_oklch()
        diff = H2 - H1
        if diff > 180:
            diff -= 360
        elif diff < -180:
            diff += 360
        return diff


def extract_btop_colors(filepath: Path) -> dict[str, str]:
    """Extract colors from a btop theme file."""
    colors = {}
    content = filepath.read_text()
    for match in re.finditer(r'theme\[(\w+)\]="(#[0-9a-fA-F]{6})"', content):
        colors[match.group(1)] = match.group(2)
    return colors


def extract_waybar_colors(filepath: Path) -> dict[str, str]:
    """Extract colors from a waybar CSS file."""
    colors = {}
    content = filepath.read_text()
    for match in re.finditer(r'@define-color\s+(\w+)\s+(#[0-9a-fA-F]{6})', content):
        colors[match.group(1)] = match.group(2)
    return colors


def extract_kitty_colors(filepath: Path) -> dict[str, str]:
    """Extract colors from a kitty config file."""
    colors = {}
    content = filepath.read_text()
    for line in content.split("\n"):
        match = re.match(r'^(\w+)\s+(#[0-9a-fA-F]{6})', line.strip())
        if match:
            colors[match.group(1)] = match.group(2)
    return colors


def find_closest_base_color(target: Color, base_colors: dict[str, Color]) -> tuple[Optional[str], float]:
    """Find which base color is closest to the target."""
    if not base_colors:
        return None, float("inf")
    closest = None
    min_dist = float("inf")
    for name, color in base_colors.items():
        dist = target.perceptual_distance(color)
        if dist < min_dist:
            min_dist = dist
            closest = name
    return closest, min_dist


def analyze_theme(omarchy_path: Path, our_palette: dict) -> dict:
    """Analyze a single omarchy theme against our palette."""
    theme_name = omarchy_path.name
    results = {"theme": theme_name, "mappings": {}}

    # Load base colors from our palette
    base_colors = {}
    if "palette" in our_palette:
        for key, value in our_palette["palette"].items():
            base_colors[key] = Color.from_hex(value)
    if "ansi" in our_palette:
        for key, value in our_palette["ansi"].items():
            base_colors[f"ansi_{key}"] = Color.from_hex(value)

    # Analyze btop
    btop_file = omarchy_path / "btop.theme"
    if btop_file.exists():
        btop_colors = extract_btop_colors(btop_file)
        results["mappings"]["btop"] = {}
        for prop, hex_color in btop_colors.items():
            target = Color.from_hex(hex_color)
            closest, dist = find_closest_base_color(target, base_colors)
            if closest is None:
                continue
            base = base_colors[closest]

            results["mappings"]["btop"][prop] = {
                "target": hex_color,
                "closest_base": closest,
                "base_color": base.to_hex(),
                "distance": round(dist, 4),
                "lightness_shift": round(target.lightness_diff(base), 2),
                "chroma_shift": round(target.chroma_diff(base), 2),
                "hue_shift": round(target.hue_diff(base), 2),
                "target_oklch": [round(x, 2) for x in target.to_oklch()],
                "base_oklch": [round(x, 2) for x in base.to_oklch()],
            }

    return results


def print_analysis_summary(results: list[dict]):
    """Print a summary of the analysis."""
    print("\n" + "=" * 80)
    print("COLOR MAPPING ANALYSIS SUMMARY")
    print("=" * 80)

    # Collect all btop mappings across themes
    btop_mappings = {}
    for result in results:
        if "btop" in result.get("mappings", {}):
            for prop, data in result["mappings"]["btop"].items():
                if prop not in btop_mappings:
                    btop_mappings[prop] = []
                btop_mappings[prop].append({
                    "theme": result["theme"],
                    **data
                })

    # Analyze each btop property
    print("\n### BTOP PROPERTY ANALYSIS ###\n")
    for prop in sorted(btop_mappings.keys()):
        mappings = btop_mappings[prop]
        print(f"\n{prop}:")
        print("-" * 40)

        # Count which base colors are used
        base_counts = {}
        for m in mappings:
            base = m["closest_base"]
            base_counts[base] = base_counts.get(base, 0) + 1

        # Show most common base color
        sorted_bases = sorted(base_counts.items(), key=lambda x: -x[1])
        print(f"  Base color usage:")
        for base, count in sorted_bases[:3]:
            pct = count / len(mappings) * 100
            print(f"    {base}: {count}/{len(mappings)} ({pct:.0f}%)")

        # Show transformation stats
        l_shifts = [m["lightness_shift"] for m in mappings]
        c_shifts = [m["chroma_shift"] for m in mappings]

        avg_l = sum(l_shifts) / len(l_shifts)
        avg_c = sum(c_shifts) / len(c_shifts)
        print(f"  Avg lightness shift: {avg_l:+.2f}")
        print(f"  Avg chroma shift: {avg_c:+.2f}")

        # Show example mappings
        print(f"  Examples:")
        for m in mappings[:3]:
            print(f"    {m['theme']}: {m['target']} ← {m['closest_base']} ({m['base_color']}) dist={m['distance']:.3f}")


def main():
    omarchy_dir = Path.home() / "code/hypr/omarchy/themes"
    our_themes_dir = Path.home() / "dotfiles/apps/common/theme/library"

    # Themes that exist in both
    common_themes = {
        "nord": "nord",
        "kanagawa": "kanagawa",
        "gruvbox": "gruvbox-dark-hard",
        "rose-pine": "rose-pine",
        "tokyo-night": "tokyo-night",
        "everforest": "everforest",
        "catppuccin": "catppuccin-mocha",
    }

    results = []

    for omarchy_name, our_name in common_themes.items():
        omarchy_path = omarchy_dir / omarchy_name
        our_path = our_themes_dir / our_name / "palette.yml"

        if not omarchy_path.exists():
            print(f"Skipping {omarchy_name}: omarchy theme not found")
            continue

        if not our_path.exists():
            print(f"Skipping {our_name}: our palette not found")
            continue

        # Parse our YAML palette (simple parser for this format)
        our_palette = {}
        current_section = None
        for line in our_path.read_text().split("\n"):
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            # Check for section headers
            if not line.startswith(" ") and ":" in line:
                key = line.split(":")[0].strip()
                if key in ("palette", "ansi", "special"):
                    current_section = key
                    our_palette[current_section] = {}
            # Check for key-value pairs under a section
            elif line.startswith("  ") and ":" in line and current_section:
                parts = stripped.split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    # Extract hex color, handling comments
                    value_part = parts[1].strip()
                    # Remove inline comments but preserve the hex color
                    if "#" in value_part:
                        # Find the hex color pattern
                        import re
                        hex_match = re.search(r'(#[0-9a-fA-F]{6})', value_part)
                        if hex_match:
                            our_palette[current_section][key] = hex_match.group(1)

        result = analyze_theme(omarchy_path, our_palette)
        results.append(result)
        print(f"Analyzed: {omarchy_name} → {our_name}")

    print_analysis_summary(results)

    # Save detailed results
    output_path = Path(__file__).parent / "analysis_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to: {output_path}")


if __name__ == "__main__":
    main()
