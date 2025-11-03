#shellcheck disable=all
# ================================================================== #
# SHARED ZSH CONFIGURATION
# Platform-agnostic configuration sourced by platform-specific configs
# ================================================================== #

echo " 🟰🟰🟰🟰🟰 Loading ZSH Configuration 🟰🟰🟰🟰🟰🟰"

# ------------------------------------------------------------------ #
# ENVIRONMENT VALIDATION
# ------------------------------------------------------------------ #
local check=" ✔️"
local error=" ❌"

SHELLS="$HOME/.shell"
source "$SHELLS/colors.sh"
source "$SHELLS/formatting.sh"

# Check for .env file and required variables
if [[ -f "$HOME/.env" ]]; then
    source "$HOME/.env"
    echo "$check Load  : $HOME/.env"

    # Validate required environment variables
    if [[ -n "$PLATFORM" ]]; then
      echo "$check Env   : $(color_cyan "PLATFORM")=$(color_green "$PLATFORM")"
    else
        color_red "$error Env   : PLATFORM not set in .env"
    fi

    if [[ -n "$NVIM_AI_ENABLED" ]]; then
      echo "$check Env   : $(color_cyan "NVIM_AI_ENABLED")=$(color_green "$NVIM_AI_ENABLED")"
    else
        color_red "$error Env   : NVIM_AI_ENABLED not set in .env"
    fi
else
    echo "$error .env file not found at $HOME/.env"
fi

# ------------------------------------------------------------------ #
# ZSH CONFIGURATION
# ------------------------------------------------------------------ #
DEBUG=1
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

# Create history directory if it doesn't exist
[[ ! -d "$HOME/.local/state/zsh" ]] && mkdir -p "$HOME/.local/state/zsh"
echo "$check Setup : History Search & Command Editing"

# ------------------------------------------------------------------ #
# GENERAL SETTINGS
# ------------------------------------------------------------------ #
export EDITOR="nvim"
export HOMEBREW_NO_AUTO_UPDATE=1
export BAT_THEME="gruvbox-dark"

# ------------------------------------------------------------------ #
# CONFIG FILE LOCATIONS (XDG Base Directory)
# ------------------------------------------------------------------ #
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_CACHE_HOME="$HOME/.cache"
export XDG_DATA_HOME="$HOME/.local/share"
export XDG_STATE_HOME="$HOME/.local/state"

# Config
export BASH_COMPLETION_USER_FILE="$XDG_CONFIG_HOME/bash-completion/bash_completion"
export DOCKER_CONFIG="$XDG_CONFIG_HOME/docker"
export INPUTRC="$XDG_CONFIG_HOME/readline/inputrc"
export KUBECONFIG="$XDG_CONFIG_HOME/kube"
export NPM_CONFIG_USERCONFIG="$XDG_CONFIG_HOME/npm/npmrc"
export PGPASSFILE="$XDG_CONFIG_HOME/pg/pgpass"
export PGSERVICEFILE="$XDG_CONFIG_HOME/pg/pg_service.conf"
export PSQLRC="$XDG_CONFIG_HOME/pg/psqlrc"
export REDISCLI_RCFILE="$XDG_CONFIG_HOME/redis/redisclirc"
export RIPGREP_CONFIG_PATH="$XDG_CONFIG_HOME/ripgrep/ripgreprc"

# State
export PSQL_HISTORY="$XDG_STATE_HOME/psql_history"
export PYTHON_HISTORY="$XDG_STATE_HOME/python/history"

# Cache
export KUBECACHEDIR="$XDG_CACHE_HOME/kube"
export PYTHONPYCACHEPREFIX="$XDG_CACHE_HOME/python"

# Data
export AZURE_CONFIG_DIR="$XDG_DATA_HOME/azure"
export ELECTRUMDIR="$XDG_DATA_HOME/electrum"
export NODE_REPL_HISTORY="$XDG_DATA_HOME/node_repl_history"
export PYTHONUSERBASE="$XDG_DATA_HOME/python"
export REDISCLI_HISTFILE="$XDG_DATA_HOME/redis/rediscli_history"
echo "$check Setup : XDG Directories"

# ------------------------------------------------------------------ #
# COMPLETIONS
# ------------------------------------------------------------------ #
# Create cache directories
[[ ! -d "$XDG_CACHE_HOME/zsh" ]] && mkdir -p "$XDG_CACHE_HOME/zsh"

# Set the cache path for Zsh completion to a directory within the XDG cache home.
# This helps in storing completion cache files in a standardized location.
zstyle ':completion:*' cache-path "$XDG_CACHE_HOME"/zsh/zcompcache

# Initialize the Zsh completion system using a version-specific dump file.
# The dump file stores the state of the completion system and is located in the XDG cache home.
# Using a version-specific file ensures compatibility with the current Zsh version.
autoload -Uz compinit
compinit -d "$XDG_CACHE_HOME/zsh/zcompdump-$ZSH_VERSION"

# Completion styling
zstyle ':completion:*' menu select
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"
zstyle ':completion:*:descriptions' format "%B--- %d%b"
zstyle ':completion:*' cache-path "$XDG_CACHE_HOME/zsh/zcompcache"

# Enable alias completion
setopt COMPLETE_ALIASES

# Terraform completion (if installed)
if command -v terraform >/dev/null 2>&1; then
    autoload -U +X bashcompinit && bashcompinit
    complete -o nospace -C terraform terraform
fi

echo "$check Setup : ZSH Completions"

# ------------------------------------------------------------------ #
# PROMPT AND THEME
# ------------------------------------------------------------------ #
# Load prompt configuration from separate file
source "$HOME/.config/zsh/prompt.zsh"
echo "$check Load  : $HOME/.config/zsh/prompt.zsh"

# ------------------------------------------------------------------ #
# OH-MY-ZSH PLUGIN REPLACEMENTS (Cross-Platform)
# ------------------------------------------------------------------ #

# ========== colored-man-pages plugin replacement ==========
export LESS_TERMCAP_mb=$'\e[1;32m'     # begin bold
export LESS_TERMCAP_md=$'\e[1;32m'     # begin blink
export LESS_TERMCAP_so=$'\e[01;33m'    # begin reverse video
export LESS_TERMCAP_us=$'\e[01;4;31m'  # begin underline
export LESS_TERMCAP_me=$'\e[0m'        # reset bold/blink
export LESS_TERMCAP_se=$'\e[0m'        # reset reverse video
export LESS_TERMCAP_ue=$'\e[0m'        # reset underline
export GROFF_NO_SGR=1                  # for groff compatibility

# ========== gh plugin replacement ==========
# GitHub CLI completions (available via package managers on all platforms)
if command -v gh >/dev/null 2>&1; then
    eval "$(gh completion -s zsh)"
fi

# ========== gnu-utils plugin replacement ==========
# Platform-specific GNU coreutils setup
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS: Use GNU coreutils from Homebrew
    gnu_paths=(
        "/usr/local/opt/coreutils/libexec/gnubin"
        "/usr/local/opt/gnu-sed/libexec/gnubin"
        "/usr/local/opt/gnu-tar/libexec/gnubin"
        "/usr/local/opt/grep/libexec/gnubin"
    )
    for gnu_path in "${gnu_paths[@]}"; do
        [[ -d "$gnu_path" ]] && export PATH="$gnu_path:$PATH"
    done
else
    # Linux: GNU coreutils are already default, no changes needed
    :
fi

# ========== Manual plugin loading from ~/.config/zsh/plugins ==========
ZSH_PLUGINS_DIR="$HOME/.config/zsh/plugins"

# Load git-open (manually cloned for cross-platform compatibility)
if [[ -f "$ZSH_PLUGINS_DIR/git-open/git-open" ]]; then
    export PATH="$ZSH_PLUGINS_DIR/git-open:$PATH"
  else
    echo "$error git-open plugin not found at $ZSH_PLUGINS_DIR/git-open"
fi

# Load zsh-vi-mode (manually cloned for cross-platform compatibility)
if [[ -f "$ZSH_PLUGINS_DIR/zsh-vi-mode/zsh-vi-mode.plugin.zsh" ]]; then
    source "$ZSH_PLUGINS_DIR/zsh-vi-mode/zsh-vi-mode.plugin.zsh"
  else
    echo "$error zsh-vi-mode plugin not found at $ZSH_PLUGINS_DIR/zsh-vi-mode"
fi

echo "$check Load  : $ZSH_PLUGINS_DIR"
# ================================================================== #

# ------------------------------------------------------------------ #
# SHELL CONFIG
# ------------------------------------------------------------------ #

# Platform-specific shell integrations
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS specific
    iterm2_shell_integration="$HOME/.iterm2_shell_integration.zsh"
    [[ -f $iterm2_shell_integration ]] && source $iterm2_shell_integration && echo "$check Load  : $iterm2_shell_integration"
fi

source "$SHELLS/aliases.sh"
echo "$check Load  : $SHELLS/aliases.sh"
[[ -f "$SHELLS/$PLATFORM-aliases.sh" ]] && source "$SHELLS/$PLATFORM-aliases.sh" && echo "$check Load  : $SHELLS/$PLATFORM-aliases.sh"

source "$SHELLS/functions.sh"
echo "$check Load  : $SHELLS/functions.sh"
[[ -f "$SHELLS/$PLATFORM-functions.sh" ]] && source "$SHELLS/$PLATFORM-functions.sh" && echo "$check Load  : $SHELLS/$PLATFORM-functions.sh"

# ------------------------------------------------------------------- #
# PATH AND ENVIRONMENT SETUP (Platform-Specific)
# ------------------------------------------------------------------- #
function add_path() {
    if [[ -d "$1" ]]; then
        export PATH="$1:$PATH"
    fi
}

# Common tools

if command -v cargo &>/dev/null; then
    CARGO_HOME="$XDG_DATA_HOME/cargo"
    export CARGO_HOME
    add_path "$CARGO_HOME/bin"
fi

# Local bin (always)
add_path "$HOME/.local/bin"

# Platform-specific PATH setup
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS specific paths
    # Spark is installed into /usr/local/bin (Already in PATH)

    if command -v scala &>/dev/null; then
        SCALA_HOME="/usr/local/opt/scala@2.12"
        export SCALA_HOME
        add_path "$SCALA_HOME/bin"
    fi

    # Postgres 16, `postgres` points to Postgres 14
    add_path "/usr/local/opt/postgresql@16/bin"

    # SnowSQL since it is an Application
    add_path "/Applications/SnowSQL.app/Contents/MacOS"

    # npm installed global packages
    add_path "$HOME/.local/share/npm/bin"

    # go installed packages
    add_path "$HOME/go/bin"

else
    # Linux/WSL specific paths
    add_path "/snap/bin"
    add_path "/opt/nvim"
    add_path "/usr/local/go/bin"
    :
fi

add_path "/usr/local/sbin"
add_path "/usr/local/bin"

# Add system bin last to put at front to make sure to use macos system tools if available
add_path "/usr/bin"

echo "$check Load  : Paths"

# ------------------------------------------------------------------ #
# TERMINAL APPS
# ------------------------------------------------------------------ #

# ---------- zoxide ---------- #
eval "$(zoxide init --cmd z zsh)"


# ---------- fzf ---------- #
source <(fzf --zsh)

# fzf uses find by default but change to fd because it is faster and better
export FZF_DEFAULT_COMMAND="fd --hidden --strip-cwd-prefix --exclude .git"
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
export FZF_ALT_COMMAND="fd --type-d --hidden --strip-cwd-prefix --exclude .git"

show_file_or_dir_preview="if [ -d {} ]; then eza --tree --color=always {} | head -200; else bat -n --color=always --line-range :500 {}; fi"

export FZF_CTRL_T_OPTS="--preview '$show_file_or_dir_preview'"
export FZF_ALT_C_OPTS="--preview 'eza --tree --color=always {} | head -200'"

# Advanced customization of fzf options via _fzf_comprun function
# - The first argument to the function is the name of the command.
# - You should make sure to pass the rest of the arguments to fzf.
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

# for ** completion of files
_fzf_compgen_path() {
    fd --hidden --follow --exclude .git . "$1"
}

# for ** completion of directories
_fzf_compgen_dir() {
    fd --type d --hidden --follow --exclude .git . "$1"
}


# ---------- nvim ---------- #
export NVM_DIR="$HOME/.config/nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion


# ---------- yazi ---------- #
function yy() {
    local tmp="$(mktemp -t "yazi-cwd.XXXXXX")" cwd
    yazi "$@" --cwd-file="$tmp"
    IFS= read -r -d '' cwd <"$tmp"
    [[ -n "$cwd" ]] && [[ "$cwd" != "$PWD" ]] && builtin cd -- "$cwd" || return
    rm -f -- "$tmp"
}

echo "$check Setup : Terminal Apps"

# ------------------------------------------------------------------ #
# SYNTAX HIGHLIGHTING (Load at end - cross-platform)
# ------------------------------------------------------------------ #
# Check common paths for different systems
if [[ -f "/usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" ]]; then
    source "/usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"
    echo "$check Load  : /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh (Linux)"
elif [[ -f "/opt/homebrew/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" ]]; then
    source "/opt/homebrew/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"
    echo "$check Load  : /opt/homebrew/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh (macOS Homebrew)"
elif [[ -f "/usr/local/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" ]]; then
    source "/usr/local/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"
    echo "$check Load  : /usr/local/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh (macOS Intel Homebrew)"
else
    echo "Could not find zsh syntax highlighting (checked Linux, macOS Homebrew paths)"
fi

echo " 🟰🟰🟰🟰🟰 ZSH Configuration Loaded 🟰🟰🟰🟰🟰🟰"
