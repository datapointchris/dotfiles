#!/usr/bin/env bash
set -euo pipefail

# ================================================================
# Shell Build Script
# ================================================================
# Reads a machine manifest and concatenates shell group files
# into single functions.sh and aliases.sh output files.
#
# Usage:
#   build-shell.sh <manifest-file> [output-dir]
#
# The manifest YAML is parsed with a simple grep/sed approach
# to avoid requiring Python/yq at shell build time.
# ================================================================

DOTFILES_DIR="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
SHELL_SRC="$DOTFILES_DIR/management/shell"
DEFAULT_OUTPUT_DIR="$HOME/.local/shell"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

usage() {
  echo "Usage: $(basename "$0") <manifest-file> [output-dir]"
  echo ""
  echo "Build shell functions.sh and aliases.sh from manifest groups."
  echo ""
  echo "Arguments:"
  echo "  manifest-file   Path to machine manifest YAML"
  echo "  output-dir      Output directory (default: $DEFAULT_OUTPUT_DIR)"
  echo ""
  echo "Examples:"
  echo "  $(basename "$0") management/machines/arch-personal-workstation.yml"
  echo "  $(basename "$0") management/machines/ubuntu-lxc-server.yml /tmp/shell-test"
  exit 0
}

# Parse a YAML list field from manifest
# Handles both inline [a, b, c] and multi-line - a formats
parse_yaml_list() {
  local file="$1"
  local field="$2"

  # Try inline format first: field: [a, b, c]
  local inline
  inline=$(grep "^${field}:" "$file" | sed -n 's/.*\[\(.*\)\].*/\1/p')
  if [[ -n "$inline" ]]; then
    echo "$inline" | tr ',' '\n' | sed 's/^ *//;s/ *$//' | grep -v '^$'
    return
  fi

  # Multi-line format:
  # field:
  #   - a
  #   - b
  local in_field=false
  while IFS= read -r line; do
    if [[ "$line" =~ ^${field}: ]]; then
      in_field=true
      continue
    fi
    if $in_field; then
      if [[ "$line" =~ ^[[:space:]]*-[[:space:]]+(.*) ]]; then
        echo "${BASH_REMATCH[1]}"
      elif [[ "$line" =~ ^[a-z_] ]]; then
        # Hit next top-level field
        break
      fi
    fi
  done < "$file"
}

# Parse a scalar field from manifest
parse_yaml_scalar() {
  local file="$1"
  local field="$2"

  grep "^${field}:" "$file" | sed 's/^[^:]*:[[:space:]]*//' | sed 's/[[:space:]]*$//'
}

# Uppercase first letter of a string
ucfirst() {
  local str="$1"
  echo "${str^}"
}

# Concatenate group files with section headers
concat_groups() {
  local src_dir="$1"
  local output_file="$2"
  shift 2
  local groups=("$@")

  # Start with empty file
  : > "$output_file"

  for group in "${groups[@]}"; do
    local src_file="$src_dir/${group}.sh"
    if [[ ! -f "$src_file" ]]; then
      log_warning "Group file not found: $src_file"
      continue
    fi

    local header
    header=$(ucfirst "$group" | tr '-' ' ')

    {
      cat <<EOF

# ================================================================
# $(echo "$header" | tr '[:lower:]' '[:upper:]')
# ================================================================

EOF
      cat "$src_file"
      echo ""
    } >> "$output_file"
  done
}

main() {
  if [[ $# -lt 1 ]] || [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    usage
  fi

  local manifest="$1"
  local output_dir="${2:-$DEFAULT_OUTPUT_DIR}"

  if [[ ! -f "$manifest" ]]; then
    # Try relative to dotfiles dir
    manifest="$DOTFILES_DIR/$manifest"
    if [[ ! -f "$manifest" ]]; then
      log_fatal "Manifest file not found: $1"
    fi
  fi

  # Parse manifest
  local platform
  platform=$(parse_yaml_scalar "$manifest" "platform")
  if [[ -z "$platform" ]]; then
    log_fatal "No 'platform' field found in manifest"
  fi

  # Parse function groups
  local function_groups=()
  while IFS= read -r group; do
    [[ -n "$group" ]] && function_groups+=("$group")
  done < <(parse_yaml_list "$manifest" "function_groups")

  # Parse alias groups
  local alias_groups=()
  while IFS= read -r group; do
    [[ -n "$group" ]] && alias_groups+=("$group")
  done < <(parse_yaml_list "$manifest" "alias_groups")

  # Ensure output directory exists
  mkdir -p "$output_dir"

  local func_output="$output_dir/functions.sh"
  local alias_output="$output_dir/aliases.sh"

  log_info "Building shell files from manifest: $(basename "$manifest")"
  log_info "Platform: $platform"
  log_info "Function groups: ${function_groups[*]}"
  log_info "Alias groups: ${alias_groups[*]}"
  log_info "Output: $output_dir"

  # Build functions.sh
  # Add specified groups, then auto-add platform group
  local all_func_groups=("${function_groups[@]}" "platform-${platform}")
  concat_groups "$SHELL_SRC/functions" "$func_output" "${all_func_groups[@]}"
  log_success "Generated: functions.sh ($(wc -l < "$func_output") lines)"

  # Build aliases.sh
  # Add specified groups, then auto-add platform group
  local all_alias_groups=("${alias_groups[@]}" "platform-${platform}")
  concat_groups "$SHELL_SRC/aliases" "$alias_output" "${all_alias_groups[@]}"
  log_success "Generated: aliases.sh ($(wc -l < "$alias_output") lines)"

  log_success "Shell build complete"
}

main "$@"
