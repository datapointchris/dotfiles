#shellcheck disable=all
# ================================================================== #
# SHARED ZSH CONFIGURATION
# Platform-agnostic configuration sourced by platform-specific configs
# ================================================================== #

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

# Create history directory if it doesn't exist
[[ ! -d "$HOME/.local/state/zsh" ]] && mkdir -p "$HOME/.local/state/zsh"

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

# ------------------------------------------------------------------ #
# PROMPT AND THEME
# ------------------------------------------------------------------ #
# Load prompt configuration from separate file
source "$HOME/.config/zsh/prompt.zsh"

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
fi

# Load any other manually installed plugins
for plugin_dir in "$ZSH_PLUGINS_DIR"/*; do
    if [[ -d "$plugin_dir" ]]; then
        plugin_name=$(basename "$plugin_dir")
        # Look for common plugin file patterns
        for plugin_file in "$plugin_dir/$plugin_name.plugin.zsh" "$plugin_dir/$plugin_name.zsh" "$plugin_dir/init.zsh"; do
            if [[ -f "$plugin_file" ]]; then
                source "$plugin_file"
                break
            fi
        done
    fi
done

# ================================================================== #

# ------------------------------------------------------------------ #
# SHELL CONFIG
# ------------------------------------------------------------------ #
source "$HOME/.env"

# Platform-specific shell integrations
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS specific
    [[ -f "$HOME/.iterm2_shell_integration.zsh" ]] && source "$HOME/.iterm2_shell_integration.zsh"
fi

SHELLS="$HOME/.shell"
source "$SHELLS/aliases.sh"
source "$SHELLS/colors.sh"
source "$SHELLS/formatting.sh"
source "$SHELLS/functions.sh"

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

if command -v jenv &>/dev/null; then
    eval "$(jenv init -)"
    add_path "$HOME/.jenv/bin/"
    JAVA_HOME="$HOME/.jenv/versions/$(jenv version-name)"
    export JAVA_HOME
    add_path "$JAVA_HOME/bin"
fi

if command -v pyenv &>/dev/null; then
    PYENV_ROOT="$XDG_DATA_HOME/pyenv"
    export PYENV_ROOT
    add_path "$PYENV_ROOT/bin"
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

    # Brew
    add_path "/usr/local/sbin"
    add_path "/usr/local/bin"
else
    # Linux/WSL specific paths
    # Add WSL-specific paths here
    :
fi

# ------------------------------------------------------------------ #
# TERMINAL APPS
# ------------------------------------------------------------------ #

# Initialize zoxide with 'z' command instead of overriding 'cd'
if command -v zoxide >/dev/null 2>&1; then
    eval "$(zoxide init --cmd z zsh)"
fi

# Initialize fzf
if command -v fzf >/dev/null 2>&1; then
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
fi

# Yazi wrapper (if installed)
if command -v yazi >/dev/null 2>&1; then
    function y() {
        local tmp="$(mktemp -t "yazi-cwd.XXXXXX")" cwd
        yazi "$@" --cwd-file="$tmp"
        IFS= read -r -d '' cwd <"$tmp"
        [[ -n "$cwd" ]] && [[ "$cwd" != "$PWD" ]] && builtin cd -- "$cwd" || return
        rm -f -- "$tmp"
    }
fi

# ------------------------------------------------------------------ #
# SYNTAX HIGHLIGHTING (Load at end - cross-platform)
# ------------------------------------------------------------------ #
# Try package manager installations first, then manual plugins
if [[ -f "/usr/local/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" ]]; then
    # macOS Homebrew location
    source "/usr/local/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"
elif [[ -f "/usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" ]]; then
    # Ubuntu/Debian APT location
    source "/usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"
elif [[ -f "/usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" ]]; then
    # Arch Linux location
    source "/usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"
elif [[ -f "$ZSH_PLUGINS_DIR/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" ]]; then
    # Manual installation fallback
    source "$ZSH_PLUGINS_DIR/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"
fi
