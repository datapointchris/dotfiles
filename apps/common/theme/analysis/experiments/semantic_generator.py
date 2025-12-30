#!/usr/bin/env python3
"""
Semantic Color Generator - Proof of Concept

Generates btop themes using semantic role mapping based on theme philosophy,
combined with OKLCH perceptual gradients.
"""

import colorsys
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Color:
    """RGB color with OKLCH conversion."""
    r: int
    g: int
    b: int

    @classmethod
    def from_hex(cls, hex_str: str) -> "Color":
        h = hex_str.lstrip("#").lower()
        if len(h) == 3:
            h = "".join([c * 2 for c in h])
        return cls(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    def to_hex(self) -> str:
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

    def to_oklch(self) -> tuple[float, float, float]:
        """Convert to OKLCH (Lightness 0-100, Chroma 0-~30, Hue 0-360)."""
        r, g, b = self.r / 255.0, self.g / 255.0, self.b / 255.0

        def to_linear(c):
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

        lr, lg, lb = to_linear(r), to_linear(g), to_linear(b)

        l = 0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb
        m = 0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb
        s = 0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb

        l_, m_, s_ = (
            l ** (1/3) if l > 0 else 0,
            m ** (1/3) if m > 0 else 0,
            s ** (1/3) if s > 0 else 0
        )

        L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
        a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
        b_ = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_

        C = math.sqrt(a * a + b_ * b_)
        H = math.degrees(math.atan2(b_, a)) % 360

        return (L * 100, C * 100, H)


def oklch_to_rgb(L: float, C: float, H: float) -> Color:
    """Convert OKLCH to RGB Color."""
    L = L / 100  # Normalize to 0-1
    C = C / 100

    a = C * math.cos(math.radians(H))
    b = C * math.sin(math.radians(H))

    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b

    l = l_ ** 3
    m = m_ ** 3
    s = s_ ** 3

    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b_ = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s

    def from_linear(c):
        c = max(0, min(1, c))
        return c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1/2.4)) - 0.055

    r = int(round(from_linear(r) * 255))
    g = int(round(from_linear(g) * 255))
    b_ = int(round(from_linear(b_) * 255))

    return Color(
        max(0, min(255, r)),
        max(0, min(255, g)),
        max(0, min(255, b_))
    )


def interpolate_oklch(c1: Color, c2: Color, t: float) -> Color:
    """Interpolate between two colors in OKLCH space."""
    L1, C1, H1 = c1.to_oklch()
    L2, C2, H2 = c2.to_oklch()

    # Handle hue interpolation (shortest path)
    h_diff = H2 - H1
    if h_diff > 180:
        h_diff -= 360
    elif h_diff < -180:
        h_diff += 360

    L = L1 + t * (L2 - L1)
    C = C1 + t * (C2 - C1)
    H = (H1 + t * h_diff) % 360

    return oklch_to_rgb(L, C, H)


# Theme philosophy definitions
PHILOSOPHIES = {
    "monochromatic": {
        "description": "Same hue family with varying intensity (Nord-style)",
        "border": "base03",
        "highlight": "base0F",
        "gradient_low": "base0D",
        "gradient_mid": "base0C",
        "gradient_high": "base06",
        "use_traffic_light_cpu": False,
    },
    "traffic_light": {
        "description": "Green→Yellow→Red semantic gradients (Kanagawa/Gruvbox)",
        "border": "base01",
        "highlight": "base08",
        "gradient_low": "ansi_bright_green",
        "gradient_mid": "base0A",
        "gradient_high": "base09",
        "use_traffic_light_cpu": True,
    },
    "accent_per_box": {
        "description": "Each UI element has distinct accent (Rose-Pine)",
        "border": None,  # Each box is different
        "cpu_box": "base0C",
        "mem_box": "base0B",
        "net_box": "base0E",
        "proc_box": "base08",
        "highlight": "base04",
        "gradient_low": "base0A",
        "gradient_mid": "base0C",
        "gradient_high": "base08",
        "use_traffic_light_cpu": True,
    }
}

# Which philosophy to use for each theme
THEME_PHILOSOPHIES = {
    "nord": "monochromatic",
    "gruvbox-dark-hard": "traffic_light",
    "kanagawa": "traffic_light",
    "tokyo-night": "traffic_light",
    "everforest": "traffic_light",
    "rose-pine": "accent_per_box",
    "catppuccin-mocha": "traffic_light",
}

# Default philosophy for themes not in the list
DEFAULT_PHILOSOPHY = "traffic_light"


def load_palette(palette_path: Path) -> dict[str, str]:
    """Load colors from palette.yml."""
    colors = {}
    current_section = None

    for line in palette_path.read_text().split("\n"):
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue

        if not line.startswith(" ") and ":" in line:
            key = line.split(":")[0].strip()
            if key in ("palette", "ansi", "special"):
                current_section = key

        elif line.startswith("  ") and ":" in line and current_section:
            parts = stripped.split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                hex_match = re.search(r'(#[0-9a-fA-F]{6})', parts[1])
                if hex_match:
                    # Use section prefix for ansi colors
                    if current_section == "ansi":
                        colors[f"ansi_{key}"] = hex_match.group(1)
                    else:
                        colors[key] = hex_match.group(1)

    return colors


def get_color(palette: dict[str, str], role: str) -> Optional[str]:
    """Get color from palette by role name."""
    if role is None:
        return None
    return palette.get(role)


def generate_btop_theme(palette: dict[str, str], theme_name: str) -> str:
    """Generate btop theme using semantic philosophy."""
    philosophy_name = THEME_PHILOSOPHIES.get(theme_name, DEFAULT_PHILOSOPHY)
    philosophy = PHILOSOPHIES[philosophy_name]

    # Helper to get color or fallback
    def color(role: str, fallback: str = "base05") -> str:
        c = get_color(palette, role)
        if c:
            return c.upper()
        return palette.get(fallback, "#FFFFFF").upper()

    # Get philosophy colors
    border = color(philosophy.get("border", "base03"))

    # For accent-per-box, each box is different
    if philosophy.get("border") is None:
        cpu_box = color(philosophy.get("cpu_box", "base0C"))
        mem_box = color(philosophy.get("mem_box", "base0B"))
        net_box = color(philosophy.get("net_box", "base0E"))
        proc_box = color(philosophy.get("proc_box", "base08"))
    else:
        cpu_box = mem_box = net_box = proc_box = border

    # Gradients
    grad_low = Color.from_hex(color(philosophy.get("gradient_low", "base0D")))
    grad_mid = Color.from_hex(color(philosophy.get("gradient_mid", "base0C")))
    grad_high = Color.from_hex(color(philosophy.get("gradient_high", "base06")))

    # Generate perceptually uniform gradient
    temp_start = grad_low.to_hex()
    temp_mid = interpolate_oklch(grad_low, grad_high, 0.5).to_hex()
    temp_end = grad_high.to_hex()

    # CPU uses same gradient or traffic light
    if philosophy.get("use_traffic_light_cpu"):
        cpu_start = color("ansi_bright_green", "base0B")
        cpu_mid = color("base0A")
        cpu_end = color("base09", "base08")
    else:
        cpu_start = temp_start
        cpu_mid = temp_mid
        cpu_end = temp_end

    output = f'''# {theme_name.replace("-", " ").title()} - btop theme
# Generated by semantic_generator.py
# Philosophy: {philosophy_name}

# Main background
theme[main_bg]="{color("base00")}"

# Main text color
theme[main_fg]="{color("base05")}"

# Title color for boxes
theme[title]="{color("base05")}"

# Highlight color for keyboard shortcuts
theme[hi_fg]="{color(philosophy.get("highlight", "base0F"))}"

# Background color of selected item
theme[selected_bg]="{color("base02")}"

# Foreground color of selected item
theme[selected_fg]="{color("base06")}"

# Color of inactive/disabled text
theme[inactive_fg]="{color("base03")}"

# Misc colors for processes box
theme[proc_misc]="{color("base0D")}"

# Box outline colors
theme[cpu_box]="{cpu_box}"
theme[mem_box]="{mem_box}"
theme[net_box]="{net_box}"
theme[proc_box]="{proc_box}"
theme[div_line]="{border}"

# Temperature gradient (cool → hot)
theme[temp_start]="{temp_start}"
theme[temp_mid]="{temp_mid}"
theme[temp_end]="{temp_end}"

# CPU graph colors
theme[cpu_start]="{cpu_start}"
theme[cpu_mid]="{cpu_mid}"
theme[cpu_end]="{cpu_end}"

# Memory free meter (green tones)
theme[free_start]="{color("base0B")}"
theme[free_mid]="{color("base0C")}"
theme[free_end]="{color("base06")}"

# Memory cached meter (blue tones)
theme[cached_start]="{color("base0D")}"
theme[cached_mid]="{color("base0C")}"
theme[cached_end]="{color("base06")}"

# Memory available meter
theme[available_start]="{color("base0D")}"
theme[available_mid]="{color("base0C")}"
theme[available_end]="{color("base06")}"

# Memory used meter (warm tones)
theme[used_start]="{color("base08")}"
theme[used_mid]="{color("base09")}"
theme[used_end]="{color("base0A")}"

# Download graph colors (cool)
theme[download_start]="{color("base0D")}"
theme[download_mid]="{color("base0C")}"
theme[download_end]="{color("base06")}"

# Upload graph colors (warm)
theme[upload_start]="{color("base0E")}"
theme[upload_mid]="{color("base0D")}"
theme[upload_end]="{color("base06")}"
'''
    return output


def main():
    themes_dir = Path.home() / "dotfiles/apps/common/theme/library"
    output_dir = Path.home() / "dotfiles/apps/common/theme/analysis/generated"
    output_dir.mkdir(exist_ok=True)

    # Generate for themes we have
    for theme_dir in themes_dir.iterdir():
        if not theme_dir.is_dir():
            continue

        palette_path = theme_dir / "palette.yml"
        if not palette_path.exists():
            continue

        theme_name = theme_dir.name
        palette = load_palette(palette_path)

        if not palette:
            print(f"Skipping {theme_name}: empty palette")
            continue

        btop_theme = generate_btop_theme(palette, theme_name)

        output_path = output_dir / f"{theme_name}.btop.theme"
        output_path.write_text(btop_theme)
        print(f"Generated: {output_path.name}")


if __name__ == "__main__":
    main()
