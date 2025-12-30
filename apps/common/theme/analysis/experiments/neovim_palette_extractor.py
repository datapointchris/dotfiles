#!/usr/bin/env python3
"""
Neovim Palette Extractor (Experiment 1)

Extracts base color palettes from Neovim colorscheme plugins and maps them
to base16 roles for comparison and analysis.

Supported colorschemes:
- kanagawa.nvim
- rose-pine/neovim
- gruvbox.nvim
- nightfox.nvim (terafox, carbonfox, etc.)
- nordic.nvim
- solarized-osaka.nvim
- github-nvim-theme
- oceanic-next
- flexoki-moon-nvim (user's themes)
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ColorPalette:
    """Represents an extracted color palette."""

    name: str
    variant: str = "default"
    colors: dict = field(default_factory=dict)
    base16: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


def extract_hex_colors(content: str) -> dict[str, str]:
    """Extract simple hex color assignments from Lua content."""
    colors = {}

    # Match: name = "#XXXXXX" or name = '#XXXXXX'
    pattern = r'(\w+)\s*=\s*["\']?(#[0-9A-Fa-f]{6})["\']?'
    for match in re.finditer(pattern, content):
        name, color = match.groups()
        colors[name] = color.upper()

    return colors


def extract_shade_objects(content: str) -> dict[str, dict]:
    """Extract Shade.new() calls from nightfox-style themes."""
    shades = {}

    # Match: name = Shade.new("#base", "#bright", "#dim") - 3 hex colors
    pattern = r'(\w+)\s*=\s*Shade\.new\(\s*["\']([#0-9A-Fa-f]+)["\'],\s*["\']([#0-9A-Fa-f]+)["\'],\s*["\']([#0-9A-Fa-f]+)["\']\s*\)'
    for match in re.finditer(pattern, content):
        name, base, bright, dim = match.groups()
        shades[name] = {
            "base": base.upper(),
            "bright": bright.upper(),
            "dim": dim.upper(),
        }

    # Match: name = Shade.new("#base", "#bright", "#dim", true/false) - 4 params (dawnfox/dayfox style)
    pattern1b = r'(\w+)\s*=\s*Shade\.new\(\s*["\']([#0-9A-Fa-f]+)["\'],\s*["\']([#0-9A-Fa-f]+)["\'],\s*["\']([#0-9A-Fa-f]+)["\'],\s*(?:true|false)\s*\)'
    for match in re.finditer(pattern1b, content):
        name, base, bright, dim = match.groups()
        if name not in shades:  # Don't overwrite if already matched
            shades[name] = {
                "base": base.upper(),
                "bright": bright.upper(),
                "dim": dim.upper(),
            }

    # Match: name = Shade.new("#base", 0.15, -0.15) - hex + numeric offsets (carbonfox style)
    pattern2 = r'(\w+)\s*=\s*Shade\.new\(\s*["\']([#0-9A-Fa-f]+)["\']\s*,\s*([0-9.-]+)\s*,\s*([0-9.-]+)\s*\)'
    for match in re.finditer(pattern2, content):
        name, base, bright_offset, dim_offset = match.groups()
        if name not in shades:  # Don't overwrite if already matched
            # For numeric offsets, we just use the base color and estimate bright/dim
            base_color = base.upper()
            shades[name] = {
                "base": base_color,
                "bright": adjust_brightness(base_color, float(bright_offset)),
                "dim": adjust_brightness(base_color, float(dim_offset)),
            }

    # Match: name = Shade.new("#base", 0.15, -0.15, true/false) - hex + numeric offsets + boolean (dayfox style)
    pattern3 = r'(\w+)\s*=\s*Shade\.new\(\s*["\']([#0-9A-Fa-f]+)["\']\s*,\s*([0-9.-]+)\s*,\s*([0-9.-]+)\s*,\s*(?:true|false)\s*\)'
    for match in re.finditer(pattern3, content):
        name, base, bright_offset, dim_offset = match.groups()
        if name not in shades:  # Don't overwrite if already matched
            base_color = base.upper()
            shades[name] = {
                "base": base_color,
                "bright": adjust_brightness(base_color, float(bright_offset)),
                "dim": adjust_brightness(base_color, float(dim_offset)),
            }

    return shades


def adjust_brightness(hex_color: str, offset: float) -> str:
    """Adjust hex color brightness by offset (e.g., 0.15 = 15% brighter)."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    # Simple brightness adjustment
    factor = 1 + offset
    r = min(255, max(0, int(r * factor)))
    g = min(255, max(0, int(g * factor)))
    b = min(255, max(0, int(b * factor)))

    return f"#{r:02X}{g:02X}{b:02X}"


def hsl_to_hex(h: float, s: float, l: float) -> str:
    """Convert HSL to hex color."""
    s = s / 100
    l = l / 100

    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2

    if 0 <= h < 60:
        r, g, b = c, x, 0
    elif 60 <= h < 120:
        r, g, b = x, c, 0
    elif 120 <= h < 180:
        r, g, b = 0, c, x
    elif 180 <= h < 240:
        r, g, b = 0, x, c
    elif 240 <= h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x

    r = int((r + m) * 255)
    g = int((g + m) * 255)
    b = int((b + m) * 255)

    return f"#{r:02X}{g:02X}{b:02X}"


def extract_hsl_colors(content: str) -> dict[str, str]:
    """Extract colors defined with hsl() function calls."""
    colors = {}

    # Match: name = hsl(h, s, l)
    pattern = r'(\w+)\s*=\s*hsl\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\)'
    for match in re.finditer(pattern, content):
        name, h, s, l = match.groups()
        colors[name] = hsl_to_hex(float(h), float(s), float(l))

    return colors


def extract_nested_tables(content: str) -> dict[str, dict]:
    """Extract nested table color definitions like nordic's aurora colors."""
    nested = {}

    # Match: name = { base = "#XXX", bright = "#YYY", dim = "#ZZZ" }
    pattern = r'(\w+)\s*=\s*\{\s*base\s*=\s*["\']([#0-9A-Fa-f]+)["\'],?\s*bright\s*=\s*["\']([#0-9A-Fa-f]+)["\'],?\s*dim\s*=\s*["\']([#0-9A-Fa-f]+)["\']\s*,?\s*\}'
    for match in re.finditer(pattern, content, re.DOTALL):
        name, base, bright, dim = match.groups()
        nested[name] = {
            "base": base.upper(),
            "bright": bright.upper(),
            "dim": dim.upper(),
        }

    return nested


def extract_kanagawa(repo_path: Path) -> list[ColorPalette]:
    """Extract palettes from kanagawa.nvim."""
    palettes = []
    colors_file = repo_path / "lua/kanagawa/colors.lua"
    themes_file = repo_path / "lua/kanagawa/themes.lua"

    if not colors_file.exists():
        return palettes

    content = colors_file.read_text()
    colors = extract_hex_colors(content)

    # Kanagawa has 3 theme variants that use subsets of the palette
    # Wave (default dark), Dragon (darker), Lotus (light)
    variants = {
        "wave": {
            "bg_prefix": "sumiInk",
            "fg_main": "fujiWhite",
            "is_light": False,
        },
        "dragon": {
            "bg_prefix": "dragonBlack",
            "fg_main": "dragonWhite",
            "is_light": False,
        },
        "lotus": {
            "bg_prefix": "lotusWhite",
            "fg_main": "lotusInk1",
            "is_light": True,
        },
    }

    for variant_name, variant_info in variants.items():
        palette = ColorPalette(
            name="kanagawa",
            variant=variant_name,
            colors=colors.copy(),
            metadata={"is_light": variant_info["is_light"]},
        )

        # Map to base16 based on variant
        bg_prefix = variant_info["bg_prefix"]
        is_light = variant_info["is_light"]

        if variant_name == "wave":
            palette.base16 = {
                "base00": colors.get("sumiInk3", ""),  # Background
                "base01": colors.get("sumiInk4", ""),  # Lighter bg
                "base02": colors.get("sumiInk5", ""),  # Selection
                "base03": colors.get("fujiGray", ""),  # Comments
                "base04": colors.get("oldWhite", ""),  # Dark fg
                "base05": colors.get("fujiWhite", ""),  # Default fg
                "base06": colors.get("fujiWhite", ""),  # Light fg
                "base07": colors.get("fujiWhite", ""),  # Lightest fg
                "base08": colors.get("waveRed", ""),  # Red
                "base09": colors.get("surimiOrange", ""),  # Orange
                "base0A": colors.get("carpYellow", ""),  # Yellow
                "base0B": colors.get("springGreen", ""),  # Green
                "base0C": colors.get("waveAqua2", ""),  # Cyan
                "base0D": colors.get("crystalBlue", ""),  # Blue
                "base0E": colors.get("oniViolet", ""),  # Purple
                "base0F": colors.get("sakuraPink", ""),  # Brown/Pink
            }
        elif variant_name == "dragon":
            palette.base16 = {
                "base00": colors.get("dragonBlack3", ""),
                "base01": colors.get("dragonBlack4", ""),
                "base02": colors.get("dragonBlack5", ""),
                "base03": colors.get("dragonGray3", ""),
                "base04": colors.get("dragonGray2", ""),
                "base05": colors.get("dragonWhite", ""),
                "base06": colors.get("dragonWhite", ""),
                "base07": colors.get("dragonWhite", ""),
                "base08": colors.get("dragonRed", ""),
                "base09": colors.get("dragonOrange", ""),
                "base0A": colors.get("dragonYellow", ""),
                "base0B": colors.get("dragonGreen", ""),
                "base0C": colors.get("dragonAqua", ""),
                "base0D": colors.get("dragonBlue2", ""),
                "base0E": colors.get("dragonViolet", ""),
                "base0F": colors.get("dragonPink", ""),
            }
        elif variant_name == "lotus":
            palette.base16 = {
                "base00": colors.get("lotusWhite3", ""),
                "base01": colors.get("lotusWhite2", ""),
                "base02": colors.get("lotusWhite1", ""),
                "base03": colors.get("lotusGray2", ""),
                "base04": colors.get("lotusGray3", ""),
                "base05": colors.get("lotusInk1", ""),
                "base06": colors.get("lotusInk2", ""),
                "base07": colors.get("lotusInk1", ""),
                "base08": colors.get("lotusRed", ""),
                "base09": colors.get("lotusOrange", ""),
                "base0A": colors.get("lotusYellow3", ""),
                "base0B": colors.get("lotusGreen", ""),
                "base0C": colors.get("lotusAqua", ""),
                "base0D": colors.get("lotusBlue4", ""),
                "base0E": colors.get("lotusViolet4", ""),
                "base0F": colors.get("lotusPink", ""),
            }

        palettes.append(palette)

    return palettes


def extract_rose_pine(repo_path: Path) -> list[ColorPalette]:
    """Extract palettes from rose-pine/neovim."""
    palettes = []
    palette_file = repo_path / "lua/rose-pine/palette.lua"

    if not palette_file.exists():
        return palettes

    content = palette_file.read_text()

    # Extract each variant's colors
    variants = ["main", "moon", "dawn"]

    for variant in variants:
        # Find the variant block
        pattern = rf'{variant}\s*=\s*\{{([^}}]+)\}}'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            continue

        variant_content = match.group(1)
        colors = extract_hex_colors(variant_content)

        is_light = variant == "dawn"

        palette = ColorPalette(
            name="rose-pine",
            variant=variant,
            colors=colors,
            metadata={"is_light": is_light},
        )

        # Map to base16
        palette.base16 = {
            "base00": colors.get("base", ""),
            "base01": colors.get("surface", ""),
            "base02": colors.get("overlay", ""),
            "base03": colors.get("muted", ""),
            "base04": colors.get("subtle", ""),
            "base05": colors.get("text", ""),
            "base06": colors.get("text", ""),
            "base07": colors.get("text", ""),
            "base08": colors.get("love", ""),  # Red
            "base09": colors.get("rose", ""),  # Orange/Pink
            "base0A": colors.get("gold", ""),  # Yellow
            "base0B": colors.get("pine", ""),  # Green (actually teal-ish)
            "base0C": colors.get("foam", ""),  # Cyan
            "base0D": colors.get("pine", ""),  # Blue (using pine)
            "base0E": colors.get("iris", ""),  # Purple
            "base0F": colors.get("rose", ""),  # Brown (using rose)
        }

        palettes.append(palette)

    return palettes


def extract_gruvbox(repo_path: Path) -> list[ColorPalette]:
    """Extract palettes from gruvbox.nvim."""
    palettes = []
    gruvbox_file = repo_path / "lua/gruvbox.lua"

    if not gruvbox_file.exists():
        return palettes

    content = gruvbox_file.read_text()
    colors = extract_hex_colors(content)

    # Gruvbox has dark and light variants with hard/soft/default contrast
    for mode in ["dark", "light"]:
        for contrast in ["hard", "", "soft"]:
            contrast_suffix = f"_{contrast}" if contrast else ""
            variant_name = f"{mode}{contrast_suffix}" if contrast else mode

            is_light = mode == "light"

            palette = ColorPalette(
                name="gruvbox",
                variant=variant_name,
                colors=colors,
                metadata={"is_light": is_light, "contrast": contrast or "default"},
            )

            # Select bg0 based on contrast
            if mode == "dark":
                bg0_key = f"dark0{contrast_suffix}" if contrast else "dark0"
                palette.base16 = {
                    "base00": colors.get(bg0_key, colors.get("dark0", "")),
                    "base01": colors.get("dark1", ""),
                    "base02": colors.get("dark2", ""),
                    "base03": colors.get("dark3", ""),
                    "base04": colors.get("gray", ""),
                    "base05": colors.get("light1", ""),
                    "base06": colors.get("light2", ""),
                    "base07": colors.get("light0", ""),
                    "base08": colors.get("bright_red", ""),
                    "base09": colors.get("bright_orange", ""),
                    "base0A": colors.get("bright_yellow", ""),
                    "base0B": colors.get("bright_green", ""),
                    "base0C": colors.get("bright_aqua", ""),
                    "base0D": colors.get("bright_blue", ""),
                    "base0E": colors.get("bright_purple", ""),
                    "base0F": colors.get("neutral_orange", ""),  # Brown-ish
                }
            else:
                bg0_key = f"light0{contrast_suffix}" if contrast else "light0"
                palette.base16 = {
                    "base00": colors.get(bg0_key, colors.get("light0", "")),
                    "base01": colors.get("light1", ""),
                    "base02": colors.get("light2", ""),
                    "base03": colors.get("light3", ""),
                    "base04": colors.get("gray", ""),
                    "base05": colors.get("dark1", ""),
                    "base06": colors.get("dark2", ""),
                    "base07": colors.get("dark0", ""),
                    "base08": colors.get("faded_red", ""),
                    "base09": colors.get("faded_orange", ""),
                    "base0A": colors.get("faded_yellow", ""),
                    "base0B": colors.get("faded_green", ""),
                    "base0C": colors.get("faded_aqua", ""),
                    "base0D": colors.get("faded_blue", ""),
                    "base0E": colors.get("faded_purple", ""),
                    "base0F": colors.get("neutral_orange", ""),
                }

            palettes.append(palette)

    return palettes


def extract_c_colors(content: str) -> dict[str, str]:
    """Extract colors from nightfox C() constructor: local bg = C('#hex')"""
    colors = {}
    pattern = r'local\s+(\w+)\s*=\s*C\(\s*["\']([#0-9A-Fa-f]+)["\']\s*\)'
    for match in re.finditer(pattern, content):
        name, color = match.groups()
        colors[name] = color.upper()
    return colors


def extract_nightfox(repo_path: Path) -> list[ColorPalette]:
    """Extract palettes from nightfox.nvim (terafox, carbonfox, etc.)."""
    palettes = []
    palette_dir = repo_path / "lua/nightfox/palette"

    if not palette_dir.exists():
        return palettes

    # Available variants
    variants = ["terafox", "carbonfox", "nightfox", "nordfox", "dawnfox", "dayfox", "duskfox"]

    for variant in variants:
        variant_file = palette_dir / f"{variant}.lua"
        if not variant_file.exists():
            continue

        content = variant_file.read_text()

        # Check if light theme
        is_light = "light = true" in content

        # Extract simple colors
        colors = extract_hex_colors(content)

        # Extract C() color definitions (for themes that compute bg/fg)
        c_colors = extract_c_colors(content)
        # Map bg/fg to bg1/fg1 if not already defined
        if "bg" in c_colors and "bg1" not in colors:
            colors["bg1"] = c_colors["bg"]
        if "fg" in c_colors and "fg1" not in colors:
            colors["fg1"] = c_colors["fg"]

        # Compute derived fg colors if missing (carbonfox computes fg2/fg3 from fg)
        if "fg" in c_colors:
            fg_base = c_colors["fg"]
            if "fg2" not in colors:
                colors["fg2"] = adjust_brightness(fg_base, -0.24)  # brighten(-24)
            if "fg3" not in colors:
                colors["fg3"] = adjust_brightness(fg_base, -0.48)  # brighten(-48)
            if "fg0" not in colors:
                colors["fg0"] = adjust_brightness(fg_base, 0.06)  # brighten(6)

        # Extract Shade objects
        shades = extract_shade_objects(content)

        palette = ColorPalette(
            name="nightfox",
            variant=variant,
            colors={**colors, **{k: v["base"] for k, v in shades.items()}},
            metadata={
                "is_light": is_light,
                "shades": shades,
            },
        )

        # Map to base16 (following nightfox's own base16.lua template)
        palette.base16 = {
            "base00": colors.get("bg1", colors.get("bg0", colors.get("bg", ""))),
            "base01": colors.get("bg2", colors.get("sel0", "")),
            "base02": colors.get("bg3", colors.get("sel1", "")),
            "base03": shades.get("black", {}).get("bright", colors.get("comment", "")),
            "base04": colors.get("fg3", ""),
            "base05": colors.get("fg1", colors.get("fg", "")),
            "base06": colors.get("fg2", ""),
            "base07": shades.get("white", {}).get("bright", colors.get("fg0", "")),
            "base08": shades.get("red", {}).get("base", ""),
            "base09": shades.get("orange", {}).get("base", ""),
            "base0A": shades.get("yellow", {}).get("base", ""),
            "base0B": shades.get("green", {}).get("base", ""),
            "base0C": shades.get("cyan", {}).get("base", ""),
            "base0D": shades.get("blue", {}).get("base", ""),
            "base0E": shades.get("magenta", {}).get("base", ""),
            "base0F": shades.get("pink", {}).get("base", ""),
        }

        palettes.append(palette)

    return palettes


def extract_nordic(repo_path: Path) -> list[ColorPalette]:
    """Extract palette from nordic.nvim."""
    palettes = []
    palette_file = repo_path / "lua/nordic/colors/nordic.lua"

    if not palette_file.exists():
        return palettes

    content = palette_file.read_text()

    # Extract simple colors
    colors = extract_hex_colors(content)

    # Extract nested table colors (aurora colors)
    nested = extract_nested_tables(content)

    palette = ColorPalette(
        name="nordic",
        variant="default",
        colors={**colors, **{k: v["base"] for k, v in nested.items()}},
        metadata={
            "is_light": False,
            "nested_colors": nested,
        },
    )

    # Map to base16
    palette.base16 = {
        "base00": colors.get("gray0", colors.get("black1", "")),
        "base01": colors.get("gray1", ""),
        "base02": colors.get("gray2", ""),
        "base03": colors.get("gray4", ""),
        "base04": colors.get("gray5", ""),
        "base05": colors.get("white1", colors.get("white0_normal", "")),
        "base06": colors.get("white2", ""),
        "base07": colors.get("white3", ""),
        "base08": nested.get("red", {}).get("base", ""),
        "base09": nested.get("orange", {}).get("base", ""),
        "base0A": nested.get("yellow", {}).get("base", ""),
        "base0B": nested.get("green", {}).get("base", ""),
        "base0C": nested.get("cyan", {}).get("base", colors.get("blue2", "")),
        "base0D": colors.get("blue1", colors.get("blue0", "")),
        "base0E": nested.get("magenta", {}).get("base", ""),
        "base0F": nested.get("orange", {}).get("dim", ""),  # Brown
    }

    palettes.append(palette)
    return palettes


def extract_flexoki_moon(repo_path: Path) -> list[ColorPalette]:
    """Extract palettes from user's flexoki-moon-nvim."""
    palettes = []
    palette_file = repo_path / "lua/flexoki/palette.lua"

    if not palette_file.exists():
        return palettes

    content = palette_file.read_text()

    # Flexoki-moon has multiple variants: black, purple, green, red, toddler
    variants = ["black", "purple", "green", "red", "toddler"]

    for variant in variants:
        # Find the variant block - need to handle nested braces properly
        # Look for the variant = { ... } pattern
        start_pattern = rf'{variant}\s*=\s*\{{'
        match = re.search(start_pattern, content)
        if not match:
            continue

        # Find the matching closing brace
        start_pos = match.end()
        brace_count = 1
        end_pos = start_pos
        while brace_count > 0 and end_pos < len(content):
            if content[end_pos] == '{':
                brace_count += 1
            elif content[end_pos] == '}':
                brace_count -= 1
            end_pos += 1

        variant_content = content[start_pos:end_pos - 1]
        colors = extract_hex_colors(variant_content)

        palette = ColorPalette(
            name="flexoki-moon",
            variant=variant,
            colors=colors,
            metadata={"is_light": False},
        )

        # Map to base16 - flexoki uses _one (dark) and _two (bright) suffixes
        palette.base16 = {
            "base00": colors.get("base", ""),  # Background
            "base01": colors.get("surface", ""),  # Surface/lighter bg
            "base02": colors.get("overlay", colors.get("highlight_low", "")),  # Selection
            "base03": colors.get("muted", ""),  # Comments
            "base04": colors.get("subtle", ""),  # Dark fg
            "base05": colors.get("text", ""),  # Default fg
            "base06": colors.get("text", ""),  # Light fg
            "base07": colors.get("text", ""),  # Lightest fg
            "base08": colors.get("red_two", colors.get("red_one", "")),  # Red
            "base09": colors.get("orange_two", colors.get("orange_one", "")),  # Orange
            "base0A": colors.get("yellow_two", colors.get("yellow_one", "")),  # Yellow
            "base0B": colors.get("green_two", colors.get("green_one", "")),  # Green
            "base0C": colors.get("cyan_two", colors.get("cyan_one", "")),  # Cyan
            "base0D": colors.get("blue_two", colors.get("blue_one", "")),  # Blue
            "base0E": colors.get("purple_two", colors.get("purple_one", "")),  # Purple
            "base0F": colors.get("magenta_two", colors.get("magenta_one", "")),  # Magenta
        }

        palettes.append(palette)

    return palettes


def extract_solarized_osaka(repo_path: Path) -> list[ColorPalette]:
    """Extract palette from solarized-osaka.nvim."""
    palettes = []

    # Try to find the colors file
    colors_file = repo_path / "lua/solarized-osaka/colors.lua"
    if not colors_file.exists():
        # Check alternative locations
        for pattern in ["lua/**/colors.lua", "lua/**/palette.lua"]:
            files = list(repo_path.glob(pattern))
            if files:
                colors_file = files[0]
                break

    if not colors_file.exists():
        return palettes

    content = colors_file.read_text()

    # Solarized-osaka uses hsl() function calls
    colors = extract_hsl_colors(content)
    # Also extract any direct hex colors
    colors.update(extract_hex_colors(content))

    palette = ColorPalette(
        name="solarized-osaka",
        variant="default",
        colors=colors,
        metadata={"is_light": False},  # Osaka is typically dark
    )

    # Map to base16 (solarized-ish mapping)
    palette.base16 = {
        "base00": colors.get("base04", colors.get("bg", "")),  # Darkest bg
        "base01": colors.get("base03", ""),
        "base02": colors.get("base02", ""),
        "base03": colors.get("base01", ""),  # Comments
        "base04": colors.get("base00", ""),
        "base05": colors.get("base0", colors.get("fg", "")),  # Default fg
        "base06": colors.get("base1", ""),
        "base07": colors.get("base2", ""),  # Brightest fg
        "base08": colors.get("red", colors.get("red500", "")),
        "base09": colors.get("orange", colors.get("orange500", "")),
        "base0A": colors.get("yellow", colors.get("yellow500", "")),
        "base0B": colors.get("green", colors.get("green500", "")),
        "base0C": colors.get("cyan", colors.get("cyan500", "")),
        "base0D": colors.get("blue", colors.get("blue500", "")),
        "base0E": colors.get("violet", colors.get("violet500", "")),
        "base0F": colors.get("magenta", colors.get("magenta500", "")),
    }

    palettes.append(palette)
    return palettes


def extract_github_primitives(repo_path: Path, variant: str) -> dict:
    """Extract color primitives from github-theme's JSON-in-Lua files."""
    # Map variant names to primitive files
    if "light" in variant:
        if "high_contrast" in variant:
            prim_file = "light_high_contrast.lua"
        elif "colorblind" in variant:
            prim_file = "light_colorblind.lua"
        elif "tritanopia" in variant:
            prim_file = "light_tritanopia.lua"
        else:
            prim_file = "light.lua"
    else:
        if "high_contrast" in variant:
            prim_file = "dark_high_contrast.lua"
        elif "colorblind" in variant:
            prim_file = "dark_colorblind.lua"
        elif "tritanopia" in variant:
            prim_file = "dark_tritanopia.lua"
        elif "dimmed" in variant:
            prim_file = "dark_dimmed.lua"
        else:
            prim_file = "dark.lua"

    prim_path = repo_path / "lua/github-theme/palette/primitives" / prim_file
    if not prim_path.exists():
        return {}

    content = prim_path.read_text()

    # Extract the JSON blob from the Lua file
    json_match = re.search(r'\[=\[(.*?)\]=\]', content, re.DOTALL)
    if not json_match:
        return {}

    try:
        primitives = json.loads(json_match.group(1))
        return primitives
    except json.JSONDecodeError:
        return {}


def extract_github_theme(repo_path: Path) -> list[ColorPalette]:
    """Extract palettes from github-nvim-theme."""
    palettes = []

    # GitHub theme has multiple variants
    palette_dir = repo_path / "lua/github-theme/palette"
    if not palette_dir.exists():
        return palettes

    for variant_file in palette_dir.glob("*.lua"):
        variant_name = variant_file.stem
        if variant_name in ["init", "primitives"]:
            continue

        content = variant_file.read_text()
        colors = extract_hex_colors(content)

        # Get primitives for this variant
        primitives = extract_github_primitives(repo_path, variant_name)

        is_light = "light" in variant_name.lower()

        # Extract colors from primitives
        if primitives:
            scale = primitives.get("scale", {})
            ansi = primitives.get("ansi", {})
            fg = primitives.get("fg", {})
            canvas = primitives.get("canvas", {})
            prettylights = primitives.get("prettylights", {}).get("syntax", {})

            # Add scale colors (arrays indexed 0-9, we want middle values)
            for color_name in ["gray", "blue", "green", "yellow", "orange", "red", "purple", "pink"]:
                if color_name in scale and isinstance(scale[color_name], list):
                    arr = scale[color_name]
                    if len(arr) >= 5:
                        colors[f"{color_name}_base"] = arr[4] if arr[4].startswith("#") else ""
                        colors[f"{color_name}_bright"] = arr[2] if arr[2].startswith("#") else ""
                        colors[f"{color_name}_dim"] = arr[6] if len(arr) > 6 and arr[6].startswith("#") else ""

            # Add canvas colors
            if isinstance(canvas, dict):
                for key, val in canvas.items():
                    if isinstance(val, str) and val.startswith("#"):
                        colors[f"canvas_{key}"] = val

            # Add fg colors
            if isinstance(fg, dict):
                for key, val in fg.items():
                    if isinstance(val, str) and val.startswith("#"):
                        colors[f"fg_{key}"] = val

            # Add ANSI colors
            if isinstance(ansi, dict):
                for key, val in ansi.items():
                    if isinstance(val, str) and val.startswith("#"):
                        colors[f"ansi_{key}"] = val

            # Add prettylights syntax colors
            if isinstance(prettylights, dict):
                for key, val in prettylights.items():
                    if isinstance(val, str) and val.startswith("#"):
                        colors[f"syntax_{key}"] = val

        palette = ColorPalette(
            name="github",
            variant=variant_name,
            colors=colors,
            metadata={"is_light": is_light},
        )

        # Build base16 mapping from extracted colors
        palette.base16 = {
            "base00": colors.get("canvas_default", colors.get("gray_base", "")),
            "base01": colors.get("canvas_overlay", colors.get("gray_dim", "")),
            "base02": colors.get("canvas_inset", ""),
            "base03": colors.get("fg_subtle", colors.get("syntax_comment", "")),
            "base04": colors.get("fg_muted", ""),
            "base05": colors.get("fg_default", ""),
            "base06": colors.get("fg_default", ""),
            "base07": colors.get("fg_onEmphasis", colors.get("ansi_whiteBright", "")),
            "base08": colors.get("ansi_red", colors.get("red_base", colors.get("syntax_keyword", ""))),
            "base09": colors.get("ansi_yellow", colors.get("orange_base", colors.get("syntax_variable", ""))),
            "base0A": colors.get("yellow_base", colors.get("ansi_yellow", "")),
            "base0B": colors.get("ansi_green", colors.get("green_base", colors.get("syntax_string", ""))),
            "base0C": colors.get("ansi_cyan", colors.get("syntax_constant", "")),
            "base0D": colors.get("ansi_blue", colors.get("blue_base", colors.get("syntax_entity", ""))),
            "base0E": colors.get("ansi_magenta", colors.get("purple_base", "")),
            "base0F": colors.get("pink_base", colors.get("ansi_magentaBright", "")),
        }

        palettes.append(palette)

    return palettes


def extract_viml_colors(content: str) -> dict[str, str]:
    """Extract colors from VimL let statements like: let s:base00 = ['#1b2b34', '235']"""
    colors = {}

    # Match: let s:name = ['#hexcolor', 'cterm']
    pattern = r"let\s+s:(\w+)\s*=\s*\[\s*['\"]([#0-9A-Fa-f]+)['\"]"
    for match in re.finditer(pattern, content):
        name, color = match.groups()
        colors[name] = color.upper()

    return colors


def extract_oceanic_next(repo_path: Path) -> list[ColorPalette]:
    """Extract palette from oceanic-next."""
    palettes = []

    # Find the colors file (VimL format)
    colors_file = repo_path / "colors/OceanicNext.vim"
    if not colors_file.exists():
        return palettes

    content = colors_file.read_text()

    # Parse VimL color definitions
    colors = extract_viml_colors(content)

    palette = ColorPalette(
        name="oceanic-next",
        variant="default",
        colors=colors,
        metadata={"is_light": False},
    )

    # Map to base16 (OceanicNext is already base16-based)
    palette.base16 = {
        "base00": colors.get("base00", ""),
        "base01": colors.get("base01", ""),
        "base02": colors.get("base02", ""),
        "base03": colors.get("base03", ""),
        "base04": colors.get("base04", ""),
        "base05": colors.get("base05", ""),
        "base06": colors.get("base06", ""),
        "base07": colors.get("base07", ""),
        "base08": colors.get("red", colors.get("base08", "")),
        "base09": colors.get("orange", colors.get("base09", "")),
        "base0A": colors.get("yellow", colors.get("base0A", "")),
        "base0B": colors.get("green", colors.get("base0B", "")),
        "base0C": colors.get("cyan", colors.get("base0C", "")),
        "base0D": colors.get("blue", colors.get("base0D", "")),
        "base0E": colors.get("purple", colors.get("base0E", "")),
        "base0F": colors.get("brown", colors.get("base0F", "")),
    }

    palettes.append(palette)
    return palettes


# Theme repository paths
THEME_REPOS = {
    "kanagawa": Path.home() / ".local/share/nvim/lazy/kanagawa.nvim",
    "rose-pine": Path.home() / ".local/share/nvim/lazy/rose-pine",
    "gruvbox": Path.home() / ".local/share/nvim/lazy/gruvbox.nvim",
    "nightfox": Path.home() / ".local/share/nvim/lazy/nightfox.nvim",
    "nordic": Path.home() / ".local/share/nvim/lazy/nordic.nvim",
    "solarized-osaka": Path.home() / ".local/share/nvim/lazy/solarized-osaka.nvim",
    "github-theme": Path.home() / ".local/share/nvim/lazy/github-theme",
    "oceanic-next": Path.home() / ".local/share/nvim/lazy/oceanic-next",
    "flexoki-moon": Path.home() / "code/flexoki-moon-nvim",
}

EXTRACTORS = {
    "kanagawa": extract_kanagawa,
    "rose-pine": extract_rose_pine,
    "gruvbox": extract_gruvbox,
    "nightfox": extract_nightfox,
    "nordic": extract_nordic,
    "solarized-osaka": extract_solarized_osaka,
    "github-theme": extract_github_theme,
    "oceanic-next": extract_oceanic_next,
    "flexoki-moon": extract_flexoki_moon,
}


def extract_all_palettes() -> list[ColorPalette]:
    """Extract palettes from all available colorscheme repos."""
    all_palettes = []

    for theme_name, repo_path in THEME_REPOS.items():
        if not repo_path.exists():
            print(f"  Skipping {theme_name}: repo not found at {repo_path}")
            continue

        extractor = EXTRACTORS.get(theme_name)
        if not extractor:
            print(f"  Skipping {theme_name}: no extractor implemented")
            continue

        try:
            palettes = extractor(repo_path)
            print(f"  {theme_name}: extracted {len(palettes)} variant(s)")
            all_palettes.extend(palettes)
        except Exception as e:
            print(f"  Error extracting {theme_name}: {e}")

    return all_palettes


def palettes_to_dict(palettes: list[ColorPalette]) -> dict:
    """Convert palettes to a dictionary for JSON export."""
    result = {}
    for p in palettes:
        key = f"{p.name}-{p.variant}" if p.variant != "default" else p.name
        result[key] = {
            "name": p.name,
            "variant": p.variant,
            "base16": p.base16,
            "metadata": p.metadata,
            "all_colors": p.colors,
        }
    return result


def generate_yaml_output(palettes: list[ColorPalette]) -> str:
    """Generate base16-style YAML output for all palettes."""
    lines = ["# Neovim Colorscheme Palettes - Base16 Format", "# Generated by neovim_palette_extractor.py", ""]

    for p in palettes:
        key = f"{p.name}-{p.variant}" if p.variant != "default" else p.name
        lines.append(f"{key}:")
        lines.append(f"  scheme: \"{key}\"")
        lines.append(f"  author: \"Extracted from {p.name}\"")
        is_light = p.metadata.get("is_light", False)
        lines.append(f"  is_light: {str(is_light).lower()}")

        for base_key in ["base00", "base01", "base02", "base03", "base04",
                         "base05", "base06", "base07", "base08", "base09",
                         "base0A", "base0B", "base0C", "base0D", "base0E", "base0F"]:
            color = p.base16.get(base_key, "")
            lines.append(f"  {base_key}: \"{color}\"")
        lines.append("")

    return "\n".join(lines)


def main():
    print("Neovim Palette Extractor - Experiment 1")
    print("=" * 50)
    print()

    print("Extracting palettes from colorscheme repos...")
    palettes = extract_all_palettes()
    print()

    print(f"Total palettes extracted: {len(palettes)}")
    print()

    # Save as JSON
    output_dir = Path(__file__).parent / "neovim_data"
    output_dir.mkdir(exist_ok=True)

    palettes_dict = palettes_to_dict(palettes)
    json_path = output_dir / "palettes.json"
    with open(json_path, "w") as f:
        json.dump(palettes_dict, f, indent=2)
    print(f"Saved JSON: {json_path}")

    # Save as YAML
    yaml_content = generate_yaml_output(palettes)
    yaml_path = output_dir / "palettes.yaml"
    with open(yaml_path, "w") as f:
        f.write(yaml_content)
    print(f"Saved YAML: {yaml_path}")

    # Print summary
    print()
    print("Extracted Palettes Summary:")
    print("-" * 40)
    for p in palettes:
        key = f"{p.name}-{p.variant}" if p.variant != "default" else p.name
        is_light = "light" if p.metadata.get("is_light") else "dark"
        num_colors = len(p.colors)
        has_base16 = sum(1 for v in p.base16.values() if v)
        print(f"  {key:30} ({is_light:5}) - {num_colors:3} colors, {has_base16:2}/16 base16")


if __name__ == "__main__":
    main()
