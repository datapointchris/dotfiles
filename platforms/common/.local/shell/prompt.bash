# shellcheck shell=bash
# ================================================================
# BASH PROMPT CONFIGURATION
# ================================================================
# Ported from zsh prompt.zsh - feature parity where possible
# Uses shared utilities from prompt-lib.sh
# ================================================================

# Source shared prompt utilities
SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
if [[ -f "$SHELL_DIR/prompt-lib.sh" ]]; then
  # shellcheck source=/dev/null
  source "$SHELL_DIR/prompt-lib.sh"
fi

# Disable virtualenv prompt modification (handled in custom prompt)
export VIRTUAL_ENV_DISABLE_PROMPT=1

# ================================================================
# COLOR SETUP
# ================================================================

# shellcheck disable=SC2034  # Colors defined for consistency, not all used
_bash_prompt_config() {
  local ESC_OPEN="\["
  local ESC_CLOSE="\]"

  if tput setaf >/dev/null 2>&1; then
    _setaf() { tput setaf "$1"; }
    RESET="${ESC_OPEN}$(tput sgr0)${ESC_CLOSE}"
    BOLD="$(tput bold)"
  else
    _setaf() { printf '\033[%sm' "$((30 + $1))"; }
    RESET="${ESC_OPEN}\033[0m${ESC_CLOSE}"
    BOLD="\033[1m"
  fi

  # Standard colors (wrapped for PS1)
  C_RED="${ESC_OPEN}$(_setaf 1)${ESC_CLOSE}"
  C_GREEN="${ESC_OPEN}$(_setaf 2)${ESC_CLOSE}"
  C_YELLOW="${ESC_OPEN}$(_setaf 3)${ESC_CLOSE}"
  C_BLUE="${ESC_OPEN}$(_setaf 4)${ESC_CLOSE}"
  C_MAGENTA="${ESC_OPEN}$(_setaf 5)${ESC_CLOSE}"
  C_CYAN="${ESC_OPEN}$(_setaf 6)${ESC_CLOSE}"
  C_WHITE="${ESC_OPEN}$(_setaf 7)${ESC_CLOSE}"

  # Bold colors
  C_WHITE_BOLD="${ESC_OPEN}${BOLD}$(_setaf 7)${ESC_CLOSE}"

  # Raw colors (not wrapped, for use in variables built during PROMPT_COMMAND)
  RC_RED="\033[31m"
  RC_GREEN="\033[32m"
  RC_YELLOW="\033[33m"
  RC_BLUE="\033[34m"
  RC_MAGENTA="\033[35m"
  RC_CYAN="\033[36m"
  RC_RESET="\033[0m"
}

# ================================================================
# DETECT GIT BASH (Windows)
# ================================================================
# MSYSTEM is set in Git Bash/MSYS2/MinGW environments
_is_git_bash() {
  [[ -n "$MSYSTEM" ]]
}

# ================================================================
# PROMPT COMPONENT FUNCTIONS
# ================================================================

_prompt_venv() {
  local venv_name
  venv_name=$(prompt_venv_name)
  if [[ -n "$venv_name" ]]; then
    printf '%s' "${RC_YELLOW}(${venv_name})${RC_RESET} "
  fi
}

_prompt_user_info() {
  local context
  context=$(prompt_user_context)

  case "$context" in
    root|root-ssh) printf '%s' "${RC_RED}${USER}@${HOSTNAME%%.*}${RC_RESET}:" ;;
    ssh)           printf '%s' "${RC_CYAN}${USER}@${HOSTNAME%%.*}${RC_RESET}:" ;;
    *)             ;; # Hide user@host for local sessions
  esac
}

_prompt_directory() {
  prompt_truncate_dir 45
}

# Fast git info for Git Bash (Windows) - only branch + dirty status
# Optimized to minimize git calls due to Windows process spawn overhead
_prompt_git_info_fast() {
  local branch_name
  branch_name=$(git symbolic-ref --short HEAD 2>/dev/null) || return

  # Check for any changes: tracked (diff-index) or untracked (ls-files)
  local dirty=""
  git diff-index --quiet HEAD -- 2>/dev/null || dirty=1
  if [[ -z "$dirty" ]]; then
    local untracked
    read -r untracked < <(git ls-files --others --exclude-standard 2>/dev/null)
    [[ -n "$untracked" ]] && dirty=1
  fi

  # Color branch: red if dirty, green if clean
  if [[ -n "$dirty" ]]; then
    printf '%s' "${RC_RED}${PROMPT_ICON_BRANCH} ${branch_name}${RC_RESET} "
  else
    printf '%s' "${RC_GREEN}${PROMPT_ICON_BRANCH} ${branch_name}${RC_RESET} "
  fi
}

# Full git info for Linux/macOS - detailed status with icons
_prompt_git_info_full() {
  if ! prompt_in_git_repo; then
    return
  fi

  local branch_name git_status status_flags

  branch_name=$(prompt_git_branch)
  status_flags=$(prompt_git_status_flags)

  git_status=""

  if [[ "$status_flags" == "clean" ]]; then
    git_status="${RC_GREEN}${PROMPT_ICON_CLEAN}${RC_RESET} "
  else
    [[ "$status_flags" == *untracked* ]] && git_status+="${RC_RED}${PROMPT_ICON_UNTRACKED}${RC_RESET} "
    [[ "$status_flags" == *staged* ]] && git_status+="${RC_GREEN}${PROMPT_ICON_ADDED}${RC_RESET} "
    [[ "$status_flags" == *modified* ]] && git_status+="${RC_YELLOW}${PROMPT_ICON_MODIFIED}${RC_RESET} "
    [[ "$status_flags" == *deleted* ]] && git_status+="${RC_RED}${PROMPT_ICON_DELETED}${RC_RESET} "
    [[ "$status_flags" == *renamed* ]] && git_status+="${RC_MAGENTA}${PROMPT_ICON_RENAMED}${RC_RESET} "
    [[ "$status_flags" == *unmerged* ]] && git_status+="${RC_RED}${PROMPT_ICON_UNMERGED}${RC_RESET} "
  fi

  # Check for stashes
  if prompt_git_has_stash; then
    git_status+="${RC_BLUE}${PROMPT_ICON_STASH}${RC_RESET} "
  fi

  printf '%s' "${RC_GREEN}${PROMPT_ICON_BRANCH} ${branch_name}${RC_RESET} ${git_status}"
}

# Wrapper that picks fast or full based on environment
_prompt_git_info() {
  if _is_git_bash; then
    _prompt_git_info_fast
  else
    _prompt_git_info_full
  fi
}

_prompt_git_remote_status() {
  # Skip on Git Bash - too slow due to Windows process overhead
  _is_git_bash && return

  if ! prompt_in_git_repo; then
    return
  fi

  local ahead_behind behind ahead remote_status
  ahead_behind=$(prompt_git_ahead_behind)

  if [[ -n "$ahead_behind" ]]; then
    # Use read to split tab-separated values (avoids pipe overhead)
    IFS=$'\t' read -r behind ahead <<< "$ahead_behind"

    remote_status=""
    [[ "$ahead" != "0" ]] && remote_status+="${RC_GREEN}${PROMPT_ICON_UP}${ahead}${RC_RESET} "
    [[ "$behind" != "0" ]] && remote_status+="${RC_RED}${PROMPT_ICON_DOWN}${behind}${RC_RESET} "

    printf '%s' "$remote_status"
  fi
}

_prompt_caret() {
  if [[ "$USER" == "root" ]]; then
    printf '%s' "${C_RED}# ${RESET}"
  else
    printf '%s' "${C_GREEN}${PROMPT_ICON_CARET} ${RESET}"
  fi
}

# ================================================================
# MAIN PROMPT COMMAND
# ================================================================

# Fast prompt for Git Bash - fully inlined to avoid subshell overhead
# On Windows, each subshell adds ~200-500ms due to process spawn cost
_bash_prompt_command_fast() {
  local exit_code=$?

  # Directory (inline, no subshell)
  local dir="${PWD/#$HOME/\~}"
  if [[ ${#dir} -gt 45 ]]; then
    dir="${dir:0:15}...${dir: -25}"
  fi

  # Git info (inline) - branch colored red if dirty, green if clean
  local git_info=""
  local branch
  if branch=$(git symbolic-ref --short HEAD 2>/dev/null); then
    local dirty=""
    git diff-index --quiet HEAD -- 2>/dev/null || dirty=1
    if [[ -z "$dirty" ]]; then
      local untracked
      read -r untracked < <(git ls-files --others --exclude-standard 2>/dev/null)
      [[ -n "$untracked" ]] && dirty=1
    fi
    if [[ -n "$dirty" ]]; then
      git_info=" \033[31m${PROMPT_ICON_BRANCH} ${branch}\033[0m"
    else
      git_info=" \033[32m${PROMPT_ICON_BRANCH} ${branch}\033[0m"
    fi
  fi

  # Exit status (inline)
  local exit_status=""
  [[ $exit_code -ne 0 ]] && exit_status=" \033[31m${exit_code} ⚠️\033[0m"

  # Update terminal title
  printf '\033]0;%s\007' "$dir"

  # Build prompt: directory git_info exit_status
  PS1="\n\[\033[1;37m\]${dir}\[\033[0m\]${git_info}${exit_status}\n\[\033[32m\]❯\[\033[0m\] "
}

# Full prompt for Linux/macOS - modular with rich git info
_bash_prompt_command_full() {
  local exit_code=$?
  local exit_status=""

  # Exit code indicator (shown at end of first line)
  if [[ $exit_code -ne 0 ]]; then
    exit_status=" ${RC_RED}${exit_code} ⚠️${RC_RESET}"
  fi

  # Update terminal title
  local title_pwd="${PWD/#$HOME/\~}"
  if [[ "$TERM" == xterm* ]] || [[ "$TERM" == screen* ]] || [[ "$TERM" == tmux* ]]; then
    printf '\033]0;%s\007' "$title_pwd"
  fi

  # Build the prompt components
  local venv user_info directory git_info git_remote

  venv="$(_prompt_venv)"
  user_info="$(_prompt_user_info)"
  directory="$(_prompt_directory)"
  git_info="$(_prompt_git_info)"
  git_remote="$(_prompt_git_remote_status)"

  # Two-line prompt matching zsh layout:
  # Line 1: (venv) [user@host:]directory  git_branch git_status  git_remote  exit_status
  # Line 2: ❯
  PS1="\n"
  PS1+="${venv}"
  PS1+="${user_info}"
  PS1+="${C_WHITE_BOLD}${directory}${RESET}"
  PS1+="  ${git_info}"
  PS1+="${git_remote}"
  PS1+="${exit_status}"
  PS1+="\n"
  PS1+="$(_prompt_caret)"
}

# Wrapper that picks fast or full based on environment
_bash_prompt_command() {
  if _is_git_bash; then
    _bash_prompt_command_fast
  else
    _bash_prompt_command_full
  fi
}

# ================================================================
# LS COLORS (matching zsh config)
# ================================================================

export LSCOLORS="gxfxcxdxbxegedabagacad"
export LS_COLORS="di=36:ln=35:so=32:pi=33:ex=31:bd=34;46:cd=34;43:su=30;41:sg=30;46:tw=30;42:ow=30;43"
export CLICOLOR=1

# GREP Colors
export GREP_COLORS='mt=40;93'

# ================================================================
# INITIALIZATION
# ================================================================

_bash_prompt_config

PROMPT_COMMAND=_bash_prompt_command
