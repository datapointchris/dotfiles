#shellcheck disable=all
# ------------------------------------------------------------------ #
# SHARED ZSH CONFIGURATION
# Platform-agnostic configuration sourced by platform-specific configs
# ------------------------------------------------------------------ #

echo " 🟰🟰🟰🟰🟰 Loading ZSH Configuration 🟰🟰🟰🟰🟰🟰"

# ------------------------------------------------------------------ #
# BOOTSTRAP: Load environment and utilities
# ------------------------------------------------------------------ #
CHECK_MARK="☑️"
ERROR_MARK="❌"
# Load .env first (sets ZSHRC_DEBUG if present)
[[ -f "$HOME/.env" ]] && source "$HOME/.env" && ZSHRC_DEBUG="${ZSHRC_DEBUG:-1}" || ZSHRC_DEBUG="${ZSHRC_DEBUG:-1}"

log() { [[ "$ZSHRC_DEBUG" == "1" ]] && printf "  $CHECK_MARK %-6s : %s\n" "$1" "$2" }
log_error() { printf "  $ERROR_MARK %-6s : %s\n" "$1" "$2" >&2 }

# Log environment
env_file="$HOME/.env"
colors_file="$HOME/shell/colors.sh"
formatting_file="$HOME/shell/formatting.sh"
[[ -f $env_file ]] && source $env_file && log "Load" "$env_file" || log_error "Load" "$env_file"
[[ -f $colors_file ]] && source $colors_file && log "Load" "$colors_file" || log_error "Load" "$colors_file"
[[ -f $formatting_file ]] && source $formatting_file && log "Load" "$formatting_file" || log_error "Load" "$formatting_file"

# Validate required environment variables
if [[ -n "$PLATFORM" ]]; then
  log "Env" "$(color_cyan "PLATFORM")=$(color_green "$PLATFORM")"
else
  log_error "Env" "PLATFORM not set in .env"
fi

if [[ -n "$NVIM_AI_ENABLED" ]]; then
  log "Env" "$(color_cyan "NVIM_AI_ENABLED")=$(color_green "$NVIM_AI_ENABLED")"
else
  log_error "Env" "NVIM_AI_ENABLED not set in .env"
fi

# ------------------------------------------------------------------ #
# ZSH CONFIGURATION
# ------------------------------------------------------------------ #
# Enable extended globbing, parameter expansion, command substitution, and arithmetic expansion
setopt EXTENDED_GLOB
setopt PROMPT_SUBST

# History settings
HISTFILE="$HOME/.local/state/zsh/history"
HISTSIZE=10000
SAVEHIST=10000
setopt HIST_IGNORE_DUPS
setopt HIST_FIND_NO_DUPS
setopt HIST_REDUCE_BLANKS
setopt SHARE_HISTORY

# History search: up/down arrows search history based on current line
autoload -U up-line-or-beginning-search
autoload -U down-line-or-beginning-search
zle -N up-line-or-beginning-search
zle -N down-line-or-beginning-search
bindkey "^[[A" up-line-or-beginning-search    # Up arrow
bindkey "^[[B" down-line-or-beginning-search  # Down arrow

# Create history directory if needed
if [[ ! -d "$HOME/.local/state/zsh" ]]; then
  mkdir -p "$HOME/.local/state/zsh"
  log "Setup" "Created $HOME/.local/state/zsh"
fi

log "Setup" "History & Command Editing"

# ------------------------------------------------------------------ #
# GENERAL SETTINGS
# ------------------------------------------------------------------ #
export EDITOR="nvim"
export HOMEBREW_NO_AUTO_UPDATE=1
export BAT_THEME="gruvbox-dark"

# Tool directories
export CARGO_HOME="$HOME/.cargo"
export NVM_DIR="$HOME/.config/nvm"

# ------------------------------------------------------------------ #
# XDG BASE DIRECTORY
# ------------------------------------------------------------------ #
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_CACHE_HOME="$HOME/.cache"
export XDG_DATA_HOME="$HOME/.local/share"
export XDG_STATE_HOME="$HOME/.local/state"

# Config locations
export BASH_COMPLETION_USER_FILE="$XDG_CONFIG_HOME/bash-completion/bash_completion"
export DOCKER_CONFIG="$XDG_CONFIG_HOME/docker"
export INPUTRC="$XDG_CONFIG_HOME/readline/inputrc"
export JUPYTER_CONFIG_DIR="$XDG_CONFIG_HOME/jupyter"
export KUBECONFIG="$XDG_CONFIG_HOME/kube"
export NPM_CONFIG_USERCONFIG="$XDG_CONFIG_HOME/npm/npmrc"
export PGPASSFILE="$XDG_CONFIG_HOME/pg/pgpass"
export PGSERVICEFILE="$XDG_CONFIG_HOME/pg/pg_service.conf"
export PSQLRC="$XDG_CONFIG_HOME/pg/psqlrc"
export REDISCLI_RCFILE="$XDG_CONFIG_HOME/redis/redisclirc"
export RIPGREP_CONFIG_PATH="$XDG_CONFIG_HOME/ripgrep/ripgreprc"
export TF_CLI_CONFIG_FILE="$XDG_CONFIG_HOME/terraform/terraformrc"
export WGETRC="$XDG_CONFIG_HOME/wget/wgetrc"

# State locations
export PSQL_HISTORY="$XDG_STATE_HOME/psql_history"
export PYTHON_HISTORY="$XDG_STATE_HOME/python/history"
export LESSHISTFILE="$XDG_STATE_HOME/less/history"

# Cache locations
export GEM_SPEC_CACHE="$XDG_CACHE_HOME/gem"
export KUBECACHEDIR="$XDG_CACHE_HOME/kube"
export PYTHONPYCACHEPREFIX="$XDG_CACHE_HOME/python"
export TF_PLUGIN_CACHE_DIR="$XDG_CACHE_HOME/terraform/plugins"
export TLDR_CACHE_HOME="$XDG_CACHE_HOME/tldr"

# Data locations
export AZURE_CONFIG_DIR="$XDG_DATA_HOME/azure"
export ELECTRUMDIR="$XDG_DATA_HOME/electrum"
export GEM_HOME="$XDG_DATA_HOME/gem"
export GNUPGHOME="$XDG_DATA_HOME/gnupg"
export NODE_REPL_HISTORY="$XDG_DATA_HOME/node_repl_history"
export PYTHONUSERBASE="$XDG_DATA_HOME/python"
export REDISCLI_HISTFILE="$XDG_DATA_HOME/redis/rediscli_history"

log "Setup" "XDG Directories"

# ------------------------------------------------------------------ #
# COMPLETIONS
# ------------------------------------------------------------------ #
# Create cache directories
if [[ ! -d "$XDG_CACHE_HOME/zsh" ]]; then
  mkdir -p "$XDG_CACHE_HOME/zsh"
  log "Setup" "Created $XDG_CACHE_HOME/zsh"
fi

# Set the cache path for Zsh completion to a directory within the XDG cache home.
# This helps in storing completion cache files in a standardized location.
zstyle ':completion:*' cache-path "$XDG_CACHE_HOME"/zsh/zcompcache

# Initialize the Zsh completion system using a version-specific dump file.
# The dump file stores the state of the completion system and is located in the XDG cache home.
# Using a version-specific file ensures compatibility with the current Zsh version.
autoload -Uz compinit
compinit -d "$XDG_CACHE_HOME/zsh/zcompdump-$ZSH_VERSION"
log "Setup" "compinit"

# Completion styling
zstyle ':completion:*' menu select
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"
zstyle ':completion:*:descriptions' format "%B--- %d%b"

setopt COMPLETE_ALIASES

# Terraform completion
if command -v terraform >/dev/null 2>&1; then
    autoload -U +X bashcompinit && bashcompinit
    complete -o nospace -C terraform terraform
    log "Setup" "terraform completions"
fi

# GitHub CLI completions
if command -v gh >/dev/null 2>&1; then
    eval "$(gh completion -s zsh)"
    log "Setup" "gh completions"
fi

log "Setup" "Completions"

# ------------------------------------------------------------------ #
# PROMPT
# ------------------------------------------------------------------ #
my_prompt="$HOME/.config/zsh/prompt.zsh"
[[ -f $my_prompt ]] && source $my_prompt && log "Load" $my_prompt || log_error "Load" $my_prompt

# ------------------------------------------------------------------ #
# PLUGIN REPLACEMENTS
# ------------------------------------------------------------------ #

# colored-man-pages
export LESS_TERMCAP_mb=$'\e[1;32m'     # begin bold
export LESS_TERMCAP_md=$'\e[1;32m'     # begin blink
export LESS_TERMCAP_so=$'\e[01;33m'    # begin reverse video
export LESS_TERMCAP_us=$'\e[01;4;31m'  # begin underline
export LESS_TERMCAP_me=$'\e[0m'        # reset bold/blink
export LESS_TERMCAP_se=$'\e[0m'        # reset reverse video
export LESS_TERMCAP_ue=$'\e[0m'        # reset underline
export GROFF_NO_SGR=1                  # for groff compatibility

# ------------------------------------------------------------------ #
# SHELL CONFIG
# ------------------------------------------------------------------ #

# File paths
SHELLS="$HOME/shell/"
iterm2_integration="$HOME/.iterm2_shell_integration.zsh"
aliases_file="$SHELLS/aliases.sh"
platform_aliases_file="$SHELLS/$PLATFORM-aliases.sh"
functions_file="$SHELLS/functions.sh"
fzf_functions_file="$SHELLS/fzf-functions.sh"
platform_functions_file="$SHELLS/$PLATFORM-functions.sh"

# Platform-specific integrations
if [[ "$OSTYPE" == "darwin"* ]]; then
  [[ -f "$iterm2_integration" ]] && source "$iterm2_integration" && log "Load" "$iterm2_integration"
fi

# Aliases
[[ -f "$aliases_file" ]] && source "$aliases_file" && log "Load" "$aliases_file" || log_error "Load" "$aliases_file"
[[ -f "$platform_aliases_file" ]] && source "$platform_aliases_file" && log "Load" "$platform_aliases_file"

# Functions
[[ -f "$functions_file" ]] && source "$functions_file" && log "Load" "$functions_file" || log_error "Load" "$functions_file"
[[ -f "$fzf_functions_file" ]] && source "$fzf_functions_file" && log "Load" "$fzf_functions_file" || log_error "Load" "$fzf_functions_file"
[[ -f "$platform_functions_file" ]] && source "$platform_functions_file" && log "Load" "$platform_functions_file"

# ------------------------------------------------------------------ #
# PATH SETUP
# ------------------------------------------------------------------ #
# Strategy: User tools > Language ecosystems > System
# add_path PREPENDS, so last call = highest priority

function add_path() {
  [[ -d "$1" ]] && export PATH="$1:$PATH" && log "Path" "$1"
}

# Tier 3: System (lowest priority - added first, ends up last)
add_path "/usr/bin"
add_path "/usr/local/bin"
add_path "/usr/local/sbin"

# Tier 2: Platform-specific
if [[ "$OSTYPE" == "darwin"* ]]; then
  add_path "/usr/local/opt/postgresql@16/bin"
  add_path "$HOME/go/bin"
else
  add_path "/snap/bin"
  add_path "/usr/local/go/bin"
  add_path "$HOME/go/bin"
fi

# Tier 1: User tools (highest priority - added last, ends up first)
add_path "$ZSH_PLUGINS_DIR/forgit/bin"
add_path "$HOME/.local/bin"
add_path "$HOME/.local/share/npm/bin"  # npm global packages
add_path "$CARGO_HOME/bin"

# ------------------------------------------------------------------ #
# TERMINAL APPS
# ------------------------------------------------------------------ #

# zoxide
if command -v zoxide >/dev/null 2>&1; then
  eval "$(zoxide init --cmd z zsh)"
  log "Setup" "zoxide"
else
  log_error "Setup" "zoxide not found"
fi

# fzf
if command -v fzf >/dev/null 2>&1; then
  source <(fzf --zsh)

  export FZF_DEFAULT_COMMAND="fd --hidden --strip-cwd-prefix --exclude .git"
  export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
  export FZF_ALT_COMMAND="fd --type-d --hidden --strip-cwd-prefix --exclude .git"

  show_file_or_dir_preview="if [ -d {} ]; then eza --tree --color=always {} | head -200; else bat -n --color=always --line-range :500 {}; fi"
  export FZF_CTRL_T_OPTS="--preview '$show_file_or_dir_preview'"
  export FZF_ALT_C_OPTS="--preview 'eza --tree --color=always {} | head -200'"

  _fzf_comprun() {
    local command=$1
    shift
    case "$command" in
      cd) fzf --preview 'eza --tree --color=always {} | head -200' "$@" ;;
      export | unset) fzf --preview "eval 'echo $'{}" "$@" ;;
      ssh) fzf --preview 'dig {}' "$@" ;;
      *) fzf --preview "bat -n --color=always --line-range :500 {}" "$@" ;;
    esac
  }

  _fzf_compgen_path() { fd --hidden --follow --exclude .git . "$1"; }
  _fzf_compgen_dir() { fd --type d --hidden --follow --exclude .git . "$1"; }

  log "Setup" "fzf"
else
  log_error "Setup" "fzf not found"
fi

# nvm
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  source "$NVM_DIR/nvm.sh"
  source "$NVM_DIR/bash_completion"
  log "Setup" "nvm"
else
  log_error "Setup" "nvm not found at $NVM_DIR/nvm.sh"
fi

# uv
if command -v uv >/dev/null 2>&1; then
  eval "$(uv generate-shell-completion zsh)"
  log "Setup" "uv"
else
  log_error "Setup" "uv not found"
fi

# yazi
if command -v yazi >/dev/null 2>&1; then
  yy() {
    local tmp="$(mktemp -t "yazi-cwd.XXXXXX")" cwd
    yazi "$@" --cwd-file="$tmp"
    IFS= read -r -d '' cwd <"$tmp"
    [[ -n "$cwd" ]] && [[ "$cwd" != "$PWD" ]] && builtin cd -- "$cwd" || return
    rm -f -- "$tmp"
  }
  log "Setup" "yazi"
else
  log_error "Setup" "yazi not found"
fi

# ------------------------------------------------------------------ #
# ZSH PLUGINS (manually cloned to ~/.config/zsh/plugins)
# ------------------------------------------------------------------ #
# NOTE: zsh-syntax-highlighting MUST be loaded last per their docs
ZSH_PLUGINS_DIR="$HOME/.config/zsh/plugins"

# Plugin file paths
git_open_file="$ZSH_PLUGINS_DIR/git-open/git-open"
zsh_vi_mode_file="$ZSH_PLUGINS_DIR/zsh-vi-mode/zsh-vi-mode.plugin.zsh"
forgit_file="$ZSH_PLUGINS_DIR/forgit/forgit.plugin.zsh"
forgit_completions="$ZSH_PLUGINS_DIR/forgit/completions"
syntax_highlighting_file="$ZSH_PLUGINS_DIR/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"

# git-open
if [[ -f "$git_open_file" ]]; then
  export PATH="$ZSH_PLUGINS_DIR/git-open:$PATH"
  log "Load" "$git_open_file"
else
  log_error "Load" "$git_open_file"
fi

# zsh-vi-mode
if [[ -f "$zsh_vi_mode_file" ]]; then
  source "$zsh_vi_mode_file"
  log "Load" "$zsh_vi_mode_file"
else
  log_error "Load" "$zsh_vi_mode_file"
fi

# forgit
if [[ -f "$forgit_file" ]]; then
  source "$forgit_file"
  log "Load" "$forgit_file"
  fpath+=($forgit_completions)
  log "Load" "$forgit_completions"
else
  log_error "Load" "$forgit_file"
fi

# zsh-syntax-highlighting (MUST load last)
if [[ -f "$syntax_highlighting_file" ]]; then
  source "$syntax_highlighting_file"
  log "Load" "$syntax_highlighting_file"
else
  log_error "Load" "$syntax_highlighting_file"
fi

echo " 🟰🟰🟰🟰🟰 ZSH Configuration Loaded 🟰🟰🟰🟰🟰🟰"
