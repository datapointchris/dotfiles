#!/usr/bin/env bash
# Generate VS Code theme config from theme.yml
# Usage: vscode.sh <theme.yml> [output-file]
#
# Reads meta.vscode_extension and meta.vscode_name from theme.yml.
# Skips generation if vscode_extension is not specified.

set -euo pipefail



if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <theme.yml> [output-file]"
  exit 1
fi

input_file="$1"
output_file="${2:-}"

extension=$(yq -r '.meta.vscode_extension // ""' "$input_file")
name=$(yq -r '.meta.vscode_name // .meta.display_name' "$input_file")

if [[ -z "$extension" ]]; then
  echo "Skipping: meta.vscode_extension not specified in $input_file" >&2
  exit 0
fi

generate() {
  cat << EOF
{
  "name": "${name}",
  "extension": "${extension}"
}
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
