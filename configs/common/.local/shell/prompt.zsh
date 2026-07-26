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

# PROMPT and RPROMPT each expand in their own subshell, so loading the git state
# inside them would run git twice per prompt. Load it once here instead; both
# halves below then only read variables.
autoload -Uz add-zsh-hook
__prompt_load_git() {
  prompt_git_load_state && PROMPT_GIT_REPO=1 || PROMPT_GIT_REPO=""
}
add-zsh-hook precmd __prompt_load_git

function git_prompt_info() {
  [[ -n "$PROMPT_GIT_REPO" ]] || return

  local git_status=""

  if [[ "$PROMPT_GIT_FLAGS" == "clean" ]]; then
    git_status="%F{green}${PROMPT_ICON_CLEAN}%f "
  else
    [[ "$PROMPT_GIT_FLAGS" == *untracked* ]] && git_status+="%F{red}${PROMPT_ICON_UNTRACKED}%f "
    [[ "$PROMPT_GIT_FLAGS" == *staged* ]] && git_status+="%F{green}${PROMPT_ICON_ADDED}%f "
    [[ "$PROMPT_GIT_FLAGS" == *modified* ]] && git_status+="%F{yellow}${PROMPT_ICON_MODIFIED}%f "
    [[ "$PROMPT_GIT_FLAGS" == *deleted* ]] && git_status+="%F{red}${PROMPT_ICON_DELETED}%f "
    [[ "$PROMPT_GIT_FLAGS" == *renamed* ]] && git_status+="%F{magenta}${PROMPT_ICON_RENAMED}%f "
    [[ "$PROMPT_GIT_FLAGS" == *unmerged* ]] && git_status+="%F{red}${PROMPT_ICON_UNMERGED}%f "
  fi

  (( PROMPT_GIT_STASH > 0 )) && git_status+="%F{blue}${PROMPT_ICON_STASH}%f "

  echo "%F{green}${PROMPT_ICON_BRANCH} ${PROMPT_GIT_BRANCH}%f ${git_status}"
}

function git_remote_status() {
  [[ -n "$PROMPT_GIT_REPO" ]] || return

  local remote_status=""
  (( PROMPT_GIT_AHEAD != 0 )) && remote_status+="%F{green}${PROMPT_ICON_UP} ${PROMPT_GIT_AHEAD}%f  "
  (( PROMPT_GIT_BEHIND != 0 )) && remote_status+="%F{red}${PROMPT_ICON_DOWN} ${PROMPT_GIT_BEHIND}%f"

  echo "$remote_status"
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
# TERMINAL TITLE (OSC 2)
# ================================================================
# Report "host:cwd" as the terminal title on every prompt. tmux tracks this as
# the pane title, so a pane running ssh into a dotfiles box shows the remote host
# and directory in its border (see the theme's pane-border-format). On ssh launch
# the local shell labels the pane "ssh: <target>", so a bare remote that can't set
# its own title still reads honestly instead of a stale local directory.

__title_host_cwd() {
  local dir=${PWD/#$HOME/\~}
  printf '\033]2;%s:%s\033\\' "${HOST%%.*}" "$dir"
}

__title_ssh_target() {
  # $1 is the command line about to run; label ssh sessions with their target
  if [[ "$1" == ssh\ * ]]; then
    printf '\033]2;ssh: %s\033\\' "${1#ssh }"
  fi
}

add-zsh-hook precmd __title_host_cwd
add-zsh-hook chpwd __title_host_cwd
add-zsh-hook preexec __title_ssh_target

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
