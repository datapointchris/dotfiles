# shellcheck shell=bash
# shellcheck disable=SC1091

export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"
export XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
export XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
export XDG_BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"

export SHELL_DIR="$HOME/.local/shell"
export EDITOR="nvim"

[[ -f "$HOME/.env" ]] && source "$HOME/.env"

# Prepended onto the PATH this shell was handed, and only where it does not
# already carry the directory.
#
# The first line here used to assign PATH the five Unix system directories
# outright. That reset was doing real work — it is what kept the unconditional
# prepends under it from accumulating across nested login shells — and it could
# afford to throw away what it was handed only because on Unix that was the same
# five directories. Git Bash reads this file for every login shell, and there the
# inherited PATH is the only copy of System32, the winget shim directory, and
# everything else Windows assembles from the registry.
#
# Appending `:$PATH` to the reset would save those and hand the accumulation
# back. A membership test keeps both: nothing is discarded, and running this file
# a second time changes nothing. It also leaves one file rather than a copy per
# os value — configs/ deploys whole files and merges nothing, so moving a single
# line onto the os axis means three .bash_profiles, two of them identical.
for path_directory in /sbin /usr/sbin /bin /usr/bin /usr/local/bin "$HOME/.local/bin" "$HOME/bin" "$HOME/go/bin"; do
  if [[ -d "$path_directory" && ":$PATH:" != *":$path_directory:"* ]]; then
    # The separator is conditional because an empty PATH would otherwise gain a
    # trailing colon, and an empty PATH entry means the current directory.
    PATH="$path_directory${PATH:+:$PATH}"
  fi
done
unset path_directory
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
