# shellcheck shell=bash
# shellcheck disable=SC1091

export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"
export XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
export XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
export XDG_BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"

export SHELL_DIR="$HOME/.local/shell"
export EDITOR="nvim"

PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
[[ -d "$HOME/.local/bin" ]] && PATH="$HOME/.local/bin:$PATH"
[[ -d "$HOME/bin" ]] && PATH="$HOME/bin:$PATH"
[[ -d "$HOME/go/bin" ]] && PATH="$HOME/go/bin:$PATH"
export PATH

HISTSIZE=10000
HISTFILESIZE=20000
HISTCONTROL=ignoreboth:erasedups

shopt -s nocaseglob
shopt -s histappend
shopt -s cdspell
shopt -s autocd 2>/dev/null
shopt -s globstar 2>/dev/null

if command -v brew &>/dev/null; then
  BREW_PREFIX="$(brew --prefix)"
  if [[ -r "$BREW_PREFIX/etc/profile.d/bash_completion.sh" ]]; then
    export BASH_COMPLETION_COMPAT_DIR="$BREW_PREFIX/etc/bash_completion.d"
    source "$BREW_PREFIX/etc/profile.d/bash_completion.sh"
  fi
elif [[ -f /etc/bash_completion ]]; then
  source /etc/bash_completion
fi

if type _git &>/dev/null; then
  complete -o default -o nospace -F _git g
fi

[[ -e "$HOME/.ssh/config" ]] && complete -o default -o nospace -W "$(grep "^Host" ~/.ssh/config | grep -v "[?*]" | cut -d " " -f2- | tr ' ' '\n')" scp sftp ssh

[[ -f "$HOME/.bashrc" ]] && source "$HOME/.bashrc"
