#shellcheck shell=bash
# shellcheck disable=SC2034
# SC2034 = Variable appears unused -- For the vars picked up by oh-my-zsh

export ZSH="$HOME/.oh-my-zsh"

# Add the zsh-completions plugin directory to the fpath.
# This must be set early to ensure that Zsh can locate and use additional
# completion scripts before any other configurations or plugins are loaded.
# The directory path is constructed using the ZSH_CUSTOM variable if set,
# otherwise it falls back to the default Oh My Zsh custom directory.
fpath+=${ZSH_CUSTOM:-${ZSH:-~/.oh-my-zsh}/custom}/plugins/zsh-completions/src

# Allow oh-my-zsh to auto-update without prompt
DISABLE_UPDATE_PROMPT="true"
ZSH_THEME="datapointchris"

plugins=(
    colored-man-pages
    git-open
    gh
    gnu-utils
    zsh-syntax-highlighting
)

# shellcheck source=/dev/null1
source "$ZSH/oh-my-zsh.sh"

# ----------------- CONFIG FILE LOCATIONS ----------------- #

export XDG_CONFIG_HOME="$HOME/.config"
export XDG_CACHE_HOME="$HOME/.cache"
export XDG_DATA_HOME="$HOME/.local/share"
export XDG_STATE_HOME="$HOME/.local/state"

HISTFILE="$XDG_STATE_HOME/zsh/history"

# Completion files: Use XDG dirs
[ -d "$XDG_CACHE_HOME"/zsh ] || mkdir -p "$XDG_CACHE_HOME/zsh"

# Set the cache path for Zsh completion to a directory within the XDG cache home.
# This helps in storing completion cache files in a standardized location.
zstyle ':completion:*' cache-path "$XDG_CACHE_HOME"/zsh/zcompcache

# Initialize the Zsh completion system using a version-specific dump file.
# The dump file stores the state of the completion system and is located in the XDG cache home.
# Using a version-specific file ensures compatibility with the current Zsh version.
compinit -d "$XDG_CACHE_HOME/zsh/zcompdump-$ZSH_VERSION"

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
export RUSTUP_HOME="$XDG_DATA_HOME/rustup"


source "$HOME/.env"
source "$HOME/.iterm2_shell_integration.zsh"
# DOTFILES="$HOME/dotfiles"

SHELLS="$HOME/.shell"
source "$SHELLS/aliases.sh"
source "$SHELLS/exports.sh"
source "$SHELLS/colors.sh"
source "$SHELLS/formatting.sh"
source "$SHELLS/functions.sh"


# The setopt complete_aliases command in Zsh enables the completion of command aliases.
# Zsh will attempt to complete the arguments of an alias as if it were the command it aliases.
setopt complete_aliases

# Enable Bash-style completion in Zsh
autoload -U +X bashcompinit && bashcompinit

# Set up custom completion for the terraform command without appending a space
complete -o nospace -C /usr/local/bin/terraform terraform

# Load jenv if installed (before exports so JAVA_HOME export can use jenv location)
if command -v jenv &>/dev/null; then
    eval "$(jenv init -)"
fi

# Initialize zoxide
eval "$(zoxide init --cmd cd zsh)"

##### FZF #####

# Initialize fzf
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

# Yazi wrapper to change directory
function y() {
  local tmp="$(mktemp -t "yazi-cwd.XXXXXX")" cwd
  yazi "$@" --cwd-file="$tmp"
  IFS= read -r -d '' cwd <"$tmp"
  [ -n "$cwd" ] && [ "$cwd" != "$PWD" ] && builtin cd -- "$cwd" || return
  rm -f -- "$tmp"
}
