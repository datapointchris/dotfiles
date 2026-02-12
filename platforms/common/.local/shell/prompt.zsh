#shellcheck disable=all
# ================================================================
# ZSH PROMPT CONFIGURATION
# ================================================================
# Uses shared utilities from prompt-lib.sh
# ================================================================

# Enable parameter expansion, command substitution and arithmetic expansion in prompts
setopt PROMPT_SUBST

# Source shared prompt utilities
SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
if [[ -f "$SHELL_DIR/prompt-lib.sh" ]]; then
  source "$SHELL_DIR/prompt-lib.sh"
fi

# Disable virtualenv prompt modification (handled in custom prompt)
export VIRTUAL_ENV_DISABLE_PROMPT=1

# ================================================================
# PROMPT COMPONENT FUNCTIONS
# ================================================================

function current_venv() {
  local venv_name
  venv_name=$(prompt_venv_name)
  if [[ -n "$venv_name" ]]; then
    echo "%F{yellow}($venv_name)%f"
  fi
}

function user_info() {
  local context
  context=$(prompt_user_context)

  case "$context" in
    root|root-ssh) echo "%F{red}$USER@%m%f:" ;;
    ssh)           echo "%F{cyan}$USER@%m%f:" ;;
    *)             ;; # Hide user@host for local sessions
  esac
}

function current_dir() {
  local _max_pwd_length="45"
  if [[ ${#PWD} -gt ${_max_pwd_length} ]]; then
    echo "%B%F{white}%-2~ ... %2~%f%b"
  else
    echo "%B%F{white}%~%f%b"
  fi
}

function git_prompt_info() {
  if ! prompt_in_git_repo; then
    return
  fi

  local branch_name git_status status_flags

  branch_name=$(prompt_git_branch)
  status_flags=$(prompt_git_status_flags)

  git_status=""

  if [[ "$status_flags" == "clean" ]]; then
    git_status="%F{green}${PROMPT_ICON_CLEAN}%f "
  else
    [[ "$status_flags" == *untracked* ]] && git_status+="%F{red}${PROMPT_ICON_UNTRACKED}%f "
    [[ "$status_flags" == *staged* ]] && git_status+="%F{green}${PROMPT_ICON_ADDED}%f "
    [[ "$status_flags" == *modified* ]] && git_status+="%F{yellow}${PROMPT_ICON_MODIFIED}%f "
    [[ "$status_flags" == *deleted* ]] && git_status+="%F{red}${PROMPT_ICON_DELETED}%f "
    [[ "$status_flags" == *renamed* ]] && git_status+="%F{magenta}${PROMPT_ICON_RENAMED}%f "
    [[ "$status_flags" == *unmerged* ]] && git_status+="%F{red}${PROMPT_ICON_UNMERGED}%f "
  fi

  # Check for stashes
  if prompt_git_has_stash; then
    git_status+="%F{blue}${PROMPT_ICON_STASH}%f "
  fi

  echo "%F{green}${PROMPT_ICON_BRANCH} ${branch_name}%f ${git_status}"
}

function git_remote_status() {
  if ! prompt_in_git_repo; then
    return
  fi

  local ahead_behind behind ahead remote_status
  ahead_behind=$(prompt_git_ahead_behind)

  if [[ -n "$ahead_behind" ]]; then
    behind=$(echo "$ahead_behind" | cut -f1)
    ahead=$(echo "$ahead_behind" | cut -f2)

    remote_status=""
    [[ "$ahead" != "0" ]] && remote_status+="%F{green}${PROMPT_ICON_UP} ${ahead}%f  "
    [[ "$behind" != "0" ]] && remote_status+="%F{red}${PROMPT_ICON_DOWN} ${behind}%f"

    echo "$remote_status"
  fi
}

function current_caret() {
  if [[ "$USER" == "root" ]]; then
    echo "%F{red}# %f"
  else
    echo "%F{green}${PROMPT_ICON_CARET} %f"
  fi
}

function return_status() {
  echo "%(?..%F{red}%? ⚠️ %f)"
}

# ================================================================
# PROMPT CONFIGURATION
# ================================================================

PROMPT='
$(current_venv) $(user_info)$(current_dir)  $(git_prompt_info)
$(current_caret)'
PROMPT2='. '
RPROMPT='%{$(echotc UP 1)%} $(git_remote_status)   $(return_status)   %{$(echotc DO 1)%}'

# ================================================================
# COLOR CONFIGURATION
# ================================================================

# LS Colors - Made with: http://geoff.greer.fm/lscolors/
export LSCOLORS="gxfxcxdxbxegedabagacad"
export LS_COLORS="di=36:ln=35:so=32:pi=33:ex=31:bd=34;46:cd=34;43:su=30;41:sg=30;46:tw=30;42:ow=30;43"
export CLICOLOR=1

# GREP Colors
export GREP_COLORS='mt40;93'

# Internal zsh styles: completions, suggestions, etc
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"
zstyle ':completion:*:descriptions' format "%B--- %d%b"
