#!/usr/bin/env python3
"""
Perceptual Color Difference Analysis

Analyzes ML predictions in terms of human-perceptible color differences (Delta E).

Delta E thresholds:
- ΔE < 1.0:  Imperceptible to human eye
- ΔE 1-2:    Perceptible through close observation
- ΔE 2-10:   Perceptible at a glance
- ΔE 10-49:  Colors are similar but clearly different
- ΔE > 49:   Colors are very different

This helps answer: "Even if R² is low, are predictions close enough for practical use?"
"""

import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

from sklearn.ensemble import ExtraTreesRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import r2_score, mean_absolute_error


# Color conversion utilities (from ml_enhanced_predictor.py)
def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#").lower()
    if len(h) == 3:
        h = "".join([c * 2 for c in h])
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_lab(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert RGB to CIELAB."""
    r, g, b = r / 255.0, g / 255.0, b / 255.0

    def to_linear(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = to_linear(r), to_linear(g), to_linear(b)

    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041

    x /= 0.95047
    y /= 1.00000
    z /= 1.08883

    def f(t):
        return t ** (1/3) if t > 0.008856 else (7.787 * t) + (16/116)

    L = (116 * f(y)) - 16
    a = 500 * (f(x) - f(y))
    b_val = 200 * (f(y) - f(z))

    return (L, a, b_val)


def delta_e_cie76(lab1: tuple, lab2: tuple) -> float:
    """Calculate CIE76 Delta E (simple Euclidean in LAB space)."""
    return math.sqrt(
        (lab1[0] - lab2[0])**2 +
        (lab1[1] - lab2[1])**2 +
        (lab1[2] - lab2[2])**2
    )


def delta_e_cie94(lab1: tuple, lab2: tuple) -> float:
    """Calculate CIE94 Delta E (improved perceptual accuracy)."""
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2

    dL = L1 - L2
    C1 = math.sqrt(a1**2 + b1**2)
    C2 = math.sqrt(a2**2 + b2**2)
    dC = C1 - C2

    da = a1 - a2
    db = b1 - b2
    dH_sq = da**2 + db**2 - dC**2
    dH = math.sqrt(max(0, dH_sq))

    SL = 1
    SC = 1 + 0.045 * C1
    SH = 1 + 0.015 * C1

    kL = kC = kH = 1

    dE = math.sqrt(
        (dL / (kL * SL))**2 +
        (dC / (kC * SC))**2 +
        (dH / (kH * SH))**2
    )
    return dE


def rgb_to_hex(r: int, g: int, b: int) -> str:
    r = max(0, min(255, int(round(r))))
    g = max(0, min(255, int(round(g))))
    b = max(0, min(255, int(round(b))))
    return f"#{r:02X}{g:02X}{b:02X}"


def print_color_block(hex_color: str) -> str:
    """Return ANSI escape code to display color block."""
    try:
        r, g, b = hex_to_rgb(hex_color)
        return f"\033[48;2;{r};{g};{b}m  \033[0m"
    except:
        return "  "


def print_progress_bar(iteration, total, prefix='', suffix='', length=40, fill='█'):
    """Print a progress bar to terminal."""
    percent = f"{100 * (iteration / float(total)):.1f}"
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='\r', flush=True)
    if iteration == total:
        print()


def prepare_features(training_data: list[dict]):
    """Prepare feature matrix from training data."""
    palette_keys = sorted(set(
        k for d in training_data
        for k in d.keys()
        if k.endswith(('_L', '_C', '_H')) and not k.startswith('target') and not k.startswith('palette_')
    ))

    stat_keys = [k for k in training_data[0].keys() if k.startswith('palette_')]
    rel_keys = ['closest_L_dist', 'closest_C_dist', 'closest_H_dist', 'closest_overall_dist']
    categorical_cols = ['category', 'role', 'philosophy', 'accent_style', 'app', 'property']

    encoders = {}
    for col in categorical_cols:
        enc = LabelEncoder()
        values = [d.get(col, 'unknown') for d in training_data]
        encoders[col] = enc
        enc.fit(values)

    X = []
    for d in training_data:
        features = []
        for k in palette_keys:
            features.append(d.get(k, 0))
        for k in stat_keys:
            features.append(d.get(k, 0))
        for k in rel_keys:
            features.append(d.get(k, 0))
        features.append(d.get('expected_L', 0.5) * 100)
        features.append(d.get('expected_C', 0.3) * 100)
        features.append(d.get('warmth', 0.5) * 100)
        features.append(d.get('contrast', 0.5) * 100)
        features.append(d.get('saturation_pref', 0.5) * 100)
        for col in categorical_cols:
            try:
                val = encoders[col].transform([d.get(col, 'unknown')])[0]
            except:
                val = 0
            features.append(val)
        X.append(features)

    return np.array(X), encoders


def run_perceptual_analysis():
    """Run comprehensive perceptual analysis with live progress."""
    print("\n" + "=" * 80)
    print("  PERCEPTUAL COLOR DIFFERENCE ANALYSIS")
    print("  Measuring how close predictions are to human-imperceptible")
    print("=" * 80)

    # Load data
    data_path = Path(__file__).parent / "training_data_enhanced.json"
    if not data_path.exists():
        print("No training data. Run: python ml_enhanced_predictor.py extract")
        return

    with open(data_path) as f:
        training_data = json.load(f)

    training_data = [d for d in training_data if any(
        k.endswith("_L") and not k.startswith("target") for k in d.keys()
    )]

    print(f"\n📊 Loaded {len(training_data)} samples from 14 omarchy themes")
    print("-" * 80)

    # Prepare features
    print("\n🔧 Preparing features...", end=" ", flush=True)
    X, encoders = prepare_features(training_data)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    print(f"Done! Shape: {X.shape}")

    # Extract RGB targets
    y_R = np.array([d.get('target_R', 0) for d in training_data])
    y_G = np.array([d.get('target_G', 0) for d in training_data])
    y_B = np.array([d.get('target_B', 0) for d in training_data])

    # Split data
    X_train, X_test, y_R_train, y_R_test = train_test_split(X_scaled, y_R, test_size=0.2, random_state=42)
    _, _, y_G_train, y_G_test = train_test_split(X_scaled, y_G, test_size=0.2, random_state=42)
    _, _, y_B_train, y_B_test = train_test_split(X_scaled, y_B, test_size=0.2, random_state=42)

    # Get test indices for sample info
    _, test_indices = train_test_split(range(len(training_data)), test_size=0.2, random_state=42)

    print(f"\n🎯 Training ExtraTrees models (optimized params)...")
    print("-" * 80)

    # Train RGB models with progress
    models = {}
    channels = [('R', y_R_train, y_R_test), ('G', y_G_train, y_G_test), ('B', y_B_train, y_B_test)]

    for i, (name, y_train, y_test) in enumerate(channels):
        print(f"\n  Training {name} channel...", end=" ", flush=True)
        start = time.time()

        model = ExtraTreesRegressor(
            n_estimators=200,
            max_depth=None,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
            verbose=0
        )
        model.fit(X_train, y_train)
        models[name] = model

        elapsed = time.time() - start
        r2 = r2_score(y_test, model.predict(X_test))
        print(f"Done! R²={r2:.3f} ({elapsed:.1f}s)")

    # Predict
    print("\n🔮 Generating predictions...", end=" ", flush=True)
    pred_R = models['R'].predict(X_test)
    pred_G = models['G'].predict(X_test)
    pred_B = models['B'].predict(X_test)
    print("Done!")

    # Calculate Delta E for each prediction
    print("\n📏 Calculating perceptual differences (Delta E)...")
    print("-" * 80)

    delta_e_values = []
    delta_e_94_values = []

    n_test = len(y_R_test)

    for i in range(n_test):
        if i % 50 == 0:
            print_progress_bar(i, n_test, prefix='  Progress:', suffix=f'{i}/{n_test}')

        # Actual color
        actual_rgb = (int(y_R_test[i]), int(y_G_test[i]), int(y_B_test[i]))
        actual_lab = rgb_to_lab(*actual_rgb)

        # Predicted color
        pred_rgb = (int(round(pred_R[i])), int(round(pred_G[i])), int(round(pred_B[i])))
        pred_rgb = tuple(max(0, min(255, c)) for c in pred_rgb)
        pred_lab = rgb_to_lab(*pred_rgb)

        # Calculate Delta E
        de76 = delta_e_cie76(actual_lab, pred_lab)
        de94 = delta_e_cie94(actual_lab, pred_lab)

        delta_e_values.append(de76)
        delta_e_94_values.append(de94)

    print_progress_bar(n_test, n_test, prefix='  Progress:', suffix=f'{n_test}/{n_test}')

    # Analyze results
    print("\n" + "=" * 80)
    print("  PERCEPTUAL ANALYSIS RESULTS")
    print("=" * 80)

    print("\n📊 Delta E Distribution (CIE76):")
    print("-" * 60)

    thresholds = [
        (1.0, "Imperceptible", "🟢"),
        (2.0, "Barely perceptible", "🟡"),
        (5.0, "Noticeable", "🟠"),
        (10.0, "Obvious difference", "🔴"),
        (float('inf'), "Very different", "⚫"),
    ]

    prev_thresh = 0
    for thresh, desc, emoji in thresholds:
        count = sum(1 for de in delta_e_values if prev_thresh <= de < thresh)
        pct = count / len(delta_e_values) * 100
        bar = "█" * int(pct / 2)
        print(f"  {emoji} ΔE {prev_thresh:>4.1f}-{thresh if thresh < 100 else '∞':>4}: {count:4} ({pct:5.1f}%) {bar}")
        prev_thresh = thresh

    print("\n📈 Statistics:")
    print("-" * 60)
    print(f"  Mean ΔE (CIE76):   {np.mean(delta_e_values):.2f}")
    print(f"  Median ΔE:         {np.median(delta_e_values):.2f}")
    print(f"  Std Dev:           {np.std(delta_e_values):.2f}")
    print(f"  Min ΔE:            {np.min(delta_e_values):.2f}")
    print(f"  Max ΔE:            {np.max(delta_e_values):.2f}")

    print(f"\n  Mean ΔE (CIE94):   {np.mean(delta_e_94_values):.2f}")
    print(f"  Median ΔE (CIE94): {np.median(delta_e_94_values):.2f}")

    # Perceptual success rates
    print("\n✅ Perceptual Success Rates:")
    print("-" * 60)
    imperceptible = sum(1 for de in delta_e_values if de < 1.0) / len(delta_e_values) * 100
    barely = sum(1 for de in delta_e_values if de < 2.0) / len(delta_e_values) * 100
    acceptable = sum(1 for de in delta_e_values if de < 5.0) / len(delta_e_values) * 100
    close = sum(1 for de in delta_e_values if de < 10.0) / len(delta_e_values) * 100

    print(f"  ΔE < 1.0  (imperceptible):     {imperceptible:5.1f}%")
    print(f"  ΔE < 2.0  (barely visible):    {barely:5.1f}%")
    print(f"  ΔE < 5.0  (acceptable):        {acceptable:5.1f}%")
    print(f"  ΔE < 10.0 (close enough):      {close:5.1f}%")

    # Show sample predictions with colors
    print("\n" + "=" * 80)
    print("  SAMPLE PREDICTIONS (sorted by error)")
    print("=" * 80)
    print(f"\n{'Theme':<12} {'Property':<20} {'Actual':<10} {'Predicted':<10} {'ΔE':<8} Visual")
    print("-" * 80)

    # Sort by delta E
    sorted_indices = np.argsort(delta_e_values)

    # Show best 10
    print("\n🟢 BEST PREDICTIONS (lowest ΔE):")
    for idx in sorted_indices[:10]:
        sample = training_data[test_indices[idx]]
        actual_hex = sample.get('target_hex', '#??????')
        pred_rgb = (int(round(pred_R[idx])), int(round(pred_G[idx])), int(round(pred_B[idx])))
        pred_rgb = tuple(max(0, min(255, c)) for c in pred_rgb)
        pred_hex = rgb_to_hex(*pred_rgb)
        de = delta_e_values[idx]

        actual_block = print_color_block(actual_hex)
        pred_block = print_color_block(pred_hex)

        status = "✓" if de < 2.0 else "~" if de < 5.0 else "✗"
        print(f"{status} {sample['theme']:<11} {sample['property']:<20} {actual_hex:<10} {pred_hex:<10} {de:>6.2f}  {actual_block} → {pred_block}")

    # Show worst 10
    print("\n🔴 WORST PREDICTIONS (highest ΔE):")
    for idx in sorted_indices[-10:]:
        sample = training_data[test_indices[idx]]
        actual_hex = sample.get('target_hex', '#??????')
        pred_rgb = (int(round(pred_R[idx])), int(round(pred_G[idx])), int(round(pred_B[idx])))
        pred_rgb = tuple(max(0, min(255, c)) for c in pred_rgb)
        pred_hex = rgb_to_hex(*pred_rgb)
        de = delta_e_values[idx]

        actual_block = print_color_block(actual_hex)
        pred_block = print_color_block(pred_hex)

        status = "✓" if de < 2.0 else "~" if de < 5.0 else "✗"
        print(f"{status} {sample['theme']:<11} {sample['property']:<20} {actual_hex:<10} {pred_hex:<10} {de:>6.2f}  {actual_block} → {pred_block}")

    # Analyze by category
    print("\n" + "=" * 80)
    print("  ANALYSIS BY CATEGORY")
    print("=" * 80)

    by_category = defaultdict(list)
    for i, de in enumerate(delta_e_values):
        sample = training_data[test_indices[i]]
        by_category[sample['category']].append(de)

    print(f"\n{'Category':<15} {'Count':<8} {'Mean ΔE':<10} {'Median':<10} {'< 5.0':<10} {'< 10.0':<10}")
    print("-" * 70)

    for cat in sorted(by_category.keys(), key=lambda c: np.mean(by_category[c])):
        des = by_category[cat]
        mean_de = np.mean(des)
        median_de = np.median(des)
        under5 = sum(1 for d in des if d < 5.0) / len(des) * 100
        under10 = sum(1 for d in des if d < 10.0) / len(des) * 100

        bar = "█" * int(under5 / 5)
        print(f"  {cat:<13} {len(des):<8} {mean_de:<10.2f} {median_de:<10.2f} {under5:<9.1f}% {under10:<9.1f}% {bar}")

    print("\n" + "=" * 80)
    print("  CONCLUSION")
    print("=" * 80)

    if acceptable > 50:
        print(f"\n  ✅ {acceptable:.1f}% of predictions are within acceptable perceptual range (ΔE < 5)")
        print(f"     This means the model produces colors that look close to the target!")
    else:
        print(f"\n  ⚠️  Only {acceptable:.1f}% of predictions are within acceptable range (ΔE < 5)")
        print(f"     The model needs improvement for production use.")

    if imperceptible > 10:
        print(f"\n  🎯 {imperceptible:.1f}% are imperceptible to humans (ΔE < 1)")

    return {
        "delta_e_values": delta_e_values,
        "mean": np.mean(delta_e_values),
        "median": np.median(delta_e_values),
        "pct_under_5": acceptable,
        "pct_under_10": close,
    }


if __name__ == "__main__":
    run_perceptual_analysis()
