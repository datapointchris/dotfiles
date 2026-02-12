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
prompt_git_status_flags() {
  local out
  out=$(git status --porcelain 2>/dev/null)

  if [[ -z "$out" ]]; then
    echo "clean"
    return
  fi

  local flags=""
  echo "$out" | grep -q "^??" && flags+="untracked "
  echo "$out" | grep -q "^A" && flags+="staged "
  echo "$out" | grep -qE "^M|^ M" && flags+="modified "
  echo "$out" | grep -qE "^D|^ D" && flags+="deleted "
  echo "$out" | grep -q "^R" && flags+="renamed "
  echo "$out" | grep -q "^UU" && flags+="unmerged "
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
