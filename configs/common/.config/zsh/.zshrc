#shellcheck disable=all
# ------------------------------------------------------------------ #
# SHARED ZSH CONFIGURATION
# Platform-agnostic configuration sourced by platform-specific configs
# ------------------------------------------------------------------ #

# ------------------------------------------------------------------ #
# BOOTSTRAP: Load environment and utilities
# ------------------------------------------------------------------ #
# Sourced before anything else because .env is where ZSHRC_DEBUG is set; the
# entry is logged further down, once log() exists to report it.
env_file="$HOME/.env"
[[ -f $env_file ]] && source $env_file
ZSHRC_DEBUG="${ZSHRC_DEBUG:-0}"

CHECK_MARK="☑️"
ERROR_MARK="❌"
[[ "$ZSHRC_DEBUG" == "1" ]] && echo " 🟰🟰🟰🟰🟰 Loading ZSH Configuration 🟰🟰🟰🟰🟰🟰"

# Columns are step and cumulative milliseconds. Timing lives inside log() rather
# than at the call sites so every existing entry reports it for free, and a
# startup stall reads as one slow step instead of having to be bisected by hand.
zmodload zsh/datetime
typeset -g ZSHRC_START=$EPOCHREALTIME
typeset -g ZSHRC_LAST=$EPOCHREALTIME

log() {
  [[ "$ZSHRC_DEBUG" == "1" ]] || return 0
  local now=$EPOCHREALTIME
  printf "  $CHECK_MARK %6.0fms %7.0fms  %-6s : %s\n" \
    $(( (now - ZSHRC_LAST) * 1000 )) $(( (now - ZSHRC_START) * 1000 )) "$1" "$2"
  ZSHRC_LAST=$now
  return 0
}
log_error() { printf "  $ERROR_MARK %-6s : %s\n" "$1" "$2" >&2 }

# Log environment
colors_file="$HOME/.local/shell/colors.sh"
formatting_file="$HOME/.local/shell/formatting.sh"
[[ -f $env_file ]] && log "Load" "$env_file" || log_error "Load" "$env_file"
[[ -f $colors_file ]] && source $colors_file && log "Load" "$colors_file" || log_error "Load" "$colors_file"
[[ -f $formatting_file ]] && source $formatting_file && log "Load" "$formatting_file" || log_error "Load" "$formatting_file"

# Shared prompt utilities (used by prompt.zsh)
prompt_lib_file="$HOME/.local/shell/prompt-lib.sh"
[[ -f $prompt_lib_file ]] && source $prompt_lib_file && log "Load" "$prompt_lib_file" || log_error "Load" "$prompt_lib_file"

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

# Silence the ZLE bell. With zsh-vi-mode, pressing ESC while already in normal
# mode is a no-op that otherwise rings the terminal bell on every press.
unsetopt BEEP LIST_BEEP HIST_BEEP

# History settings
HISTFILE="$HOME/.local/state/zsh/history"
HISTSIZE=10000
SAVEHIST=10000
setopt EXTENDED_HISTORY
setopt HIST_IGNORE_DUPS
setopt HIST_FIND_NO_DUPS
setopt HIST_REDUCE_BLANKS
setopt SHARE_HISTORY

# History search: up/down arrows search history based on current line
# These are autoloaded here but bound in zvm_after_init (below) because
# zsh-vi-mode overwrites all keybindings when it initializes.
autoload -U up-line-or-beginning-search
autoload -U down-line-or-beginning-search
zle -N up-line-or-beginning-search
zle -N down-line-or-beginning-search

# zsh-vi-mode hook: re-apply bindings after vi-mode overwrites the keymap
zvm_after_init() {
  bindkey "^[[A" up-line-or-beginning-search    # Up arrow
  bindkey "^[[B" down-line-or-beginning-search  # Down arrow
  # Re-apply fzf keybindings (Ctrl+R, Ctrl+T, Alt+C), which vi-mode has just
  # overwritten. Reads the cache written during startup rather than re-running fzf.
  cache_eval fzf fzf --zsh
  # atuin has to follow fzf here for the same reason it does at startup: both bind
  # Ctrl-R and the last one loaded wins. vi-mode runs this after the whole rc file,
  # so re-applying fzf alone handed Ctrl-R back to it and the atuin binding set
  # during startup never survived into the shell the user actually typed in.
  cache_eval atuin atuin init zsh --disable-up-arrow
}

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
export PAGER="bat --style=plain"
export MANPAGER="bat --style=plain --language=man"
export HOMEBREW_NO_AUTO_UPDATE=1

# Tool directories
export CARGO_HOME="$HOME/.cargo"

# Declared here rather than beside the plugin loading further down, because the
# PATH section reads it first and silently added nothing when it was still empty.
ZSH_PLUGINS_DIR="$HOME/.config/zsh/plugins"

# ------------------------------------------------------------------ #
# XDG BASE DIRECTORY
# ------------------------------------------------------------------ #
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_CACHE_HOME="$HOME/.cache"
export XDG_DATA_HOME="$HOME/.local/share"
export XDG_STATE_HOME="$HOME/.local/state"
export XDG_BIN_HOME="$HOME/.local/bin"

# Shell library location
export SHELL_DIR="$HOME/.local/shell"

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
export OLLAMA_MODELS="$XDG_DATA_HOME/ollama/models"

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

# Cache generated completions, regenerating when the tool's binary is newer. Each
# otherwise spawns a subprocess per shell, and a slow one blocks startup — todoui
# reconciled with its API here and cost 6s. A missing tool is normal and stays at
# debug level; one that fails to generate always prints its stderr, and only a
# cache that actually sourced gets the success mark.
ZSH_COMPLETION_CACHE="$XDG_CACHE_HOME/zsh/completions"
[[ -d "$ZSH_COMPLETION_CACHE" ]] || mkdir -p "$ZSH_COMPLETION_CACHE"

cache_eval() {
  local name="$1"; shift
  local cache="$ZSH_COMPLETION_CACHE/$name.zsh" bin err

  if ! bin="$(command -v "$1")"; then
    log "Skip" "$name not installed"
    return 0
  fi

  if [[ ! -s "$cache" || "$bin" -nt "$cache" ]]; then
    # `2>&1 >file` splits the streams: stdout to the cache, stderr into $err.
    if err="$("$@" 2>&1 >"$cache.new")" && [[ -s "$cache.new" ]]; then
      mv -f "$cache.new" "$cache"
    else
      rm -f "$cache.new"
      log_error "Setup" "$name: ${err:-generated nothing}"
    fi
  fi

  # A failed regeneration above still leaves the previous cache usable.
  if [[ -s "$cache" ]]; then
    source "$cache"
    log "Setup" "$name"
  fi
  return 0
}

# Terraform completion
if command -v terraform >/dev/null 2>&1; then
    autoload -U +X bashcompinit && bashcompinit
    complete -o nospace -C terraform terraform
    log "Setup" "terraform completions"
fi

cache_eval gh gh completion -s zsh
cache_eval forge forge completion zsh
cache_eval todoui todoui completion zsh

log "Setup" "Completions"

# ------------------------------------------------------------------ #
# PROMPT
# ------------------------------------------------------------------ #
my_prompt="$HOME/.local/shell/prompt.zsh"
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

SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"

# Shell code (symlinked from dotfiles/shell/ by symlinks manager)
[[ -f "$SHELL_DIR/functions.sh" ]] && source "$SHELL_DIR/functions.sh" && log "Load" "$SHELL_DIR/functions.sh" || log_error "Load" "$SHELL_DIR/functions.sh"
[[ -f "$SHELL_DIR/aliases.sh" ]] && source "$SHELL_DIR/aliases.sh" && log "Load" "$SHELL_DIR/aliases.sh" || log_error "Load" "$SHELL_DIR/aliases.sh"
[[ -f "$SHELL_DIR/$PLATFORM.sh" ]] && source "$SHELL_DIR/$PLATFORM.sh" && log "Load" "$SHELL_DIR/$PLATFORM.sh" || log_error "Load" "$SHELL_DIR/$PLATFORM.sh"

# ------------------------------------------------------------------ #
# PATH SETUP
# ------------------------------------------------------------------ #
# Strategy: User tools > Language ecosystems > System
# add_path PREPENDS, so last call = highest priority

# Keeps $path unique, dropping the later copy of any entry. .zshenv seeds a
# minimal PATH for non-interactive shells and a login shell re-runs the lot, so
# without this the same directories accumulated up to four times each.
typeset -U path PATH

function add_path() {
  [[ -d "$1" ]] && export PATH="$1:$PATH" && log "Path" "$1"
}

# Tier 3: System (lowest priority - added first, ends up last)
add_path "/usr/bin"
add_path "/usr/local/bin"
add_path "/usr/local/sbin"

# Tier 2.5: GNU utilities (macOS only - override system utilities)
if [[ "$OSTYPE" == "darwin"* ]]; then
  # Add GNU coreutils, findutils, and other GNU tools without g-prefix
  add_path "/usr/local/opt/coreutils/libexec/gnubin"
  add_path "/usr/local/opt/findutils/libexec/gnubin"
  add_path "/usr/local/opt/gnu-sed/libexec/gnubin"
  add_path "/usr/local/opt/gnu-tar/libexec/gnubin"
  add_path "/usr/local/opt/grep/libexec/gnubin"
  add_path "/usr/local/opt/gawk/libexec/gnubin"
fi

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

cache_eval zoxide zoxide init --cmd z zsh

# fzf
if command -v fzf >/dev/null 2>&1; then
  cache_eval fzf fzf --zsh

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
fi

# atuin — SQLite history capture (command, exit, cwd, session) backing the
# flow-review analysis. atuin owns Ctrl-R (its DB-backed search shows time, cwd,
# and exit — richer than fzf's flat fuzzy match; it overrides fzf's Ctrl-R since
# this sources after the fzf block). Up-arrow stays the prefix-search bound above
# (--disable-up-arrow) rather than atuin's launch-a-TUI-every-press. To revert
# Ctrl-R to fzf, add --disable-ctrl-r; to also hand up-arrow to atuin, drop the
# flag.
cache_eval atuin atuin init zsh --disable-up-arrow

cache_eval uv uv generate-shell-completion zsh

cache_eval direnv direnv hook zsh

# yazi
if command -v yazi >/dev/null 2>&1; then
  y() {
    YAZI_LAUNCH_DIR="$PWD" yazi "$@"
  }
  log "Setup" "yazi"
else
  log_error "Setup" "yazi not found"
fi

# broot — manual shell integration so broot --install never touches dotfiles
if command -v broot >/dev/null 2>&1; then
  br() {
    local tmp cmd
    tmp=$(mktemp -t "broot-outcmd.XXXXXX")
    broot --outcmd "$tmp" "$@"
    IFS= read -r -d '' cmd < "$tmp"
    rm -f -- "$tmp"
    [[ -n "$cmd" ]] && eval "$cmd"
  }
  log "Setup" "broot"
else
  log_error "Setup" "broot not found"
fi

# ------------------------------------------------------------------ #
# ZSH PLUGINS (manually cloned to ~/.config/zsh/plugins)
# ------------------------------------------------------------------ #
# NOTE: zsh-syntax-highlighting MUST be loaded last per their docs
# ZSH_PLUGINS_DIR is set in the XDG section, above the PATH setup that reads it.

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

# zsh-vi-mode — explicit clipboard model. Leave the native sync OFF so vi-mode
# yanks/deletes stay in the internal cut buffer and never touch the OS clipboard
# (deletes don't pollute clipboard history). `gp` / `gP` still paste FROM the
# system clipboard — those widgets read it regardless of this flag. On WSL the
# platform file points zvm's paste command at win32yank. Set before sourcing.
ZVM_SYSTEM_CLIPBOARD_ENABLED=false
if [[ -f "$zsh_vi_mode_file" ]]; then
  source "$zsh_vi_mode_file"
  log "Load" "$zsh_vi_mode_file"
else
  log_error "Load" "$zsh_vi_mode_file"
fi

# forgit
# forgit pipes every diff into delta, and delta cannot detect the terminal width
# through a pipe — it silently renders at a fixed 80 columns whatever the pane
# is. Pass the real width; FORGIT_IN_PREVIEW is forgit's own marker for the
# preview pane, and is more reliable here than FZF_PREVIEW_COLUMNS, which fzf
# may also export to execute() bindings. Do not switch the preview to unified to
# gain room: delta only wraps long lines in side-by-side mode, so unified runs
# them past the pane edge where fzf clips them.
export FORGIT_PAGER='delta --paging=never --width=$([ -n "$FORGIT_IN_PREVIEW" ] && echo "${FZF_PREVIEW_COLUMNS:-80}" || tput cols)'
export FORGIT_DIFF_FZF_OPTS="--preview-window='right:70%'"

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

if [[ "$ZSHRC_DEBUG" == "1" ]]; then
  printf " 🟰🟰🟰🟰🟰 ZSH Configuration Loaded in %.0fms 🟰🟰🟰🟰🟰🟰\n" \
    $(( (EPOCHREALTIME - ZSHRC_START) * 1000 ))
else
  echo " ✓ zsh loaded"
fi

# ------------------------------------------------------------------ #
# MENU REVIEW - What's Due to Revisit (Shell Startup)
# ------------------------------------------------------------------ #
# Surface the review register's due items on the first shell of each half-day
# (morning / afternoon) — at most twice a day, and only when something is due.
# The gate is a cheap marker-mtime check so the reviewer (a uv/python script)
# only spawns once per interval, never on every shell. The nudge itself is silent
# when nothing is due, so a clear day adds no startup noise. Marker and interval
# live in the synced menu state dir, so the interval is shared across machines —
# a rolling schedule (default 4h; set with `menu review nudge-every <dur>`), not
# once per machine.
if [[ -x "$HOME/.local/bin/menu-review" ]]; then
  _mr_state="${XDG_STATE_HOME:-$HOME/.local/state}/menu"
  _mr_marker="$_mr_state/nudge"
  _mr_mins="$(cat "$_mr_state/nudge-interval-minutes" 2>/dev/null || echo 240)"
  if [[ ! -f "$_mr_marker" || -n "$(find "$_mr_marker" -mmin +"$_mr_mins" 2>/dev/null)" ]]; then
    mkdir -p "$_mr_state"
    : > "$_mr_marker"  # touch: mtime = now = last-nudged
    menu-review nudge
  fi
  unset _mr_state _mr_marker _mr_mins
fi
