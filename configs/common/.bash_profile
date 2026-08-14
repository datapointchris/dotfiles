# shellcheck shell=bash
# shellcheck disable=SC1091

export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"
export XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
export XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
export XDG_BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"

export SHELL_DIR="$HOME/.local/shell"
export EDITOR="nvim"

# Readline's own search is `$INPUTRC`, then `~/.inputrc`, then `/etc/inputrc`,
# and this repo deploys neither of the last two — so without this line every
# setting in `configs/common/.config/readline/inputrc` is silently absent for
# any bash that has no zsh above it to inherit the variable from. `.zshrc`
# exports the same path for the same reason, which is duplication the deployment
# cannot avoid: `configs/` merges nothing, and the two shells share no file.
#
# Read after the startup files, not before them: readline initialises on the
# first prompt, so exporting it here is in time.
export INPUTRC="$XDG_CONFIG_HOME/readline/inputrc"

[[ -f "$HOME/.env" ]] && source "$HOME/.env"

# Prepended onto the PATH this shell was handed, and only where it does not
# already carry the directory.
#
# The membership test is what keeps nested login shells from accumulating
# duplicate entries. An unconditional prepend needs a `PATH=` assignment above it
# to do that job instead, and this file cannot afford one: Git Bash reads it for
# every login shell, and there the inherited PATH is the only copy of System32,
# the winget shim directory, and everything else Windows assembles from the
# registry. Appending `:$PATH` to such an assignment saves those and hands the
# accumulation straight back, so the test is what holds both properties at once —
# nothing inherited is discarded, and a second run changes nothing.
#
# One file rather than a copy per os value: configs/ deploys whole files and
# merges nothing, so moving a single line onto the os axis means three
# .bash_profiles, two of them identical.
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
