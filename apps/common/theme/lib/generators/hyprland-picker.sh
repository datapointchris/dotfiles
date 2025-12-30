#!/usr/bin/env bash
# Generate Hyprland preview share picker CSS from theme.yml
# Usage: hyprland-picker.sh <theme.yml> [output-file]
#
# Generates CSS for hyprland-preview-share-picker dialog.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../theme.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <theme.yml> [output-file]"
  exit 1
fi

input_file="$1"
output_file="${2:-}"

eval "$(load_colors "$input_file")"

generate() {
  cat << EOF
@define-color foreground ${SPECIAL_FG};
@define-color background ${SPECIAL_BG};
@define-color accent ${BASE09};
@define-color muted ${BASE03};
@define-color card_bg ${BASE01};
@define-color text_dark ${SPECIAL_BG};
@define-color accent_hover ${BASE0A};
@define-color selected_tab ${BASE09};
@define-color text ${SPECIAL_FG};

* {
  all: unset;
  font-family: JetBrains Mono NF;
  color: @foreground;
  font-weight: bold;
  font-size: 16px;
}

.window {
  background: alpha(@background, 0.95);
  border: solid 2px @accent;
  margin: 4px;
  padding: 18px;
}

tabs {
    padding: 0.5rem 1rem;
}

tabs > tab {
    margin-right: 1rem;
}

.tab-label {
    color: @text;
    transition: all 0.2s ease;
}

tabs > tab:checked > .tab-label, tabs > tab:active > .tab-label {
    text-decoration: underline currentColor;
    color: @selected_tab;
}

tabs > tab:focus > .tab-label {
    color: @foreground;
}

.page {
    padding: 1rem;
}

.image-label {
    font-size: 12px;
    padding: 0.25rem;
}

flowboxchild > .card, button > .card {
    transition: all 0.2s ease;
    border: solid 2px transparent;
    border-color: @background;
    border-radius: 5px;
    background-color: @card_bg;
    padding: 5px;
}

flowboxchild:hover > .card, button:hover > .card, flowboxchild:active > .card, flowboxchild:selected > .card, button:active > .card, button:selected > .card, button:focus > .card {
    border: solid 2px @accent;
}

.image {
    border-radius: 5px;
}

.region-button {
    padding: 0.5rem 1rem;
    border-radius: 5px;
    background-color: @accent;
    color: @text_dark;
    transition: all 0.2s ease;
}

.region-button > label {
    color: @text_dark;
}

.region-button:not(:disabled):hover, .region-button:not(:disabled):focus {
    background-color: @accent_hover;
    color: @text_dark;
}

.region-button:disabled {
    background-color: @muted;
    color: @background;
}
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
