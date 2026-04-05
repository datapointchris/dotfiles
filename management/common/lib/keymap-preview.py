"""Render a ZMK keymap layer as a formatted grid for fzf preview.

Usage: python3 keymap-preview.py <keymap.yaml> <LAYER_NAME>

Reads keymap_drawer YAML format and prints a split keyboard layout
with hold-tap annotations and active combos.
"""

import json
import subprocess
import sys


def cell(v):
    """Format a single key cell from keymap_drawer YAML."""
    if isinstance(v, dict):
        parts = []
        if "t" in v:
            parts.append(str(v["t"]))
        if "h" in v:
            parts.append(f'({v["h"]})')
        if "type" in v:
            return f'[{v["type"]}]'
        return " ".join(parts) if parts else "\u00b7"
    if v == "":
        return "\u00b7"
    return str(v)


def render_layer(yaml_file, layer):
    raw = subprocess.run(
        ["yq", f".layers.{layer}", yaml_file],
        capture_output=True,
        text=True,
    ).stdout
    rows = json.loads(raw)

    combo_raw = subprocess.run(
        ["yq", ".combos", yaml_file],
        capture_output=True,
        text=True,
    ).stdout
    combos = (
        json.loads(combo_raw)
        if combo_raw.strip() and combo_raw.strip() != "null"
        else []
    )

    w = max(len(cell(k)) for row in rows for k in row) + 1
    w = max(w, 6)

    bar = "\u2500"
    print(f"\n  {layer}\n  {bar * (w * 6 + 12)}\n")

    for row in rows:
        cells = [cell(k) for k in row]
        if len(cells) == 12:
            left = "  ".join(f"{c:>{w}}" for c in cells[:6])
            right = "  ".join(f"{c:<{w}}" for c in cells[6:])
            print(f"    {left}    {right}")
        elif len(cells) == 6:
            pad = " " * (w * 3 + 6)
            left = "  ".join(f"{c:>{w}}" for c in cells[:3])
            right = "  ".join(f"{c:<{w}}" for c in cells[3:])
            print(f"    {pad}{left}    {right}")

    active_combos = [c for c in combos if "l" not in c or layer in c["l"]]
    if active_combos:
        print(f"\n  {bar * 40}")
        print("  Combos:")
        for c in active_combos:
            positions = ",".join(str(p) for p in c["p"])
            key = c.get("k", "?")
            print(f"    pos [{positions}] \u2192 {key}")

    print()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <keymap.yaml> <LAYER_NAME>", file=sys.stderr)
        sys.exit(1)
    render_layer(sys.argv[1], sys.argv[2])
