#!/usr/bin/env python3
"""
Enhanced ML Color Predictor with Multiple Models and Feature Engineering

Expands on ml_color_predictor.py with:
- All 14 omarchy themes as training data
- Advanced feature engineering (color relationships, semantic weights)
- Multiple model types (RandomForest, XGBoost, GradientBoosting)
- Theme philosophy classifications
- Comprehensive evaluation

Usage:
    python ml_enhanced_predictor.py extract     # Extract all omarchy themes
    python ml_enhanced_predictor.py train       # Train and compare models
    python ml_enhanced_predictor.py analyze     # Feature importance analysis
"""

import json
import math
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

try:
    from sklearn.ensemble import (
        RandomForestRegressor,
        GradientBoostingRegressor,
        AdaBoostRegressor,
        ExtraTreesRegressor,
    )
    from sklearn.linear_model import Ridge, Lasso, ElasticNet
    from sklearn.svm import SVR
    from sklearn.neighbors import KNeighborsRegressor
    from sklearn.model_selection import cross_val_score, train_test_split, GridSearchCV
    from sklearn.preprocessing import StandardScaler, LabelEncoder, OneHotEncoder
    from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
    from sklearn.pipeline import Pipeline
    from sklearn.multioutput import MultiOutputRegressor
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("Warning: scikit-learn not installed. Run: uv pip install scikit-learn")

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("Note: XGBoost not installed. Run: uv pip install xgboost")

try:
    from sklearn.neural_network import MLPRegressor
    MLP_AVAILABLE = True
except ImportError:
    MLP_AVAILABLE = False


# ============================================================================
# Color conversion utilities
# ============================================================================

def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Parse hex color to RGB."""
    h = hex_str.lstrip("#").lower()
    if len(h) == 3:
        h = "".join([c * 2 for c in h])
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_oklch(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert RGB to OKLCH (Lightness, Chroma, Hue)."""
    r, g, b = r / 255.0, g / 255.0, b / 255.0

    def to_linear(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    lr, lg, lb = to_linear(r), to_linear(g), to_linear(b)

    l = 0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb
    m = 0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb
    s = 0.0883024619 * lr + 0.2817188376 * lb + 0.6299787005 * lb

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


def hex_to_oklch(hex_str: str) -> tuple[float, float, float]:
    """Convert hex to OKLCH."""
    r, g, b = hex_to_rgb(hex_str)
    return rgb_to_oklch(r, g, b)


def rgb_to_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert RGB to HSL."""
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx = max(r, g, b)
    mn = min(r, g, b)
    l = (mx + mn) / 2

    if mx == mn:
        h = s = 0
    else:
        d = mx - mn
        s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
        if mx == r:
            h = (g - b) / d + (6 if g < b else 0)
        elif mx == g:
            h = (b - r) / d + 2
        else:
            h = (r - g) / d + 4
        h /= 6

    return (h * 360, s * 100, l * 100)


def oklch_to_rgb(L: float, C: float, H: float) -> tuple[int, int, int]:
    """Convert OKLCH to RGB."""
    L = L / 100
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

    return (
        max(0, min(255, int(round(from_linear(r) * 255)))),
        max(0, min(255, int(round(from_linear(g) * 255)))),
        max(0, min(255, int(round(from_linear(b_) * 255))))
    )


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB to hex."""
    return f"#{r:02X}{g:02X}{b:02X}"


def rgb_to_lab(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert RGB to CIELAB."""
    # RGB to XYZ
    r, g, b = r / 255.0, g / 255.0, b / 255.0

    def to_linear(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = to_linear(r), to_linear(g), to_linear(b)

    # sRGB to XYZ (D65)
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041

    # XYZ to Lab (D65 reference)
    x /= 0.95047
    y /= 1.00000
    z /= 1.08883

    def f(t):
        return t ** (1/3) if t > 0.008856 else (7.787 * t) + (16/116)

    L = (116 * f(y)) - 16
    a = 500 * (f(x) - f(y))
    b_val = 200 * (f(y) - f(z))

    return (L, a, b_val)


def hex_to_lab(hex_str: str) -> tuple[float, float, float]:
    """Convert hex to CIELAB."""
    r, g, b = hex_to_rgb(hex_str)
    return rgb_to_lab(r, g, b)


def compute_color_temperature(r: int, g: int, b: int) -> float:
    """Estimate color temperature (warm = positive, cool = negative)."""
    # Simple approximation based on red-blue balance
    return (r - b) / 255.0


def compute_perceived_brightness(r: int, g: int, b: int) -> float:
    """Compute perceived brightness using luminance formula."""
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def find_closest_palette_index(hex_color: str, palette: dict[str, str]) -> tuple[str, float]:
    """Find the closest palette color and distance."""
    target_L, target_C, target_H = hex_to_oklch(hex_color)

    closest_key = None
    min_dist = float("inf")

    for key, pal_hex in palette.items():
        try:
            L, C, H = hex_to_oklch(pal_hex)
            dist = math.sqrt(
                (target_L - L)**2 +
                (target_C - C)**2 +
                ((target_H - H) / 10)**2
            )
            if dist < min_dist:
                min_dist = dist
                closest_key = key
        except:
            pass

    return closest_key, min_dist


def _adjust_expected_L_for_light(expected_L: float, category: str, is_light: bool) -> float:
    """Adjust expected lightness for light themes.

    In dark themes: backgrounds are dark (L~0.2), foregrounds are light (L~0.85)
    In light themes: backgrounds are light (L~0.95), foregrounds are dark (L~0.3)
    """
    if not is_light:
        return expected_L

    # For light themes, invert lightness for bg/fg categories
    if category == "background":
        # Dark bg (0.2) → Light bg (0.95)
        return 1.0 - expected_L + 0.15  # Shift up for light backgrounds
    elif category == "foreground":
        # Light fg (0.85) → Dark fg (0.3)
        return 1.0 - expected_L - 0.15  # Shift down for dark text
    else:
        # Accents, borders, etc. stay similar
        return expected_L


# ============================================================================
# Theme philosophy classifications (subjective)
# ============================================================================

THEME_PHILOSOPHIES = {
    # Monochromatic: Same hue family, intensity/saturation gradients
    "nord": {
        "philosophy": "monochromatic",
        "warmth": 0.2,  # Cool
        "contrast": 0.5,  # Medium contrast
        "saturation_preference": 0.3,  # Low saturation
        "accent_style": "subtle",  # Subtle accents
    },
    # Traffic light: Semantic colors (green=good, yellow=warn, red=bad)
    "gruvbox": {
        "philosophy": "traffic_light",
        "warmth": 0.8,  # Warm
        "contrast": 0.7,  # High contrast
        "saturation_preference": 0.6,  # Medium-high saturation
        "accent_style": "bold",
    },
    "kanagawa": {
        "philosophy": "traffic_light",
        "warmth": 0.6,  # Warm-neutral
        "contrast": 0.6,
        "saturation_preference": 0.5,
        "accent_style": "artistic",
    },
    "everforest": {
        "philosophy": "nature",
        "warmth": 0.5,  # Neutral
        "contrast": 0.5,
        "saturation_preference": 0.4,
        "accent_style": "organic",
    },
    "rose-pine": {
        # NOTE: Omarchy's rose-pine is actually Dawn (light variant)!
        "philosophy": "light_romantic",
        "warmth": 0.5,  # Warm-neutral (light theme)
        "contrast": 0.4,  # Lower contrast (light theme)
        "saturation_preference": 0.4,  # Muted (light theme)
        "accent_style": "romantic",
        "is_light": True,  # Flag for light theme
    },
    "catppuccin": {
        "philosophy": "pastel",
        "warmth": 0.5,
        "contrast": 0.4,
        "saturation_preference": 0.6,
        "accent_style": "soft",
    },
    "catppuccin-latte": {
        "philosophy": "pastel_light",
        "warmth": 0.6,
        "contrast": 0.4,
        "saturation_preference": 0.5,
        "accent_style": "soft",
        "is_light": True,  # Flag for light theme
    },
    "tokyo-night": {
        "philosophy": "neon",
        "warmth": 0.3,
        "contrast": 0.7,
        "saturation_preference": 0.7,
        "accent_style": "vibrant",
    },
    "hackerman": {
        "philosophy": "neon",
        "warmth": 0.2,
        "contrast": 0.9,
        "saturation_preference": 0.8,
        "accent_style": "cyber",
    },
    "matte-black": {
        "philosophy": "minimal",
        "warmth": 0.3,
        "contrast": 0.8,
        "saturation_preference": 0.2,
        "accent_style": "stark",
    },
    "ethereal": {
        "philosophy": "ethereal",
        "warmth": 0.4,
        "contrast": 0.3,
        "saturation_preference": 0.4,
        "accent_style": "dreamy",
    },
    "osaka-jade": {
        "philosophy": "monochromatic",
        "warmth": 0.4,
        "contrast": 0.5,
        "saturation_preference": 0.5,
        "accent_style": "jade",
    },
    "ristretto": {
        "philosophy": "coffee",
        "warmth": 0.9,
        "contrast": 0.6,
        "saturation_preference": 0.4,
        "accent_style": "earthy",
    },
    "flexoki-light": {
        "philosophy": "paper_light",
        "warmth": 0.7,
        "contrast": 0.4,
        "saturation_preference": 0.3,
        "accent_style": "minimal",
        "is_light": True,  # Flag for light theme
    },
}

# Default for unknown themes
DEFAULT_PHILOSOPHY = {
    "philosophy": "balanced",
    "warmth": 0.5,
    "contrast": 0.5,
    "saturation_preference": 0.5,
    "accent_style": "standard",
}

# Philosophy encodings (for ML features)
PHILOSOPHY_CODES = {
    "monochromatic": 0,
    "traffic_light": 1,
    "accent_per_box": 2,
    "pastel": 3,
    "neon": 4,
    "minimal": 5,
    "nature": 6,
    "ethereal": 7,
    "coffee": 8,
    "paper": 9,
    "balanced": 10,
}

ACCENT_STYLE_CODES = {
    "subtle": 0,
    "bold": 1,
    "artistic": 2,
    "organic": 3,
    "romantic": 4,
    "soft": 5,
    "vibrant": 6,
    "cyber": 7,
    "stark": 8,
    "dreamy": 9,
    "jade": 10,
    "earthy": 11,
    "minimal": 12,
    "standard": 13,
}


# ============================================================================
# Property categorization with semantic weights
# ============================================================================

PROPERTY_SEMANTICS = {
    # Background properties - should be low lightness, low chroma
    "main_bg": {"category": "background", "role": "primary", "expected_L": 0.2, "expected_C": 0.1},
    "selected_bg": {"category": "background", "role": "selection", "expected_L": 0.25, "expected_C": 0.15},

    # Foreground properties - should be high lightness
    "main_fg": {"category": "foreground", "role": "primary", "expected_L": 0.85, "expected_C": 0.1},
    "selected_fg": {"category": "foreground", "role": "selection", "expected_L": 0.9, "expected_C": 0.2},
    "title": {"category": "foreground", "role": "title", "expected_L": 0.8, "expected_C": 0.3},
    "inactive_fg": {"category": "foreground", "role": "inactive", "expected_L": 0.5, "expected_C": 0.05},

    # UI chrome - medium lightness, variable chroma
    "cpu_box": {"category": "border", "role": "cpu", "expected_L": 0.4, "expected_C": 0.3},
    "mem_box": {"category": "border", "role": "mem", "expected_L": 0.4, "expected_C": 0.3},
    "net_box": {"category": "border", "role": "net", "expected_L": 0.4, "expected_C": 0.3},
    "proc_box": {"category": "border", "role": "proc", "expected_L": 0.4, "expected_C": 0.3},
    "div_line": {"category": "border", "role": "divider", "expected_L": 0.3, "expected_C": 0.1},
    "hi_fg": {"category": "accent", "role": "highlight", "expected_L": 0.7, "expected_C": 0.5},
    "proc_misc": {"category": "accent", "role": "misc", "expected_L": 0.6, "expected_C": 0.4},

    # Gradients - semantic color progressions
    "temp_start": {"category": "gradient", "role": "temp_low", "expected_L": 0.6, "expected_C": 0.4, "semantic": "cool"},
    "temp_mid": {"category": "gradient", "role": "temp_mid", "expected_L": 0.7, "expected_C": 0.5, "semantic": "warm"},
    "temp_end": {"category": "gradient", "role": "temp_high", "expected_L": 0.6, "expected_C": 0.6, "semantic": "hot"},

    "cpu_start": {"category": "gradient", "role": "cpu_low", "expected_L": 0.6, "expected_C": 0.4, "semantic": "ok"},
    "cpu_mid": {"category": "gradient", "role": "cpu_mid", "expected_L": 0.7, "expected_C": 0.5, "semantic": "busy"},
    "cpu_end": {"category": "gradient", "role": "cpu_high", "expected_L": 0.6, "expected_C": 0.6, "semantic": "critical"},

    "free_start": {"category": "gradient", "role": "free_low", "expected_L": 0.6, "expected_C": 0.4},
    "free_mid": {"category": "gradient", "role": "free_mid", "expected_L": 0.65, "expected_C": 0.45},
    "free_end": {"category": "gradient", "role": "free_high", "expected_L": 0.7, "expected_C": 0.5},

    "used_start": {"category": "gradient", "role": "used_low", "expected_L": 0.6, "expected_C": 0.4},
    "used_mid": {"category": "gradient", "role": "used_mid", "expected_L": 0.65, "expected_C": 0.5},
    "used_end": {"category": "gradient", "role": "used_high", "expected_L": 0.6, "expected_C": 0.6},

    "download_start": {"category": "gradient", "role": "dl_low", "expected_L": 0.6, "expected_C": 0.4},
    "download_mid": {"category": "gradient", "role": "dl_mid", "expected_L": 0.65, "expected_C": 0.45},
    "download_end": {"category": "gradient", "role": "dl_high", "expected_L": 0.7, "expected_C": 0.5},

    "upload_start": {"category": "gradient", "role": "ul_low", "expected_L": 0.6, "expected_C": 0.4},
    "upload_mid": {"category": "gradient", "role": "ul_mid", "expected_L": 0.65, "expected_C": 0.45},
    "upload_end": {"category": "gradient", "role": "ul_high", "expected_L": 0.7, "expected_C": 0.5},

    # Walker/Mako properties
    "background": {"category": "background", "role": "primary", "expected_L": 0.2, "expected_C": 0.1},
    "foreground": {"category": "foreground", "role": "primary", "expected_L": 0.85, "expected_C": 0.1},
    "base": {"category": "background", "role": "primary", "expected_L": 0.2, "expected_C": 0.1},
    "text": {"category": "foreground", "role": "primary", "expected_L": 0.85, "expected_C": 0.1},
    "border": {"category": "border", "role": "main", "expected_L": 0.5, "expected_C": 0.2},
    "selected-text": {"category": "accent", "role": "selection", "expected_L": 0.7, "expected_C": 0.4},
    "selected_text": {"category": "accent", "role": "selection", "expected_L": 0.7, "expected_C": 0.4},

    # Hyprlock
    "color": {"category": "background", "role": "primary", "expected_L": 0.2, "expected_C": 0.1},
    "inner_color": {"category": "background", "role": "input", "expected_L": 0.2, "expected_C": 0.1},
    "outer_color": {"category": "border", "role": "input", "expected_L": 0.5, "expected_C": 0.2},
    "font_color": {"category": "foreground", "role": "primary", "expected_L": 0.85, "expected_C": 0.1},
    "check_color": {"category": "accent", "role": "verify", "expected_L": 0.6, "expected_C": 0.4},

    # SwayOSD
    "background-color": {"category": "background", "role": "primary", "expected_L": 0.2, "expected_C": 0.1},
    "border-color": {"category": "border", "role": "main", "expected_L": 0.5, "expected_C": 0.2},
    "label": {"category": "foreground", "role": "label", "expected_L": 0.85, "expected_C": 0.1},
    "image": {"category": "foreground", "role": "icon", "expected_L": 0.85, "expected_C": 0.1},
    "progress": {"category": "accent", "role": "progress", "expected_L": 0.6, "expected_C": 0.4},

    # Alacritty terminal colors
    "alacritty_background": {"category": "background", "role": "primary", "expected_L": 0.2, "expected_C": 0.1},
    "alacritty_foreground": {"category": "foreground", "role": "primary", "expected_L": 0.85, "expected_C": 0.1},
    "alacritty_dim_foreground": {"category": "foreground", "role": "dim", "expected_L": 0.6, "expected_C": 0.1},
    "alacritty_text": {"category": "foreground", "role": "cursor_text", "expected_L": 0.2, "expected_C": 0.1},
    "alacritty_cursor": {"category": "accent", "role": "cursor", "expected_L": 0.85, "expected_C": 0.2},

    # Alacritty ANSI colors (normal)
    "alacritty_black": {"category": "ansi", "role": "black", "expected_L": 0.25, "expected_C": 0.05},
    "alacritty_red": {"category": "ansi", "role": "red", "expected_L": 0.55, "expected_C": 0.4, "semantic": "error"},
    "alacritty_green": {"category": "ansi", "role": "green", "expected_L": 0.6, "expected_C": 0.35, "semantic": "success"},
    "alacritty_yellow": {"category": "ansi", "role": "yellow", "expected_L": 0.75, "expected_C": 0.4, "semantic": "warning"},
    "alacritty_blue": {"category": "ansi", "role": "blue", "expected_L": 0.6, "expected_C": 0.35},
    "alacritty_magenta": {"category": "ansi", "role": "magenta", "expected_L": 0.55, "expected_C": 0.35},
    "alacritty_cyan": {"category": "ansi", "role": "cyan", "expected_L": 0.65, "expected_C": 0.3},
    "alacritty_white": {"category": "ansi", "role": "white", "expected_L": 0.9, "expected_C": 0.05},

    # Hyprland window manager
    "activeBorderColor": {"category": "border", "role": "active", "expected_L": 0.7, "expected_C": 0.3},

    # Waybar
    "waybar_foreground": {"category": "foreground", "role": "primary", "expected_L": 0.85, "expected_C": 0.1},
    "waybar_background": {"category": "background", "role": "primary", "expected_L": 0.2, "expected_C": 0.1},
    "waybar_border": {"category": "border", "role": "main", "expected_L": 0.5, "expected_C": 0.2},
    "waybar_accent": {"category": "accent", "role": "accent", "expected_L": 0.6, "expected_C": 0.4},

    # Btop additional properties
    "cached_start": {"category": "gradient", "role": "cached_low", "expected_L": 0.6, "expected_C": 0.4},
    "cached_mid": {"category": "gradient", "role": "cached_mid", "expected_L": 0.65, "expected_C": 0.45},
    "cached_end": {"category": "gradient", "role": "cached_high", "expected_L": 0.7, "expected_C": 0.5},
    "available_start": {"category": "gradient", "role": "avail_low", "expected_L": 0.6, "expected_C": 0.4},
    "available_mid": {"category": "gradient", "role": "avail_mid", "expected_L": 0.65, "expected_C": 0.45},
    "available_end": {"category": "gradient", "role": "avail_high", "expected_L": 0.7, "expected_C": 0.5},
    "process_start": {"category": "gradient", "role": "proc_low", "expected_L": 0.6, "expected_C": 0.4},
    "process_mid": {"category": "gradient", "role": "proc_mid", "expected_L": 0.65, "expected_C": 0.45},
    "process_end": {"category": "gradient", "role": "proc_high", "expected_L": 0.7, "expected_C": 0.5},
    "graph_text": {"category": "foreground", "role": "graph", "expected_L": 0.7, "expected_C": 0.2},
    "meter_bg": {"category": "background", "role": "meter", "expected_L": 0.25, "expected_C": 0.1},

    # Mako text-color (different from text)
    "text-color": {"category": "foreground", "role": "primary", "expected_L": 0.85, "expected_C": 0.1},

    # Kitty terminal colors (colorN = base16 index)
    "color0": {"category": "ansi", "role": "color0", "expected_L": 0.2, "expected_C": 0.05},
    "color1": {"category": "ansi", "role": "color1", "expected_L": 0.55, "expected_C": 0.4, "semantic": "error"},
    "color2": {"category": "ansi", "role": "color2", "expected_L": 0.6, "expected_C": 0.35, "semantic": "success"},
    "color3": {"category": "ansi", "role": "color3", "expected_L": 0.75, "expected_C": 0.4, "semantic": "warning"},
    "color4": {"category": "ansi", "role": "color4", "expected_L": 0.6, "expected_C": 0.35},
    "color5": {"category": "ansi", "role": "color5", "expected_L": 0.55, "expected_C": 0.35},
    "color6": {"category": "ansi", "role": "color6", "expected_L": 0.65, "expected_C": 0.3},
    "color7": {"category": "ansi", "role": "color7", "expected_L": 0.9, "expected_C": 0.05},
    "color8": {"category": "ansi", "role": "color8", "expected_L": 0.35, "expected_C": 0.08},
    "color9": {"category": "ansi", "role": "color9", "expected_L": 0.6, "expected_C": 0.45, "semantic": "error"},
    "color10": {"category": "ansi", "role": "color10", "expected_L": 0.65, "expected_C": 0.4, "semantic": "success"},
    "color11": {"category": "ansi", "role": "color11", "expected_L": 0.8, "expected_C": 0.45, "semantic": "warning"},
    "color12": {"category": "ansi", "role": "color12", "expected_L": 0.65, "expected_C": 0.4},
    "color13": {"category": "ansi", "role": "color13", "expected_L": 0.6, "expected_C": 0.4},
    "color14": {"category": "ansi", "role": "color14", "expected_L": 0.7, "expected_C": 0.35},
    "color15": {"category": "ansi", "role": "color15", "expected_L": 0.95, "expected_C": 0.03},
    "color16": {"category": "ansi", "role": "color16", "expected_L": 0.65, "expected_C": 0.45},
    "color17": {"category": "ansi", "role": "color17", "expected_L": 0.55, "expected_C": 0.35},

    # Kitty selection and cursor
    "selection_foreground": {"category": "foreground", "role": "selection", "expected_L": 0.2, "expected_C": 0.1},
    "selection_background": {"category": "background", "role": "selection", "expected_L": 0.4, "expected_C": 0.15},
    "cursor": {"category": "accent", "role": "cursor", "expected_L": 0.85, "expected_C": 0.2},
    "cursor_text_color": {"category": "foreground", "role": "cursor_text", "expected_L": 0.2, "expected_C": 0.1},

    # Kitty tabs
    "active_tab_foreground": {"category": "foreground", "role": "tab_active", "expected_L": 0.9, "expected_C": 0.1},
    "active_tab_background": {"category": "background", "role": "tab_active", "expected_L": 0.3, "expected_C": 0.15},
    "inactive_tab_foreground": {"category": "foreground", "role": "tab_inactive", "expected_L": 0.6, "expected_C": 0.05},
    "inactive_tab_background": {"category": "background", "role": "tab_inactive", "expected_L": 0.2, "expected_C": 0.1},
    "tab_bar_background": {"category": "background", "role": "tab_bar", "expected_L": 0.18, "expected_C": 0.08},

    # Kitty borders
    "active_border_color": {"category": "border", "role": "active", "expected_L": 0.6, "expected_C": 0.35},
    "inactive_border_color": {"category": "border", "role": "inactive", "expected_L": 0.3, "expected_C": 0.1},
    "bell_border_color": {"category": "accent", "role": "bell", "expected_L": 0.7, "expected_C": 0.5},

    # Kitty URL and marks
    "url_color": {"category": "accent", "role": "link", "expected_L": 0.6, "expected_C": 0.4},
    "mark1_foreground": {"category": "foreground", "role": "mark1", "expected_L": 0.2, "expected_C": 0.1},
    "mark1_background": {"category": "accent", "role": "mark1", "expected_L": 0.65, "expected_C": 0.4},
    "mark2_foreground": {"category": "foreground", "role": "mark2", "expected_L": 0.2, "expected_C": 0.1},
    "mark2_background": {"category": "accent", "role": "mark2", "expected_L": 0.6, "expected_C": 0.45},
    "mark3_foreground": {"category": "foreground", "role": "mark3", "expected_L": 0.2, "expected_C": 0.1},
    "mark3_background": {"category": "accent", "role": "mark3", "expected_L": 0.55, "expected_C": 0.4},

    # Alacritty additional
    "alacritty_bright_foreground": {"category": "foreground", "role": "bright", "expected_L": 0.95, "expected_C": 0.05},
    "alacritty_color": {"category": "ansi", "role": "generic", "expected_L": 0.6, "expected_C": 0.3},
}


# ============================================================================
# Data extraction from omarchy themes
# ============================================================================

def extract_btop_colors(filepath: Path) -> dict[str, str]:
    """Extract colors from btop theme file."""
    colors = {}
    content = filepath.read_text()
    for match in re.finditer(r'theme\[(\w+)\]="(#[0-9a-fA-F]{6})"', content):
        colors[match.group(1)] = match.group(2)
    return colors


def extract_kitty_colors(filepath: Path) -> dict[str, str]:
    """Extract colors from kitty config."""
    colors = {}
    for line in filepath.read_text().split("\n"):
        match = re.match(r'^(\w+)\s+(#[0-9a-fA-F]{6})', line.strip())
        if match:
            colors[match.group(1)] = match.group(2)
    return colors


def extract_walker_colors(filepath: Path) -> dict[str, str]:
    """Extract colors from walker CSS."""
    colors = {}
    for match in re.finditer(r'@define-color\s+(\S+)\s+(#[0-9a-fA-F]{6})', filepath.read_text()):
        colors[match.group(1)] = match.group(2)
    return colors


def extract_mako_colors(filepath: Path) -> dict[str, str]:
    """Extract colors from mako INI."""
    colors = {}
    for line in filepath.read_text().split("\n"):
        if "=" in line and "#" in line:
            parts = line.split("=", 1)
            key = parts[0].strip()
            hex_match = re.search(r'(#[0-9a-fA-F]{6})', parts[1])
            if hex_match:
                colors[key] = hex_match.group(1)
    return colors


def extract_swayosd_colors(filepath: Path) -> dict[str, str]:
    """Extract colors from swayosd CSS."""
    return extract_walker_colors(filepath)


def extract_hyprlock_colors(filepath: Path) -> dict[str, str]:
    """Extract colors from hyprlock conf (rgba format)."""
    colors = {}
    content = filepath.read_text()
    for match in re.finditer(r'\$(\w+)\s*=\s*rgba\((\d+),(\d+),(\d+)', content):
        name = match.group(1)
        r, g, b = int(match.group(2)), int(match.group(3)), int(match.group(4))
        colors[name] = f"#{r:02x}{g:02x}{b:02x}"
    return colors


def extract_alacritty_colors(filepath: Path) -> dict[str, str]:
    """Extract colors from alacritty TOML config."""
    colors = {}
    content = filepath.read_text()

    # Match patterns like: background = "#2e3440"
    for match in re.finditer(r'(\w+)\s*=\s*"(#[0-9a-fA-F]{6})"', content):
        key = match.group(1)
        colors[f"alacritty_{key}"] = match.group(2)

    return colors


def extract_hyprland_colors(filepath: Path) -> dict[str, str]:
    """Extract colors from hyprland.conf (rgb format)."""
    colors = {}
    content = filepath.read_text()

    # Match patterns like: $activeBorderColor = rgb(D8DEE9)
    for match in re.finditer(r'\$(\w+)\s*=\s*rgb\(([0-9a-fA-F]{6})\)', content):
        name = match.group(1)
        hex_val = match.group(2)
        colors[name] = f"#{hex_val}"

    return colors


def extract_waybar_colors(filepath: Path) -> dict[str, str]:
    """Extract colors from waybar CSS."""
    colors = {}
    content = filepath.read_text()

    # Match @define-color patterns
    for match in re.finditer(r'@define-color\s+(\S+)\s+(#[0-9a-fA-F]{6})', content):
        colors[f"waybar_{match.group(1)}"] = match.group(2)

    return colors


def load_our_palette(palette_path: Path) -> dict[str, str]:
    """Load colors from our palette.yml."""
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
                    prefix = f"{current_section}_" if current_section != "palette" else ""
                    colors[f"{prefix}{key}"] = hex_match.group(1)

    return colors


def compute_palette_statistics(palette: dict[str, str]) -> dict[str, float]:
    """Compute statistical features from a palette."""
    stats = {}

    # Convert all colors to OKLCH
    oklch_values = []
    for key, hex_color in palette.items():
        try:
            L, C, H = hex_to_oklch(hex_color)
            oklch_values.append((key, L, C, H))
        except:
            pass

    if not oklch_values:
        return stats

    # Overall statistics
    L_vals = [v[1] for v in oklch_values]
    C_vals = [v[2] for v in oklch_values]
    H_vals = [v[3] for v in oklch_values]

    stats["palette_L_mean"] = np.mean(L_vals)
    stats["palette_L_std"] = np.std(L_vals)
    stats["palette_L_min"] = np.min(L_vals)
    stats["palette_L_max"] = np.max(L_vals)
    stats["palette_L_range"] = np.max(L_vals) - np.min(L_vals)

    stats["palette_C_mean"] = np.mean(C_vals)
    stats["palette_C_std"] = np.std(C_vals)
    stats["palette_C_max"] = np.max(C_vals)

    # Hue diversity (circular standard deviation)
    H_rad = np.radians(H_vals)
    sin_sum = np.sum(np.sin(H_rad))
    cos_sum = np.sum(np.cos(H_rad))
    R = np.sqrt(sin_sum**2 + cos_sum**2) / len(H_vals)
    stats["palette_H_concentration"] = R  # 1 = all same hue, 0 = spread

    # Contrast ratio (max L / min L approximation)
    if np.min(L_vals) > 0:
        stats["palette_contrast"] = np.max(L_vals) / np.min(L_vals)
    else:
        stats["palette_contrast"] = 10.0

    return stats


def compute_color_relationships(palette: dict[str, str], target_hex: str) -> dict[str, float]:
    """Compute relationships between target color and palette."""
    features = {}

    try:
        target_L, target_C, target_H = hex_to_oklch(target_hex)
    except:
        return features

    # Find closest palette colors
    min_L_dist = float("inf")
    min_C_dist = float("inf")
    min_H_dist = float("inf")
    min_overall_dist = float("inf")

    for key, hex_color in palette.items():
        try:
            L, C, H = hex_to_oklch(hex_color)

            L_dist = abs(target_L - L)
            C_dist = abs(target_C - C)
            H_dist = min(abs(target_H - H), 360 - abs(target_H - H))

            overall_dist = math.sqrt(L_dist**2 + C_dist**2 + (H_dist/10)**2)

            if L_dist < min_L_dist:
                min_L_dist = L_dist
            if C_dist < min_C_dist:
                min_C_dist = C_dist
            if H_dist < min_H_dist:
                min_H_dist = H_dist
            if overall_dist < min_overall_dist:
                min_overall_dist = overall_dist
        except:
            pass

    features["closest_L_dist"] = min_L_dist
    features["closest_C_dist"] = min_C_dist
    features["closest_H_dist"] = min_H_dist
    features["closest_overall_dist"] = min_overall_dist

    return features


# ============================================================================
# Training data extraction
# ============================================================================

def extract_all_training_data():
    """Extract training data from ALL omarchy themes."""
    omarchy_dir = Path.home() / "code/hypr/omarchy/themes"
    our_themes_dir = Path.home() / "dotfiles/apps/common/theme/library"

    # Map all omarchy themes to our palette names where possible
    theme_mapping = {
        "nord": "nord",
        "kanagawa": "kanagawa",
        "gruvbox": "gruvbox-dark-hard",
        "rose-pine": "rose-pine",
        "everforest": "everforest-dark-hard",
        # Themes without direct mapping will use closest match or be skipped
        "catppuccin": None,
        "catppuccin-latte": None,
        "tokyo-night": None,
        "hackerman": None,
        "matte-black": None,
        "ethereal": None,
        "osaka-jade": None,
        "ristretto": None,
        "flexoki-light": None,
    }

    training_data = []
    themes_processed = []

    for omarchy_theme in sorted(omarchy_dir.iterdir()):
        if not omarchy_theme.is_dir():
            continue

        theme_name = omarchy_theme.name
        our_name = theme_mapping.get(theme_name)

        # Try to load our palette if mapping exists
        palette = {}
        if our_name:
            our_palette_path = our_themes_dir / our_name / "palette.yml"
            if our_palette_path.exists():
                palette = load_our_palette(our_palette_path)

        # Even without our palette, we can extract omarchy's color choices
        # and use them as training data with the theme's own colors as features

        theme_philosophy = THEME_PHILOSOPHIES.get(theme_name, DEFAULT_PHILOSOPHY)

        # Compute palette statistics if we have a palette
        palette_stats = compute_palette_statistics(palette) if palette else {}

        # Extract from all available config files
        extractors = [
            ("btop", "btop.theme", extract_btop_colors),
            ("walker", "walker.css", extract_walker_colors),
            ("mako", "mako.ini", extract_mako_colors),
            ("swayosd", "swayosd.css", extract_swayosd_colors),
            ("hyprlock", "hyprlock.conf", extract_hyprlock_colors),
            ("kitty", "kitty.conf", extract_kitty_colors),
            ("alacritty", "alacritty.toml", extract_alacritty_colors),
            ("hyprland", "hyprland.conf", extract_hyprland_colors),
            ("waybar", "waybar.css", extract_waybar_colors),
        ]

        theme_samples = 0

        for app_name, filename, extractor in extractors:
            filepath = omarchy_theme / filename
            if not filepath.exists():
                continue

            try:
                colors = extractor(filepath)
            except Exception as e:
                print(f"  Warning: Failed to extract {filename} from {theme_name}: {e}")
                continue

            for prop, hex_color in colors.items():
                try:
                    target_L, target_C, target_H = hex_to_oklch(hex_color)

                    # Get property semantics
                    semantics = PROPERTY_SEMANTICS.get(prop, {
                        "category": "unknown",
                        "role": prop,
                        "expected_L": 0.5,
                        "expected_C": 0.3,
                    })

                    # Compute color relationships
                    color_rels = compute_color_relationships(palette, hex_color) if palette else {}

                    # Convert palette to OKLCH features
                    palette_features = {}
                    for key, hex_val in palette.items():
                        try:
                            L, C, H = hex_to_oklch(hex_val)
                            palette_features[f"{key}_L"] = L
                            palette_features[f"{key}_C"] = C
                            palette_features[f"{key}_H"] = H
                        except:
                            pass

                    # Compute additional target representations
                    target_rgb = hex_to_rgb(hex_color)
                    target_lab = rgb_to_lab(*target_rgb)
                    target_hsl = rgb_to_hsl(*target_rgb)
                    target_temp = compute_color_temperature(*target_rgb)
                    target_brightness = compute_perceived_brightness(*target_rgb)

                    # Find closest palette color
                    closest_pal_key = None
                    closest_pal_dist = 0
                    if palette:
                        closest_pal_key, closest_pal_dist = find_closest_palette_index(hex_color, palette)

                    sample = {
                        # Metadata
                        "theme": theme_name,
                        "app": app_name,
                        "property": prop,

                        # Semantic features
                        "category": semantics["category"],
                        "role": semantics["role"],
                        # Adjust expected_L for light themes (invert bg/fg lightness)
                        "expected_L": _adjust_expected_L_for_light(
                            semantics.get("expected_L", 0.5),
                            semantics["category"],
                            theme_philosophy.get("is_light", False)
                        ),
                        "expected_C": semantics.get("expected_C", 0.3),

                        # Philosophy features
                        "philosophy": theme_philosophy["philosophy"],
                        "warmth": theme_philosophy["warmth"],
                        "contrast": theme_philosophy["contrast"],
                        "saturation_pref": theme_philosophy["saturation_preference"],
                        "accent_style": theme_philosophy["accent_style"],

                        # Target OKLCH (what omarchy chose)
                        "target_hex": hex_color,
                        "target_L": target_L,
                        "target_C": target_C,
                        "target_H": target_H,

                        # Target RGB
                        "target_R": target_rgb[0],
                        "target_G": target_rgb[1],
                        "target_B": target_rgb[2],

                        # Target LAB
                        "target_Lab_L": target_lab[0],
                        "target_Lab_a": target_lab[1],
                        "target_Lab_b": target_lab[2],

                        # Target HSL
                        "target_HSL_H": target_hsl[0],
                        "target_HSL_S": target_hsl[1],
                        "target_HSL_Lightness": target_hsl[2],

                        # Derived targets
                        "target_temperature": target_temp,
                        "target_brightness": target_brightness,

                        # Closest palette info
                        "closest_palette_key": closest_pal_key,
                        "closest_palette_dist": closest_pal_dist,

                        # Palette colors (will be empty for unmapped themes)
                        **palette_features,

                        # Palette statistics
                        **palette_stats,

                        # Color relationships
                        **color_rels,
                    }
                    training_data.append(sample)
                    theme_samples += 1

                except Exception as e:
                    print(f"  Warning: Failed to process {prop}={hex_color}: {e}")

        if theme_samples > 0:
            themes_processed.append(theme_name)
            print(f"Extracted {theme_name}: {theme_samples} samples")

    # Save training data
    output_path = Path(__file__).parent / "training_data_enhanced.json"
    with open(output_path, "w") as f:
        json.dump(training_data, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Total samples: {len(training_data)}")
    print(f"Themes processed: {len(themes_processed)}")
    print(f"Themes: {', '.join(themes_processed)}")
    print(f"Saved to: {output_path}")

    # Print category distribution
    categories = defaultdict(int)
    for d in training_data:
        categories[d["category"]] += 1
    print(f"\nCategory distribution:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    return training_data


# ============================================================================
# Model training with multiple algorithms
# ============================================================================

def prepare_features(training_data: list[dict]):
    """Prepare feature matrix and targets from training data."""
    # Identify all palette feature columns
    palette_keys = set()
    for d in training_data:
        for k in d.keys():
            if k.endswith(("_L", "_C", "_H")) and not k.startswith("target") and not k.startswith("palette_"):
                palette_keys.add(k)
    palette_keys = sorted(palette_keys)

    # Identify palette statistics columns
    stat_keys = [k for k in training_data[0].keys() if k.startswith("palette_")]

    # Identify color relationship columns
    rel_keys = ["closest_L_dist", "closest_C_dist", "closest_H_dist", "closest_overall_dist"]

    # Encode categorical features
    encoders = {}
    categorical_cols = ["category", "role", "philosophy", "accent_style", "app", "property"]

    for col in categorical_cols:
        enc = LabelEncoder()
        values = [d.get(col, "unknown") for d in training_data]
        encoders[col] = enc
        enc.fit(values)

    # Build feature matrix
    X = []
    y_L, y_C, y_H = [], [], []

    for d in training_data:
        features = []

        # Palette colors (OKLCH)
        for k in palette_keys:
            features.append(d.get(k, 0))

        # Palette statistics
        for k in stat_keys:
            features.append(d.get(k, 0))

        # Color relationships
        for k in rel_keys:
            features.append(d.get(k, 0))

        # Semantic expectations
        features.append(d.get("expected_L", 0.5) * 100)
        features.append(d.get("expected_C", 0.3) * 100)

        # Philosophy numerical features
        features.append(d.get("warmth", 0.5) * 100)
        features.append(d.get("contrast", 0.5) * 100)
        features.append(d.get("saturation_pref", 0.5) * 100)

        # Categorical encodings
        for col in categorical_cols:
            try:
                val = encoders[col].transform([d.get(col, "unknown")])[0]
            except ValueError:
                val = 0
            features.append(val)

        X.append(features)
        y_L.append(d["target_L"])
        y_C.append(d["target_C"])
        y_H.append(d["target_H"])

    feature_names = (
        palette_keys +
        stat_keys +
        rel_keys +
        ["expected_L", "expected_C", "warmth", "contrast", "saturation_pref"] +
        categorical_cols
    )

    return (
        np.array(X),
        np.array(y_L),
        np.array(y_C),
        np.array(y_H),
        feature_names,
        encoders,
    )


def train_and_compare_models(training_data: list[dict] = None):
    """Train multiple models and compare performance."""
    if not SKLEARN_AVAILABLE:
        print("Error: scikit-learn not installed")
        return None

    # Load training data if not provided
    if training_data is None:
        data_path = Path(__file__).parent / "training_data_enhanced.json"
        if not data_path.exists():
            print("No training data found. Run: python ml_enhanced_predictor.py extract")
            return None
        with open(data_path) as f:
            training_data = json.load(f)

    # Filter to only samples with palette data
    training_data = [d for d in training_data if any(k.endswith("_L") and not k.startswith("target") for k in d.keys())]

    print(f"Training on {len(training_data)} samples (with palette data)")

    # Prepare features
    X, y_L, y_C, y_H, feature_names, encoders = prepare_features(training_data)
    print(f"Feature matrix shape: {X.shape}")

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Define models to compare
    models = {
        "RandomForest": RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1),
        "GradientBoosting": GradientBoostingRegressor(n_estimators=100, random_state=42),
        "ExtraTrees": ExtraTreesRegressor(n_estimators=100, random_state=42, n_jobs=-1),
        "Ridge": Ridge(alpha=1.0),
        "KNeighbors": KNeighborsRegressor(n_neighbors=5, weights='distance'),
    }

    if XGBOOST_AVAILABLE:
        models["XGBoost"] = xgb.XGBRegressor(n_estimators=100, random_state=42, n_jobs=-1, verbosity=0)

    if MLP_AVAILABLE:
        models["MLP_small"] = MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=500, random_state=42, early_stopping=True)
        models["MLP_medium"] = MLPRegressor(hidden_layer_sizes=(128, 64, 32), max_iter=500, random_state=42, early_stopping=True)

    # Split data
    X_train, X_test, y_L_train, y_L_test = train_test_split(X_scaled, y_L, test_size=0.2, random_state=42)
    _, _, y_C_train, y_C_test = train_test_split(X_scaled, y_C, test_size=0.2, random_state=42)
    _, _, y_H_train, y_H_test = train_test_split(X_scaled, y_H, test_size=0.2, random_state=42)

    results = {}

    print("\n" + "=" * 80)
    print("MODEL COMPARISON")
    print("=" * 80)

    for name, model in models.items():
        print(f"\n{name}:")
        print("-" * 40)

        # Train separate models for L, C, H
        model_L = model.__class__(**model.get_params())
        model_C = model.__class__(**model.get_params())
        model_H = model.__class__(**model.get_params())

        model_L.fit(X_train, y_L_train)
        model_C.fit(X_train, y_C_train)
        model_H.fit(X_train, y_H_train)

        # Evaluate
        pred_L = model_L.predict(X_test)
        pred_C = model_C.predict(X_test)
        pred_H = model_H.predict(X_test)

        r2_L = r2_score(y_L_test, pred_L)
        r2_C = r2_score(y_C_test, pred_C)
        r2_H = r2_score(y_H_test, pred_H)

        mae_L = mean_absolute_error(y_L_test, pred_L)
        mae_C = mean_absolute_error(y_C_test, pred_C)
        mae_H = mean_absolute_error(y_H_test, pred_H)

        print(f"  Lightness - R²: {r2_L:.3f}, MAE: {mae_L:.2f}")
        print(f"  Chroma    - R²: {r2_C:.3f}, MAE: {mae_C:.2f}")
        print(f"  Hue       - R²: {r2_H:.3f}, MAE: {mae_H:.2f}")

        # Combined color error
        combined_errors = []
        for i in range(len(pred_L)):
            error = math.sqrt(
                (pred_L[i] - y_L_test[i])**2 +
                (pred_C[i] - y_C_test[i])**2 +
                ((pred_H[i] - y_H_test[i])/10)**2
            )
            combined_errors.append(error)

        avg_error = np.mean(combined_errors)
        pct_under_5 = np.mean([1 if e < 5 else 0 for e in combined_errors]) * 100

        print(f"  Combined  - Avg Error: {avg_error:.2f}, <5 error: {pct_under_5:.1f}%")

        results[name] = {
            "r2_L": r2_L, "r2_C": r2_C, "r2_H": r2_H,
            "mae_L": mae_L, "mae_C": mae_C, "mae_H": mae_H,
            "avg_error": avg_error,
            "pct_under_5": pct_under_5,
            "model_L": model_L,
            "model_C": model_C,
            "model_H": model_H,
        }

    # Best model summary
    print("\n" + "=" * 80)
    print("BEST MODELS BY METRIC")
    print("=" * 80)

    best_r2_L = max(results.items(), key=lambda x: x[1]["r2_L"])
    best_r2_C = max(results.items(), key=lambda x: x[1]["r2_C"])
    best_r2_H = max(results.items(), key=lambda x: x[1]["r2_H"])
    best_combined = min(results.items(), key=lambda x: x[1]["avg_error"])

    print(f"Best Lightness R²:  {best_r2_L[0]} ({best_r2_L[1]['r2_L']:.3f})")
    print(f"Best Chroma R²:     {best_r2_C[0]} ({best_r2_C[1]['r2_C']:.3f})")
    print(f"Best Hue R²:        {best_r2_H[0]} ({best_r2_H[1]['r2_H']:.3f})")
    print(f"Best Combined:      {best_combined[0]} (avg error: {best_combined[1]['avg_error']:.2f})")

    # Feature importance from best tree model
    tree_models = ["RandomForest", "ExtraTrees", "GradientBoosting"]
    if XGBOOST_AVAILABLE:
        tree_models.append("XGBoost")

    best_tree = None
    best_tree_score = -float("inf")
    for name in tree_models:
        if name in results and results[name]["r2_L"] > best_tree_score:
            best_tree = name
            best_tree_score = results[name]["r2_L"]

    if best_tree:
        print(f"\nFeature Importances ({best_tree} Lightness model):")
        print("-" * 40)
        importances = list(zip(feature_names, results[best_tree]["model_L"].feature_importances_))
        importances.sort(key=lambda x: -x[1])
        for name, imp in importances[:15]:
            print(f"  {name:30} {imp:.4f}")

    return results, scaler, encoders, feature_names


def comprehensive_training(training_data: list[dict] = None):
    """Train on all color representations with hyperparameter tuning."""
    if not SKLEARN_AVAILABLE:
        print("Error: scikit-learn not installed")
        return None

    # Load training data if not provided
    if training_data is None:
        data_path = Path(__file__).parent / "training_data_enhanced.json"
        if not data_path.exists():
            print("No training data found. Run: python ml_enhanced_predictor.py extract")
            return None
        with open(data_path) as f:
            training_data = json.load(f)

    training_data = [d for d in training_data if any(k.endswith("_L") and not k.startswith("target") for k in d.keys())]
    print(f"Training on {len(training_data)} samples")

    # Prepare features
    X, _, _, _, feature_names, encoders = prepare_features(training_data)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Define all target variables to test
    target_configs = {
        # OKLCH
        "OKLCH_L": ("target_L", "Lightness (OKLCH)"),
        "OKLCH_C": ("target_C", "Chroma (OKLCH)"),
        "OKLCH_H": ("target_H", "Hue (OKLCH)"),
        # RGB
        "RGB_R": ("target_R", "Red"),
        "RGB_G": ("target_G", "Green"),
        "RGB_B": ("target_B", "Blue"),
        # LAB
        "LAB_L": ("target_Lab_L", "L* (CIELAB)"),
        "LAB_a": ("target_Lab_a", "a* (CIELAB)"),
        "LAB_b": ("target_Lab_b", "b* (CIELAB)"),
        # HSL
        "HSL_H": ("target_HSL_H", "Hue (HSL)"),
        "HSL_S": ("target_HSL_S", "Saturation (HSL)"),
        "HSL_L": ("target_HSL_Lightness", "Lightness (HSL)"),
        # Derived
        "Temperature": ("target_temperature", "Color Temperature"),
        "Brightness": ("target_brightness", "Perceived Brightness"),
    }

    # Models to test with tuning parameters
    model_configs = {
        "ExtraTrees": {
            "model": ExtraTreesRegressor(random_state=42, n_jobs=-1),
            "params": {
                "n_estimators": [100, 200],
                "max_depth": [None, 30],
                "min_samples_leaf": [1, 2],
            }
        },
        "RandomForest": {
            "model": RandomForestRegressor(random_state=42, n_jobs=-1),
            "params": {
                "n_estimators": [100, 200],
                "max_depth": [None, 30],
                "min_samples_leaf": [1, 2],
            }
        },
        "GradientBoosting": {
            "model": GradientBoostingRegressor(random_state=42),
            "params": {
                "n_estimators": [100, 200],
                "max_depth": [3, 5],
                "learning_rate": [0.1, 0.05],
            }
        },
    }

    if XGBOOST_AVAILABLE:
        model_configs["XGBoost"] = {
            "model": xgb.XGBRegressor(random_state=42, n_jobs=-1, verbosity=0),
            "params": {
                "n_estimators": [100, 200],
                "max_depth": [3, 6],
                "learning_rate": [0.1, 0.05],
            }
        }

    results = {}

    print("\n" + "=" * 100)
    print("COMPREHENSIVE MODEL TRAINING WITH HYPERPARAMETER TUNING")
    print("=" * 100)

    # Train for each target
    for target_key, (target_col, target_name) in target_configs.items():
        y = np.array([d.get(target_col, 0) for d in training_data])

        # Skip if target has no variance
        if np.std(y) < 0.001:
            continue

        X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)

        print(f"\n{target_name} ({target_key})")
        print("-" * 60)

        target_results = {}

        for model_name, config in model_configs.items():
            grid = GridSearchCV(
                config["model"].__class__(**{k: v for k, v in config["model"].get_params().items() if k != 'n_jobs'}),
                config["params"],
                cv=3,
                scoring='r2',
                n_jobs=-1,
            )
            grid.fit(X_train, y_train)

            pred = grid.predict(X_test)
            r2 = r2_score(y_test, pred)
            mae = mean_absolute_error(y_test, pred)

            target_results[model_name] = {
                "r2": r2,
                "mae": mae,
                "best_params": grid.best_params_,
                "model": grid.best_estimator_,
            }

            print(f"  {model_name:20} R²={r2:.3f}  MAE={mae:.2f}  params={grid.best_params_}")

        results[target_key] = target_results

    # Summary
    print("\n" + "=" * 100)
    print("BEST RESULTS BY TARGET VARIABLE")
    print("=" * 100)
    print(f"{'Target':<25} {'Best Model':<20} {'R²':<10} {'MAE':<10}")
    print("-" * 70)

    best_overall = {}
    for target_key, target_results in results.items():
        if not target_results:
            continue
        best = max(target_results.items(), key=lambda x: x[1]["r2"])
        target_name = target_configs[target_key][1]
        print(f"{target_name:<25} {best[0]:<20} {best[1]['r2']:.3f}      {best[1]['mae']:.2f}")
        best_overall[target_key] = best

    # Color space comparison
    print("\n" + "=" * 100)
    print("COLOR SPACE COMPARISON (Best R² per space)")
    print("=" * 100)

    spaces = {
        "OKLCH": ["OKLCH_L", "OKLCH_C", "OKLCH_H"],
        "RGB": ["RGB_R", "RGB_G", "RGB_B"],
        "CIELAB": ["LAB_L", "LAB_a", "LAB_b"],
        "HSL": ["HSL_H", "HSL_S", "HSL_L"],
        "Derived": ["Temperature", "Brightness"],
    }

    for space_name, keys in spaces.items():
        r2_vals = []
        for k in keys:
            if k in best_overall:
                r2_vals.append(best_overall[k][1]["r2"])
        if r2_vals:
            avg_r2 = np.mean(r2_vals)
            components = ', '.join(f"{k}={best_overall[k][1]['r2']:.2f}" for k in keys if k in best_overall)
            print(f"{space_name:<12} Avg R²={avg_r2:.3f}  Components: {components}")

    return results, best_overall


def tune_best_model(training_data: list[dict] = None):
    """Hyperparameter tune the best performing model (ExtraTrees)."""
    if not SKLEARN_AVAILABLE:
        print("Error: scikit-learn not installed")
        return None

    # Load training data if not provided
    if training_data is None:
        data_path = Path(__file__).parent / "training_data_enhanced.json"
        if not data_path.exists():
            print("No training data found. Run: python ml_enhanced_predictor.py extract")
            return None
        with open(data_path) as f:
            training_data = json.load(f)

    training_data = [d for d in training_data if any(k.endswith("_L") and not k.startswith("target") for k in d.keys())]
    X, y_L, y_C, y_H, feature_names, encoders = prepare_features(training_data)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_train, X_test, y_L_train, y_L_test = train_test_split(X_scaled, y_L, test_size=0.2, random_state=42)
    _, _, y_C_train, y_C_test = train_test_split(X_scaled, y_C, test_size=0.2, random_state=42)
    _, _, y_H_train, y_H_test = train_test_split(X_scaled, y_H, test_size=0.2, random_state=42)

    print("Tuning ExtraTrees hyperparameters...")
    print("-" * 60)

    param_grid = {
        'n_estimators': [100, 200, 300],
        'max_depth': [None, 20, 30, 50],
        'min_samples_split': [2, 5, 10],
        'min_samples_leaf': [1, 2, 4],
    }

    base_model = ExtraTreesRegressor(random_state=42, n_jobs=-1)

    grid_search = GridSearchCV(
        base_model, param_grid, cv=5, scoring='r2', n_jobs=-1, verbose=1
    )
    grid_search.fit(X_train, y_L_train)

    print(f"\nBest parameters: {grid_search.best_params_}")
    print(f"Best CV R²: {grid_search.best_score_:.3f}")

    # Train final models with best params
    best_params = grid_search.best_params_
    model_L = ExtraTreesRegressor(**best_params, random_state=42, n_jobs=-1)
    model_C = ExtraTreesRegressor(**best_params, random_state=42, n_jobs=-1)
    model_H = ExtraTreesRegressor(**best_params, random_state=42, n_jobs=-1)

    model_L.fit(X_train, y_L_train)
    model_C.fit(X_train, y_C_train)
    model_H.fit(X_train, y_H_train)

    pred_L = model_L.predict(X_test)
    pred_C = model_C.predict(X_test)
    pred_H = model_H.predict(X_test)

    print(f"\nTuned Model Performance:")
    print(f"  Lightness R²: {r2_score(y_L_test, pred_L):.3f}")
    print(f"  Chroma R²:    {r2_score(y_C_test, pred_C):.3f}")
    print(f"  Hue R²:       {r2_score(y_H_test, pred_H):.3f}")

    return {
        "model_L": model_L,
        "model_C": model_C,
        "model_H": model_H,
        "scaler": scaler,
        "encoders": encoders,
        "feature_names": feature_names,
        "params": best_params,
    }


def show_predictions(training_data: list[dict] = None, n_samples: int = 30):
    """Show sample predictions vs actual values."""
    if not SKLEARN_AVAILABLE:
        print("Error: scikit-learn not installed")
        return

    # Load training data if not provided
    if training_data is None:
        data_path = Path(__file__).parent / "training_data_enhanced.json"
        if not data_path.exists():
            print("No training data found. Run: python ml_enhanced_predictor.py extract")
            return
        with open(data_path) as f:
            training_data = json.load(f)

    training_data = [d for d in training_data if any(k.endswith("_L") and not k.startswith("target") for k in d.keys())]
    X, y_L, y_C, y_H, feature_names, encoders = prepare_features(training_data)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_train, X_test, y_L_train, y_L_test = train_test_split(X_scaled, y_L, test_size=0.2, random_state=42)
    _, _, y_C_train, y_C_test = train_test_split(X_scaled, y_C, test_size=0.2, random_state=42)
    _, _, y_H_train, y_H_test = train_test_split(X_scaled, y_H, test_size=0.2, random_state=42)

    # Get test indices
    _, test_indices = train_test_split(range(len(training_data)), test_size=0.2, random_state=42)

    # Train ExtraTrees
    model_L = ExtraTreesRegressor(n_estimators=200, random_state=42, n_jobs=-1)
    model_C = ExtraTreesRegressor(n_estimators=200, random_state=42, n_jobs=-1)
    model_H = ExtraTreesRegressor(n_estimators=200, random_state=42, n_jobs=-1)

    model_L.fit(X_train, y_L_train)
    model_C.fit(X_train, y_C_train)
    model_H.fit(X_train, y_H_train)

    pred_L = model_L.predict(X_test)
    pred_C = model_C.predict(X_test)
    pred_H = model_H.predict(X_test)

    print("\n" + "=" * 100)
    print("SAMPLE PREDICTIONS")
    print("=" * 100)
    print(f"{'Theme':<15} {'Property':<25} {'Cat':<12} {'Actual':<10} {'Predicted':<10} {'Error':<8}")
    print("-" * 100)

    errors = []
    for i in range(min(n_samples, len(test_indices))):
        sample = training_data[test_indices[i]]

        try:
            actual_rgb = oklch_to_rgb(y_L_test[i], y_C_test[i], y_H_test[i])
            actual_hex = rgb_to_hex(*actual_rgb)
        except:
            actual_hex = sample.get("target_hex", "?")

        try:
            pred_rgb = oklch_to_rgb(pred_L[i], pred_C[i], pred_H[i])
            pred_hex = rgb_to_hex(*pred_rgb)
        except:
            pred_hex = "??????"

        error = math.sqrt(
            (pred_L[i] - y_L_test[i])**2 +
            (pred_C[i] - y_C_test[i])**2 +
            ((pred_H[i] - y_H_test[i])/10)**2
        )
        errors.append(error)

        match = "✓" if error < 5 else "✗"
        print(f"{match} {sample['theme']:<13} {sample['property']:<25} {sample['category']:<12} {actual_hex:<10} {pred_hex:<10} {error:.2f}")

    print("-" * 100)
    print(f"Average error: {np.mean(errors):.2f}")
    print(f"Median error: {np.median(errors):.2f}")
    print(f"% under 5: {np.mean([1 if e < 5 else 0 for e in errors]) * 100:.1f}%")
    print(f"% under 10: {np.mean([1 if e < 10 else 0 for e in errors]) * 100:.1f}%")


def analyze_by_category(training_data: list[dict] = None):
    """Analyze model performance by property category."""
    if not SKLEARN_AVAILABLE:
        print("Error: scikit-learn not installed")
        return

    # Load training data if not provided
    if training_data is None:
        data_path = Path(__file__).parent / "training_data_enhanced.json"
        if not data_path.exists():
            print("No training data found. Run: python ml_enhanced_predictor.py extract")
            return
        with open(data_path) as f:
            training_data = json.load(f)

    # Filter to samples with palette data
    training_data = [d for d in training_data if any(k.endswith("_L") and not k.startswith("target") for k in d.keys())]

    print(f"\nAnalyzing {len(training_data)} samples by category...")

    # Group by category
    by_category = defaultdict(list)
    for d in training_data:
        by_category[d["category"]].append(d)

    print("\n" + "=" * 80)
    print("CATEGORY-SPECIFIC ANALYSIS")
    print("=" * 80)

    for category, samples in sorted(by_category.items(), key=lambda x: -len(x[1])):
        if len(samples) < 10:
            continue

        print(f"\n{category.upper()} ({len(samples)} samples)")
        print("-" * 40)

        # Prepare features just for this category
        X, y_L, y_C, y_H, feature_names, _ = prepare_features(samples)

        if len(X) < 20:
            print("  Too few samples for reliable training")
            continue

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        X_train, X_test, y_L_train, y_L_test = train_test_split(X_scaled, y_L, test_size=0.2, random_state=42)
        _, _, y_C_train, y_C_test = train_test_split(X_scaled, y_C, test_size=0.2, random_state=42)
        _, _, y_H_train, y_H_test = train_test_split(X_scaled, y_H, test_size=0.2, random_state=42)

        model_L = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
        model_L.fit(X_train, y_L_train)
        pred_L = model_L.predict(X_test)

        model_C = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
        model_C.fit(X_train, y_C_train)
        pred_C = model_C.predict(X_test)

        r2_L = r2_score(y_L_test, pred_L)
        r2_C = r2_score(y_C_test, pred_C)

        print(f"  Lightness R²: {r2_L:.3f}")
        print(f"  Chroma R²:    {r2_C:.3f}")

        # Top features for this category
        importances = list(zip(feature_names, model_L.feature_importances_))
        importances.sort(key=lambda x: -x[1])
        print(f"  Top features: {', '.join([f[0] for f in importances[:5]])}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nCommands:")
        print("  extract      - Extract training data from omarchy themes")
        print("  train        - Train and compare all models (quick)")
        print("  comprehensive - Train all models on all color spaces with tuning")
        print("  tune         - Hyperparameter tune ExtraTrees only")
        print("  predict      - Show sample predictions")
        print("  analyze      - Analyze performance by category")
        print("  all          - Run extract, train, and analyze")
        return

    command = sys.argv[1]

    if command == "extract":
        extract_all_training_data()
    elif command == "train":
        train_and_compare_models()
    elif command == "comprehensive":
        comprehensive_training()
    elif command == "tune":
        tune_best_model()
    elif command == "predict":
        show_predictions()
    elif command == "analyze":
        analyze_by_category()
    elif command == "all":
        print("Extracting training data...")
        data = extract_all_training_data()
        print("\nTraining models...")
        train_and_compare_models(data)
        print("\nAnalyzing by category...")
        analyze_by_category(data)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
