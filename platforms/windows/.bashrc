# shellcheck shell=bash
# Git Bash config - sources shell config from WSL Ubuntu dotfiles

# WSL paths (must be running for these to work)
WSL_HOME="//wsl$/Ubuntu-24.04/home/chris"
WSL_SHELL_DIR="$WSL_HOME/.local/shell"

# Fallback if WSL not running
if [[ ! -d "$WSL_HOME" ]]; then
  echo "⚠ WSL not running - using minimal config"
  PS1='\[\e[32m\]\u@gitbash\[\e[0m\]:\[\e[33m\]\w\[\e[0m\] \$ '
  # shellcheck disable=SC2317
  return 0 2>/dev/null || exit 0
fi

# Shell library
[[ -f "$WSL_SHELL_DIR/colors.sh" ]] && source "$WSL_SHELL_DIR/colors.sh"
[[ -f "$WSL_SHELL_DIR/formatting.sh" ]] && source "$WSL_SHELL_DIR/formatting.sh"

# Aliases and functions
[[ -f "$WSL_SHELL_DIR/aliases.sh" ]] && source "$WSL_SHELL_DIR/aliases.sh"
[[ -f "$WSL_SHELL_DIR/functions.sh" ]] && source "$WSL_SHELL_DIR/functions.sh"
[[ -f "$WSL_SHELL_DIR/wsl-aliases.sh" ]] && source "$WSL_SHELL_DIR/wsl-aliases.sh"
[[ -f "$WSL_SHELL_DIR/wsl-functions.sh" ]] && source "$WSL_SHELL_DIR/wsl-functions.sh"

# Prompt
[[ -f "$WSL_SHELL_DIR/.bash_prompt" ]] && source "$WSL_SHELL_DIR/.bash_prompt"

# Tools (install via: winget install junegunn.fzf ajeetdsouza.zoxide)
command -v zoxide >/dev/null 2>&1 && eval "$(zoxide init bash)"
command -v fzf >/dev/null 2>&1 && eval "$(fzf --bash)"

# History
HISTSIZE=10000
HISTFILESIZE=20000
HISTCONTROL=ignoreboth:erasedups
shopt -s histappend

# Shell options
shopt -s nocaseglob
shopt -s cdspell
shopt -s globstar 2>/dev/null

# Windows-specific aliases
alias explorer='explorer.exe .'
alias open='start'
alias clip='clip.exe'
alias paste='powershell.exe Get-Clipboard'

# Path
[[ -d "$HOME/bin" ]] && export PATH="$HOME/bin:$PATH"
