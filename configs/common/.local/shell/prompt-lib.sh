# shellcheck shell=bash
# ================================================================
# Shared Prompt Library
# ================================================================
# Common utilities for bash and zsh prompts.
# Sourced by prompt.bash and prompt.zsh
# ================================================================

# ================================================================
# NERD FONT ICONS
# ================================================================
# Export as variables for use in prompt scripts

# shellcheck disable=SC2034
PROMPT_ICON_BRANCH=$'\ue0a0'      # git branch
PROMPT_ICON_UNTRACKED="󱀶"         # question file
PROMPT_ICON_ADDED=$'\uf067'       # plus
PROMPT_ICON_MODIFIED=$'\uf459'    # modified file
PROMPT_ICON_DELETED=$'\uf068'     # minus
PROMPT_ICON_RENAMED=$'\uf061'     # arrow right
PROMPT_ICON_UNMERGED=$'\uf071'    # warning triangle
PROMPT_ICON_CLEAN=$'\uf00c'       # check mark
PROMPT_ICON_STASH=$'\uf01c'       # inbox/stash
PROMPT_ICON_UP=$'\uf062'          # up arrow
PROMPT_ICON_DOWN=$'\uf063'        # down arrow
PROMPT_ICON_CARET=$'\u276f'       # ❯ symbol

# ================================================================
# GIT UTILITIES
# ================================================================

# Check if current directory is in a git repo
prompt_in_git_repo() {
  git rev-parse --git-dir >/dev/null 2>&1
}

# Get current branch name (or short SHA if detached)
prompt_git_branch() {
  git symbolic-ref --short HEAD 2>/dev/null || git rev-parse --short HEAD 2>/dev/null
}

# Check if repo has stashed changes
prompt_git_has_stash() {
  git stash list 2>/dev/null | grep -q "stash@"
}

# Get git status flags (returns space-separated words)
# Possible values: clean, untracked, staged, modified, deleted, renamed, unmerged
# Uses while loop instead of grep pipes for performance (critical on Windows/VPN)
prompt_git_status_flags() {
  local out
  out=$(git status --porcelain 2>/dev/null)

  if [[ -z "$out" ]]; then
    echo "clean"
    return
  fi

  local flags="" code
  local has_untracked="" has_staged="" has_modified="" has_deleted="" has_renamed="" has_unmerged=""

  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    code="${line:0:2}"
    case "$code" in
      "??") has_untracked=1 ;;
      "A "|"A"?) has_staged=1 ;;
      "M "|" M"|"MM") has_modified=1 ;;
      "D "|" D") has_deleted=1 ;;
      "R ") has_renamed=1 ;;
      "UU") has_unmerged=1 ;;
    esac
  done <<< "$out"

  [[ $has_untracked ]] && flags+="untracked "
  [[ $has_staged ]] && flags+="staged "
  [[ $has_modified ]] && flags+="modified "
  [[ $has_deleted ]] && flags+="deleted "
  [[ $has_renamed ]] && flags+="renamed "
  [[ $has_unmerged ]] && flags+="unmerged "
  echo "$flags"
}

# Get ahead/behind counts relative to upstream
# Returns: "behind ahead" (tab-separated) or empty if no upstream
prompt_git_ahead_behind() {
  local upstream
  upstream=$(git rev-parse --abbrev-ref '@{upstream}' 2>/dev/null)
  [[ -z "$upstream" ]] && return

  git rev-list --count --left-right '@{upstream}...HEAD' 2>/dev/null
}

# ================================================================
# DIRECTORY UTILITIES
# ================================================================

# Truncate directory path (default 45 chars, first 2/.../last 2)
prompt_truncate_dir() {
  local max_length="${1:-45}"
  local pwd_display="${PWD/#$HOME/\~}"

  if [[ ${#pwd_display} -gt $max_length ]]; then
    local first last_dirs
    first=$(echo "$pwd_display" | cut -d'/' -f1-2)
    last_dirs=$(echo "$pwd_display" | rev | cut -d'/' -f1-2 | rev)
    pwd_display="${first}/.../${last_dirs}"
  fi

  echo "$pwd_display"
}

# ================================================================
# USER CONTEXT
# ================================================================

# Determine user context for prompt coloring
# Returns: "local", "ssh", "root", or "root-ssh"
prompt_user_context() {
  if [[ -n "$SSH_CONNECTION" ]]; then
    if [[ "$USER" == "root" ]]; then
      echo "root-ssh"
    else
      echo "ssh"
    fi
  elif [[ "$USER" == "root" ]]; then
    echo "root"
  else
    echo "local"
  fi
}

# ================================================================
# VIRTUALENV
# ================================================================

# Get virtualenv name (basename only)
prompt_venv_name() {
  if [[ -n "$VIRTUAL_ENV" ]]; then
    basename "$VIRTUAL_ENV"
  fi
}
