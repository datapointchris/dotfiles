#!/usr/bin/env bash
# Font storage layer - JSONL-based tracking
# Per-platform history files to avoid git merge conflicts

# Data directory - stored with app (git-tracked, not runtime data)
# FONT_APP_DIR is set by the main script before sourcing this library
FONT_DATA_DIR="${FONT_APP_DIR}/data"

#==============================================================================
# PLATFORM DETECTION
#==============================================================================

detect_platform() {
  # Check for PLATFORM env var first (set by dotfiles)
  if [[ -n "${PLATFORM:-}" ]]; then
    echo "$PLATFORM"
    return
  fi

  # Detect platform
  if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macos"
  elif [[ -f /proc/version ]] && grep -qi microsoft /proc/version; then
    echo "wsl"
  elif [[ -f /etc/arch-release ]]; then
    echo "arch"
  elif [[ -f /etc/os-release ]]; then
    # Generic Linux fallback
    . /etc/os-release
    echo "${ID:-linux}"
  else
    echo "unknown"
  fi
}

#==============================================================================
# CORE STORAGE OPERATIONS
#==============================================================================

log_action() {
  local action="$1"
  local font="${2:-}"
  local message="${3:-}"

  if [[ -z "$action" ]]; then
    echo "Error: action required" >&2
    return 1
  fi

  local platform
  platform=$(detect_platform)
  local timestamp
  timestamp=$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)

  # Per-platform history file - eliminates merge conflicts
  local history_file="$FONT_DATA_DIR/history-${platform}.jsonl"
  mkdir -p "$FONT_DATA_DIR"

  # Build JSON record (compact format for JSONL)
  local record
  if [[ -n "$message" ]]; then
    record=$(jq -nc \
      --arg ts "$timestamp" \
      --arg plat "$platform" \
      --arg font "$font" \
      --arg act "$action" \
      --arg msg "$message" \
      '{ts:$ts, platform:$plat, font:$font, action:$act, message:$msg}')
  else
    record=$(jq -nc \
      --arg ts "$timestamp" \
      --arg plat "$platform" \
      --arg font "$font" \
      --arg act "$action" \
      '{ts:$ts, platform:$plat, font:$font, action:$act}')
  fi

  echo "$record" >> "$history_file"
}

get_history() {
  # Combine all platform history files
  # Returns sorted JSON array
  if compgen -G "$FONT_DATA_DIR/history-*.jsonl" > /dev/null; then
    cat "$FONT_DATA_DIR"/history-*.jsonl 2>/dev/null | jq -s 'sort_by(.ts)'
  else
    echo "[]"
  fi
}

get_history_raw() {
  # Return raw JSONL (one object per line) for streaming
  if compgen -G "$FONT_DATA_DIR/history-*.jsonl" > /dev/null; then
    cat "$FONT_DATA_DIR"/history-*.jsonl 2>/dev/null | jq -c '.' | sort
  fi
}

#==============================================================================
# QUERY FUNCTIONS
#==============================================================================

get_font_stats() {
  local font="$1"

  if [[ -z "$font" ]]; then
    echo "Error: font name required" >&2
    return 1
  fi

  get_history | jq --arg font "$font" '
    map(select(.font == $font)) |
    {
      font: $font,
      total_actions: length,
      likes: map(select(.action == "like")) | length,
      dislikes: map(select(.action == "dislike")) | length,
      notes: map(select(.action == "note")) | length,
      applies: map(select(.action == "apply")) | length,
      score: (map(select(.action == "like")) | length) - (map(select(.action == "dislike")) | length),
      last_used: map(select(.action == "apply")) | max_by(.ts) | .ts // "never",
      platforms: [.[].platform] | unique
    }
  '
}

get_rankings() {
  # Aggregate and rank all fonts by likes/dislikes
  # Returns JSONL (compact JSON, one object per line)
  get_history | jq -c '
    group_by(.font) |
    map({
      font: .[0].font,
      likes: map(select(.action == "like")) | length,
      dislikes: map(select(.action == "dislike")) | length,
      score: (map(select(.action == "like")) | length) - (map(select(.action == "dislike")) | length),
      last_used: (map(select(.action == "apply")) | max_by(.ts) | .ts // "never"),
      platforms: [.[].platform] | unique | join(","),
      # Add sort_key for proper ordering (never gets lowest timestamp)
      sort_key: (if (map(select(.action == "apply")) | length) > 0 then (map(select(.action == "apply")) | max_by(.ts) | .ts) else "0" end)
    }) |
    # Sort by score descending (negate for desc), then by sort_key descending
    sort_by(.score, .sort_key) | reverse |
    .[]
  '
}

#==============================================================================
# FILTER FUNCTIONS
#==============================================================================

filter_by_font() {
  local font="$1"
  get_history | jq --arg font "$font" 'map(select(.font == $font))'
}

filter_by_action() {
  local action="$1"
  get_history | jq --arg action "$action" 'map(select(.action == $action))'
}

filter_by_platform() {
  local platform="$1"
  get_history | jq --arg platform "$platform" 'map(select(.platform == $platform))'
}

filter_by_date_range() {
  local start="$1"
  local end="$2"
  get_history | jq --arg start "$start" --arg end "$end" '
    map(select(.ts >= $start and .ts <= $end))
  '
}

#==============================================================================
# ANALYSIS FUNCTIONS
#==============================================================================

get_most_liked_fonts() {
  local limit="${1:-10}"

  get_history | jq --arg limit "$limit" '
    group_by(.font) |
    map({
      font: .[0].font,
      likes: map(select(.action == "like")) | length
    }) |
    sort_by(-.likes) |
    limit($limit | tonumber; .[])
  '
}

get_recently_used() {
  local limit="${1:-10}"

  get_history | jq --arg limit "$limit" '
    map(select(.action == "apply")) |
    sort_by(-.ts) |
    unique_by(.font) |
    limit($limit | tonumber; .[])
  '
}

get_font_notes() {
  local font="$1"

  get_history | jq --arg font "$font" '
    map(select(.font == $font and .action == "note")) |
    sort_by(.ts) |
    .[]
  '
}

#==============================================================================
# UTILITY FUNCTIONS
#==============================================================================

count_total_actions() {
  get_history | jq 'length'
}

count_fonts_tracked() {
  get_history | jq 'group_by(.font) | length'
}

list_tracked_fonts() {
  get_history | jq -r 'group_by(.font) | .[].font' | sort -u
}

#==============================================================================
# VALIDATION
#==============================================================================

validate_history_files() {
  local valid=true

  for file in "$FONT_DATA_DIR"/history-*.jsonl; do
    [[ -f "$file" ]] || continue

    if ! jq -e '.' "$file" >/dev/null 2>&1; then
      echo "Invalid JSON in: $file" >&2
      valid=false
    fi
  done

  $valid
}

#==============================================================================
# INITIALIZATION
#==============================================================================

init_storage() {
  # Ensure data directory exists
  if [[ ! -d "$FONT_DATA_DIR" ]]; then
    mkdir -p "$FONT_DATA_DIR"
  fi

  # Ensure platform-specific history file exists
  local platform
  platform=$(detect_platform)
  local history_file="$FONT_DATA_DIR/history-${platform}.jsonl"

  if [[ ! -f "$history_file" ]]; then
    touch "$history_file"
  fi
}

# Auto-initialize on source
# This ensures the data directory and current platform's history file exist
# Making the tool robust against deleted log files
init_storage
