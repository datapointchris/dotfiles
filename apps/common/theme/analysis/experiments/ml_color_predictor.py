#!/usr/bin/env python3
"""
Machine Learning Color Predictor

Trains on omarchy's hand-crafted themes to learn color selection patterns.
Uses scikit-learn to predict optimal UI colors from base palettes.

Training data: omarchy themes (14 themes × multiple apps × multiple properties)
Features: Base palette colors in OKLCH + property metadata
Target: Selected color in OKLCH

Usage:
    python ml_color_predictor.py extract   # Extract training data from omarchy
    python ml_color_predictor.py train     # Train the model
    python ml_color_predictor.py predict   # Generate predictions for our themes
    python ml_color_predictor.py evaluate  # Compare predictions to omarchy
"""

import colorsys
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.model_selection import cross_val_score, train_test_split
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.metrics import mean_squared_error, r2_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("Warning: scikit-learn not installed. Run: pip install scikit-learn")


# Color conversion utilities
def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Parse hex color to RGB."""
    h = hex_str.lstrip("#").lower()
    if len(h) == 3:
        h = "".join([c * 2 for c in h])
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_oklch(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert RGB to OKLCH."""
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


# Data extraction
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


# Property categorization for features
PROPERTY_CATEGORIES = {
    # Background properties
    "main_bg": ("background", "primary"),
    "selected_bg": ("background", "selection"),

    # Foreground properties
    "main_fg": ("foreground", "primary"),
    "selected_fg": ("foreground", "selection"),
    "title": ("foreground", "title"),
    "inactive_fg": ("foreground", "inactive"),

    # UI chrome
    "cpu_box": ("border", "cpu"),
    "mem_box": ("border", "mem"),
    "net_box": ("border", "net"),
    "proc_box": ("border", "proc"),
    "div_line": ("border", "divider"),
    "hi_fg": ("accent", "highlight"),
    "proc_misc": ("accent", "misc"),

    # Gradients
    "temp_start": ("gradient", "temp_low"),
    "temp_mid": ("gradient", "temp_mid"),
    "temp_end": ("gradient", "temp_high"),
    "cpu_start": ("gradient", "cpu_low"),
    "cpu_mid": ("gradient", "cpu_mid"),
    "cpu_end": ("gradient", "cpu_high"),
    "free_start": ("gradient", "free_low"),
    "free_mid": ("gradient", "free_mid"),
    "free_end": ("gradient", "free_high"),
    "used_start": ("gradient", "used_low"),
    "used_mid": ("gradient", "used_mid"),
    "used_end": ("gradient", "used_high"),
    "download_start": ("gradient", "dl_low"),
    "download_mid": ("gradient", "dl_mid"),
    "download_end": ("gradient", "dl_high"),
    "upload_start": ("gradient", "ul_low"),
    "upload_mid": ("gradient", "ul_mid"),
    "upload_end": ("gradient", "ul_high"),
}


def extract_training_data():
    """Extract training data from omarchy themes."""
    omarchy_dir = Path.home() / "code/hypr/omarchy/themes"
    our_themes_dir = Path.home() / "dotfiles/apps/common/theme/library"

    # Map omarchy theme names to our palette names
    theme_mapping = {
        "nord": "nord",
        "kanagawa": "kanagawa",
        "gruvbox": "gruvbox-dark-hard",
        "rose-pine": "rose-pine",
        "everforest": "everforest-dark-hard",
    }

    training_data = []

    for omarchy_name, our_name in theme_mapping.items():
        omarchy_path = omarchy_dir / omarchy_name
        our_palette_path = our_themes_dir / our_name / "palette.yml"

        if not omarchy_path.exists() or not our_palette_path.exists():
            print(f"Skipping {omarchy_name}: missing files")
            continue

        # Load our base palette
        palette = load_our_palette(our_palette_path)
        if not palette:
            print(f"Skipping {omarchy_name}: empty palette")
            continue

        # Convert palette to OKLCH features
        palette_features = {}
        for key, hex_color in palette.items():
            try:
                L, C, H = hex_to_oklch(hex_color)
                palette_features[f"{key}_L"] = L
                palette_features[f"{key}_C"] = C
                palette_features[f"{key}_H"] = H
            except Exception as e:
                print(f"  Warning: Failed to convert {key}={hex_color}: {e}")

        # Extract btop colors from omarchy
        btop_path = omarchy_path / "btop.theme"
        if btop_path.exists():
            btop_colors = extract_btop_colors(btop_path)

            for prop, hex_color in btop_colors.items():
                try:
                    target_L, target_C, target_H = hex_to_oklch(hex_color)

                    # Get property category
                    cat = PROPERTY_CATEGORIES.get(prop, ("unknown", "unknown"))

                    sample = {
                        "theme": omarchy_name,
                        "app": "btop",
                        "property": prop,
                        "category": cat[0],
                        "subcategory": cat[1],
                        "target_hex": hex_color,
                        "target_L": target_L,
                        "target_C": target_C,
                        "target_H": target_H,
                        **palette_features,
                    }
                    training_data.append(sample)
                except Exception as e:
                    print(f"  Warning: Failed to process {prop}={hex_color}: {e}")

        # Extract walker colors
        walker_path = omarchy_path / "walker.css"
        if walker_path.exists():
            walker_colors = extract_walker_colors(walker_path)
            for prop, hex_color in walker_colors.items():
                try:
                    target_L, target_C, target_H = hex_to_oklch(hex_color)
                    sample = {
                        "theme": omarchy_name,
                        "app": "walker",
                        "property": prop,
                        "category": "ui",
                        "subcategory": prop.replace("-", "_"),
                        "target_hex": hex_color,
                        "target_L": target_L,
                        "target_C": target_C,
                        "target_H": target_H,
                        **palette_features,
                    }
                    training_data.append(sample)
                except Exception as e:
                    print(f"  Warning: Failed to process walker {prop}: {e}")

        print(f"Extracted {omarchy_name}: {len([d for d in training_data if d['theme'] == omarchy_name])} samples")

    # Save training data
    output_path = Path(__file__).parent / "training_data.json"
    with open(output_path, "w") as f:
        json.dump(training_data, f, indent=2)

    print(f"\nTotal samples: {len(training_data)}")
    print(f"Saved to: {output_path}")

    return training_data


def train_model(training_data: list[dict] = None):
    """Train ML model on extracted data."""
    if not SKLEARN_AVAILABLE:
        print("Error: scikit-learn not installed")
        return None

    # Load training data if not provided
    if training_data is None:
        data_path = Path(__file__).parent / "training_data.json"
        if not data_path.exists():
            print("No training data found. Run: python ml_color_predictor.py extract")
            return None
        with open(data_path) as f:
            training_data = json.load(f)

    print(f"Training on {len(training_data)} samples")

    # Prepare features and targets
    # Feature columns: all palette colors in OKLCH + categorical encoding
    palette_keys = [k for k in training_data[0].keys() if k.endswith(("_L", "_C", "_H")) and not k.startswith("target")]

    # Encode categorical features
    category_encoder = LabelEncoder()
    subcategory_encoder = LabelEncoder()
    app_encoder = LabelEncoder()
    property_encoder = LabelEncoder()

    categories = [d["category"] for d in training_data]
    subcategories = [d["subcategory"] for d in training_data]
    apps = [d["app"] for d in training_data]
    properties = [d["property"] for d in training_data]

    category_encoded = category_encoder.fit_transform(categories)
    subcategory_encoded = subcategory_encoder.fit_transform(subcategories)
    app_encoded = app_encoder.fit_transform(apps)
    property_encoded = property_encoder.fit_transform(properties)

    # Build feature matrix
    X = []
    y_L = []
    y_C = []
    y_H = []

    for i, d in enumerate(training_data):
        features = [d.get(k, 0) for k in palette_keys]
        features.extend([
            category_encoded[i],
            subcategory_encoded[i],
            app_encoded[i],
            property_encoded[i],
        ])
        X.append(features)
        y_L.append(d["target_L"])
        y_C.append(d["target_C"])
        y_H.append(d["target_H"])

    X = np.array(X)
    y_L = np.array(y_L)
    y_C = np.array(y_C)
    y_H = np.array(y_H)

    print(f"Feature matrix shape: {X.shape}")

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Train separate models for L, C, H
    print("\nTraining Lightness model...")
    model_L = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    model_L.fit(X_scaled, y_L)
    scores_L = cross_val_score(model_L, X_scaled, y_L, cv=5, scoring='r2')
    print(f"  R² scores: {scores_L}")
    print(f"  Mean R²: {scores_L.mean():.3f} (+/- {scores_L.std() * 2:.3f})")

    print("\nTraining Chroma model...")
    model_C = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    model_C.fit(X_scaled, y_C)
    scores_C = cross_val_score(model_C, X_scaled, y_C, cv=5, scoring='r2')
    print(f"  R² scores: {scores_C}")
    print(f"  Mean R²: {scores_C.mean():.3f} (+/- {scores_C.std() * 2:.3f})")

    print("\nTraining Hue model...")
    model_H = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    model_H.fit(X_scaled, y_H)
    scores_H = cross_val_score(model_H, X_scaled, y_H, cv=5, scoring='r2')
    print(f"  R² scores: {scores_H}")
    print(f"  Mean R²: {scores_H.mean():.3f} (+/- {scores_H.std() * 2:.3f})")

    # Feature importance for Lightness model
    print("\nTop 10 feature importances (Lightness):")
    feature_names = palette_keys + ["category", "subcategory", "app", "property"]
    importances = list(zip(feature_names, model_L.feature_importances_))
    importances.sort(key=lambda x: -x[1])
    for name, imp in importances[:10]:
        print(f"  {name}: {imp:.4f}")

    # Save models
    model_data = {
        "palette_keys": palette_keys,
        "category_classes": category_encoder.classes_.tolist(),
        "subcategory_classes": subcategory_encoder.classes_.tolist(),
        "app_classes": app_encoder.classes_.tolist(),
        "property_classes": property_encoder.classes_.tolist(),
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
    }

    # Note: For production, you'd save the actual sklearn models with joblib
    # For this PoC, we'll just report the results

    print("\n" + "=" * 60)
    print("MODEL TRAINING COMPLETE")
    print("=" * 60)
    print(f"Lightness R²: {scores_L.mean():.3f}")
    print(f"Chroma R²:    {scores_C.mean():.3f}")
    print(f"Hue R²:       {scores_H.mean():.3f}")

    return {
        "model_L": model_L,
        "model_C": model_C,
        "model_H": model_H,
        "scaler": scaler,
        "encoders": {
            "category": category_encoder,
            "subcategory": subcategory_encoder,
            "app": app_encoder,
            "property": property_encoder,
        },
        "palette_keys": palette_keys,
    }


def evaluate_model(models: dict = None):
    """Evaluate model predictions against omarchy themes."""
    if models is None:
        print("No models provided. Train first.")
        return

    # Load training data
    data_path = Path(__file__).parent / "training_data.json"
    with open(data_path) as f:
        training_data = json.load(f)

    print("\nEvaluating predictions...")
    print("-" * 60)

    total_error = 0
    count = 0

    for sample in training_data[:20]:  # Show first 20
        # Prepare features
        features = [sample.get(k, 0) for k in models["palette_keys"]]

        cat_idx = list(models["encoders"]["category"].classes_).index(sample["category"])
        subcat_idx = list(models["encoders"]["subcategory"].classes_).index(sample["subcategory"])
        app_idx = list(models["encoders"]["app"].classes_).index(sample["app"])
        prop_idx = list(models["encoders"]["property"].classes_).index(sample["property"])

        features.extend([cat_idx, subcat_idx, app_idx, prop_idx])

        X = np.array([features])
        X_scaled = models["scaler"].transform(X)

        # Predict
        pred_L = models["model_L"].predict(X_scaled)[0]
        pred_C = models["model_C"].predict(X_scaled)[0]
        pred_H = models["model_H"].predict(X_scaled)[0]

        # Convert to hex
        try:
            pred_rgb = oklch_to_rgb(pred_L, pred_C, pred_H)
            pred_hex = rgb_to_hex(*pred_rgb)
        except:
            pred_hex = "#??????"

        # Calculate error (deltaE in OKLCH)
        error = math.sqrt(
            (pred_L - sample["target_L"]) ** 2 +
            (pred_C - sample["target_C"]) ** 2 +
            ((pred_H - sample["target_H"]) / 10) ** 2  # Scale hue difference
        )
        total_error += error
        count += 1

        match = "✓" if error < 5 else "✗"
        print(f"{match} {sample['theme']:12} {sample['property']:20} "
              f"target={sample['target_hex']} pred={pred_hex} err={error:.2f}")

    print("-" * 60)
    print(f"Average error: {total_error / count:.2f}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1]

    if command == "extract":
        extract_training_data()
    elif command == "train":
        training_data = None
        data_path = Path(__file__).parent / "training_data.json"
        if data_path.exists():
            with open(data_path) as f:
                training_data = json.load(f)
        models = train_model(training_data)
        if models:
            evaluate_model(models)
    elif command == "evaluate":
        print("Run 'train' command which includes evaluation")
    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
