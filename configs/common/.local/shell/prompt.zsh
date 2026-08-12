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
#
# Every segment is *assigned to a variable*, never printed from inside PROMPT.
#
# A `$(...)` in a prompt is a forked subshell on every redraw, and this prompt
# had nine of them — five in PROMPT, four in RPROMPT — on top of the one `git`
# call. Eight of the nine were computing something that had not changed: the
# caret depends on $USER, the user@host segment on $SSH_CONNECTION, the two
# echotc sequences on the terminal, and the exit-status segment was a subshell
# wrapped around a `%(?..)` that zsh expands by itself. A fork is cheap on Arch
# and is not cheap on WSL, where this was measured as a prompt that lagged.
#
# What is left is one `git status` per prompt, in precmd, where it was already.

# Constant for the life of the shell, so they are computed once here rather than
# per keystroke. `%m` and `%F` stay unexpanded — they are prompt escapes, which
# zsh expands at render time whatever built the string.
case "$(prompt_user_context)" in
  root|root-ssh) PROMPT_USER_SEGMENT="%F{red}$USER@%m%f:" ;;
  ssh)           PROMPT_USER_SEGMENT="%F{cyan}$USER@%m%f:" ;;
  *)             PROMPT_USER_SEGMENT="" ;; # Hide user@host for local sessions
esac

if [[ "$USER" == "root" ]]; then
  PROMPT_CARET_SEGMENT="%F{red}# %f"
else
  PROMPT_CARET_SEGMENT="%F{green}${PROMPT_ICON_CARET} %f"
fi

# The two cursor moves RPROMPT uses to paint itself a line up. Captured once:
# they are a property of the terminal, and re-asking termcap on every redraw was
# two of the nine forks.
PROMPT_CURSOR_UP="$(echotc UP 1)"
PROMPT_CURSOR_DOWN="$(echotc DO 1)"

PROMPT_MAX_PWD_LENGTH=45

autoload -Uz add-zsh-hook

# `${VIRTUAL_ENV:t}` rather than `basename`, which was a fork per prompt for a
# string zsh can take the tail of itself.
__prompt_set_venv() {
  if [[ -n "$VIRTUAL_ENV" ]]; then
    PROMPT_VENV_SEGMENT="%F{yellow}(${VIRTUAL_ENV:t})%f"
  else
    PROMPT_VENV_SEGMENT=""
  fi
}

# Which of the two spellings to use is the only thing measured here; both are
# prompt escapes, so zsh still renders the path itself at redraw time and a
# directory whose name contains a `%` or a `$` cannot reach this string.
__prompt_set_dir() {
  if (( ${#PWD} > PROMPT_MAX_PWD_LENGTH )); then
    PROMPT_DIR_SEGMENT="%B%F{white}%-2~ ... %2~%f%b"
  else
    PROMPT_DIR_SEGMENT="%B%F{white}%~%f%b"
  fi
}

__prompt_set_git() {
  PROMPT_GIT_SEGMENT=""
  PROMPT_GIT_REMOTE_SEGMENT=""
  prompt_git_load_state || return 0

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

  PROMPT_GIT_SEGMENT="%F{green}${PROMPT_ICON_BRANCH} ${PROMPT_GIT_BRANCH}%f ${git_status}"

  (( PROMPT_GIT_AHEAD != 0 )) && PROMPT_GIT_REMOTE_SEGMENT+="%F{green}${PROMPT_ICON_UP} ${PROMPT_GIT_AHEAD}%f  "
  (( PROMPT_GIT_BEHIND != 0 )) && PROMPT_GIT_REMOTE_SEGMENT+="%F{red}${PROMPT_ICON_DOWN} ${PROMPT_GIT_BEHIND}%f"
  return 0
}

__prompt_refresh() {
  __prompt_set_venv
  __prompt_set_dir
  __prompt_set_git
}
add-zsh-hook precmd __prompt_refresh

# ================================================================
# PROMPT CONFIGURATION
# ================================================================
#
# PROMPT_SUBST expands these once per redraw. Every `$` below names a variable
# precmd already filled, so nothing here starts a process — and a branch name or
# a directory arriving through a parameter is substituted rather than re-parsed,
# which is the property the `$(...)` version had and this must not lose.
#
# `%(?..)` stays inline: it is zsh's own conditional on the last exit status,
# and it has to be evaluated at render time, after the command whose status it
# reports. It was wrapped in a subshell that did nothing but echo it back.

PROMPT='
${PROMPT_VENV_SEGMENT} ${PROMPT_USER_SEGMENT}${PROMPT_DIR_SEGMENT}  ${PROMPT_GIT_SEGMENT}
${PROMPT_CARET_SEGMENT}'
PROMPT2='. '
RPROMPT='%{${PROMPT_CURSOR_UP}%} ${PROMPT_GIT_REMOTE_SEGMENT}   %(?..%F{red}%? ⚠️ %f)   %{${PROMPT_CURSOR_DOWN}%}'

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
