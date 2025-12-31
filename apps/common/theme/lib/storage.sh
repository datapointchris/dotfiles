#!/usr/bin/env bash
# Theme storage layer - JSONL-based tracking
# Per-platform history files to avoid git merge conflicts

# Data directory - stored with app (git-tracked, not runtime data)
# THEME_APP_DIR is set by the main script before sourcing this library
THEME_DATA_DIR="${THEME_APP_DIR}/data"

#==============================================================================
# PLATFORM DETECTION
#==============================================================================

detect_platform() {
  if [[ -n "${PLATFORM:-}" ]]; then
    echo "$PLATFORM"
    return
  fi

  if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macos"
  elif [[ -f /proc/version ]] && grep -qi microsoft /proc/version; then
    echo "wsl"
  elif [[ -f /etc/arch-release ]]; then
    echo "arch"
  elif [[ -f /etc/os-release ]]; then
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
  local theme="${2:-}"
  local message="${3:-}"

  if [[ -z "$action" ]]; then
    echo "Error: action required" >&2
    return 1
  fi

  local platform
  platform=$(detect_platform)
  local timestamp
  timestamp=$(date -u -Iseconds 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)

  local history_file="$THEME_DATA_DIR/history-${platform}.jsonl"
  mkdir -p "$THEME_DATA_DIR"

  local record
  if [[ -n "$message" ]]; then
    record=$(jq -nc \
      --arg ts "$timestamp" \
      --arg plat "$platform" \
      --arg theme "$theme" \
      --arg act "$action" \
      --arg msg "$message" \
      '{ts:$ts, platform:$plat, theme:$theme, action:$act, message:$msg}')
  else
    record=$(jq -nc \
      --arg ts "$timestamp" \
      --arg plat "$platform" \
      --arg theme "$theme" \
      --arg act "$action" \
      '{ts:$ts, platform:$plat, theme:$theme, action:$act}')
  fi

  echo "$record" >> "$history_file"
}

get_history() {
  if compgen -G "$THEME_DATA_DIR/history-*.jsonl" > /dev/null; then
    cat "$THEME_DATA_DIR"/history-*.jsonl 2>/dev/null | jq -s 'sort_by(.ts)'
  else
    echo "[]"
  fi
}

get_history_raw() {
  if compgen -G "$THEME_DATA_DIR/history-*.jsonl" > /dev/null; then
    cat "$THEME_DATA_DIR"/history-*.jsonl 2>/dev/null | jq -c '.' | sort
  fi
}

#==============================================================================
# QUERY FUNCTIONS
#==============================================================================

get_theme_stats() {
  local theme="$1"

  if [[ -z "$theme" ]]; then
    echo "Error: theme name required" >&2
    return 1
  fi

  get_history | jq --arg theme "$theme" '
    map(select(.theme == $theme)) |
    {
      theme: $theme,
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

calculate_usage_time() {
  local current_theme="$1"

  get_history | jq -r --arg current "$current_theme" '
    def parse_ts:
      if test("[+-][0-9]{2}:[0-9]{2}$") then
        gsub("[+-][0-9]{2}:[0-9]{2}$"; "Z") | fromdateiso8601
      else
        fromdateiso8601
      end;

    [map(select(.action == "apply")) | sort_by(.ts) | to_entries[]] as $applies |

    ($applies | map(
      . as $entry |
      $entry.key as $idx |
      $entry.value as $apply |

      if ($idx < (($applies | length) - 1)) then
        {
          theme: $apply.theme,
          duration: (($applies[$idx + 1].value.ts | parse_ts) - ($apply.ts | parse_ts))
        }
      elif $apply.theme == $current then
        {
          theme: $apply.theme,
          duration: ((now | floor) - ($apply.ts | parse_ts))
        }
      else
        null
      end
    ) | map(select(. != null))) as $durations |

    ($durations | group_by(.theme) | map({
      key: .[0].theme,
      value: (map(.duration) | add // 0)
    }) | from_entries)
  '
}

get_rankings() {
  local current_theme
  current_theme=$(get_current_theme 2>/dev/null || echo "")

  local usage_times
  usage_times=$(calculate_usage_time "$current_theme")

  get_history | jq -c --argjson usage "$usage_times" '
    group_by(.theme) |
    map({
      theme: .[0].theme,
      likes: map(select(.action == "like")) | length,
      dislikes: map(select(.action == "dislike")) | length,
      score: (map(select(.action == "like")) | length) - (map(select(.action == "dislike")) | length),
      last_used: (map(select(.action == "apply")) | max_by(.ts) | .ts // "never"),
      platforms: [.[].platform] | unique | join(","),
      usage_seconds: ($usage[.[0].theme] // 0),
      sort_key: (if (map(select(.action == "apply")) | length) > 0 then (map(select(.action == "apply")) | max_by(.ts) | .ts) else "0" end)
    }) |
    sort_by(.score, .sort_key) | reverse |
    .[]
  '
}

#==============================================================================
# FILTER FUNCTIONS
#==============================================================================

filter_by_theme() {
  local theme="$1"
  get_history | jq --arg theme "$theme" 'map(select(.theme == $theme))'
}

filter_by_action() {
  local action="$1"
  get_history | jq --arg action "$action" 'map(select(.action == $action))'
}

filter_by_platform() {
  local platform="$1"
  get_history | jq --arg platform "$platform" 'map(select(.platform == $platform))'
}

#==============================================================================
# ANALYSIS FUNCTIONS
#==============================================================================

get_most_liked_themes() {
  local limit="${1:-10}"

  get_history | jq --arg limit "$limit" '
    group_by(.theme) |
    map({
      theme: .[0].theme,
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
    unique_by(.theme) |
    limit($limit | tonumber; .[])
  '
}

get_theme_notes() {
  local theme="$1"

  get_history | jq --arg theme "$theme" '
    map(select(.theme == $theme and .action == "note")) |
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

count_themes_tracked() {
  get_history | jq 'group_by(.theme) | length'
}

list_tracked_themes() {
  get_history | jq -r 'group_by(.theme) | .[].theme' | sort -u
}

#==============================================================================
# VALIDATION
#==============================================================================

validate_history_files() {
  local valid=true

  for file in "$THEME_DATA_DIR"/history-*.jsonl; do
    [[ -f "$file" ]] || continue

    if ! jq -e '.' "$file" >/dev/null 2>&1; then
      echo "Invalid JSON in: $file" >&2
      valid=false
    fi
  done

  $valid
}

#==============================================================================
# REJECTED THEMES TRACKING
#==============================================================================

REJECTED_THEMES_FILE="$THEME_DATA_DIR/rejected-themes.json"

reject_theme() {
  local theme="$1"
  local reason="${2:-No reason provided}"

  if [[ -z "$theme" ]]; then
    echo "Error: theme name required" >&2
    return 1
  fi

  local platform
  platform=$(detect_platform)
  local timestamp
  timestamp=$(date -u -Iseconds 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)

  if [[ ! -f "$REJECTED_THEMES_FILE" ]]; then
    echo "{}" > "$REJECTED_THEMES_FILE"
  fi

  local temp_file="${REJECTED_THEMES_FILE}.tmp"
  jq --arg theme "$theme" \
     --arg reason "$reason" \
     --arg platform "$platform" \
     --arg ts "$timestamp" \
     '.[$theme] = {
       "rejected_date": $ts,
       "reason": $reason,
       "platforms": ((.[$theme].platforms // []) + [$platform] | unique)
     }' "$REJECTED_THEMES_FILE" > "$temp_file"

  mv "$temp_file" "$REJECTED_THEMES_FILE"
}

is_theme_rejected() {
  local theme="$1"

  if [[ ! -f "$REJECTED_THEMES_FILE" ]]; then
    return 1
  fi

  jq -e --arg theme "$theme" '.[$theme] != null' "$REJECTED_THEMES_FILE" >/dev/null 2>&1
}

get_rejected_theme_info() {
  local theme="$1"

  if [[ ! -f "$REJECTED_THEMES_FILE" ]]; then
    echo "{}"
    return
  fi

  jq --arg theme "$theme" '.[$theme] // {}' "$REJECTED_THEMES_FILE"
}

list_rejected_themes() {
  if [[ ! -f "$REJECTED_THEMES_FILE" ]]; then
    echo "[]"
    return
  fi

  jq -c 'to_entries | map({theme: .key, rejected_date: .value.rejected_date, reason: .value.reason, platforms: .value.platforms | join(",")}) | sort_by(.rejected_date) | reverse | .[]' "$REJECTED_THEMES_FILE"
}

unreject_theme() {
  local theme="$1"

  if [[ -z "$theme" ]]; then
    echo "Error: theme name required" >&2
    return 1
  fi

  if [[ ! -f "$REJECTED_THEMES_FILE" ]]; then
    return 0
  fi

  local temp_file="${REJECTED_THEMES_FILE}.tmp"
  jq --arg theme "$theme" 'del(.[$theme])' "$REJECTED_THEMES_FILE" > "$temp_file"
  mv "$temp_file" "$REJECTED_THEMES_FILE"
}

#==============================================================================
# INITIALIZATION
#==============================================================================

init_storage() {
  if [[ ! -d "$THEME_DATA_DIR" ]]; then
    mkdir -p "$THEME_DATA_DIR"
  fi

  local platform
  platform=$(detect_platform)
  local history_file="$THEME_DATA_DIR/history-${platform}.jsonl"

  if [[ ! -f "$history_file" ]]; then
    touch "$history_file"
  fi

  if [[ ! -f "$REJECTED_THEMES_FILE" ]]; then
    echo "{}" > "$REJECTED_THEMES_FILE"
  fi
}

init_storage
