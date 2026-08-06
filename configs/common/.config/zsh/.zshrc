#shellcheck disable=all
# ------------------------------------------------------------------ #
# SHARED ZSH CONFIGURATION
# Platform-agnostic configuration sourced by platform-specific configs
# ------------------------------------------------------------------ #

# ------------------------------------------------------------------ #
# BOOTSTRAP: Load environment and utilities
# ------------------------------------------------------------------ #
# Sourced before anything else because .env is where every feature flag is set;
# the entry is logged further down, once log() exists to report it.
env_file="$HOME/.env"
[[ -f $env_file ]] && source $env_file

# Exported before the libraries load, not with the other exports further down:
# formatting.sh resolves colors.sh through SHELL_DIR and falls back to a
# $(dirname) fork per shell startup when it is unset.
export SHELL_DIR="$HOME/.local/shell"

# flags.sh next, because every gate below this point is a flag_enabled call.
flags_file="$SHELL_DIR/flags.sh"
[[ -f $flags_file ]] && source $flags_file

CHECK_MARK="☑️"
ERROR_MARK="❌"
flag_enabled ZSHRC_DEBUG 0 && echo " 🟰🟰🟰🟰🟰 Loading ZSH Configuration 🟰🟰🟰🟰🟰🟰"

# Columns are step and cumulative milliseconds. Timing lives inside log() rather
# than at the call sites so every existing entry reports it for free, and a
# startup stall reads as one slow step instead of having to be bisected by hand.
zmodload zsh/datetime
typeset -g ZSHRC_START=$EPOCHREALTIME
typeset -g ZSHRC_LAST=$EPOCHREALTIME

log() {
  flag_enabled ZSHRC_DEBUG 0 || return 0
  local now=$EPOCHREALTIME
  printf "  $CHECK_MARK %6.0fms %7.0fms  %-6s : %s\n" \
    $(( (now - ZSHRC_LAST) * 1000 )) $(( (now - ZSHRC_START) * 1000 )) "$1" "$2"
  ZSHRC_LAST=$now
  return 0
}
log_error() { printf "  $ERROR_MARK %-6s : %s\n" "$1" "$2" >&2 }

# Log environment
colors_file="$SHELL_DIR/colors.sh"
formatting_file="$SHELL_DIR/formatting.sh"
[[ -f $env_file ]] && log "Load" "$env_file" || log_error "Load" "$env_file"
[[ -f $flags_file ]] && log "Load" "$flags_file" || log_error "Load" "$flags_file"
[[ -f $colors_file ]] && source $colors_file && log "Load" "$colors_file" || log_error "Load" "$colors_file"
[[ -f $formatting_file ]] && source $formatting_file && log "Load" "$formatting_file" || log_error "Load" "$formatting_file"

# Shared prompt utilities (used by prompt.zsh)
prompt_lib_file="$SHELL_DIR/prompt-lib.sh"
[[ -f $prompt_lib_file ]] && source $prompt_lib_file && log "Load" "$prompt_lib_file" || log_error "Load" "$prompt_lib_file"

# Validate required environment variables
if [[ -n "$PLATFORM" ]]; then
  log "Env" "$(color_cyan "PLATFORM")=$(color_green "$PLATFORM")"
else
  log_error "Env" "PLATFORM not set in .env"
fi

# The OS cannot answer what a machine is *for*, so unlike PLATFORM this has no
# detection fallback and defaults to the majority case rather than erroring.
export MACHINE_ROLE="${MACHINE_ROLE:-personal}"
log "Env" "$(color_cyan "MACHINE_ROLE")=$(color_green "$MACHINE_ROLE")"

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

# Every binding that has to be applied after the rest of the rc file has run.
# A function rather than inline because it has two callers: zsh-vi-mode's hook
# when SHELL_VI_MODE is on, and the tail of this file when it is off. Without
# the second caller, turning vi-mode off would silently cost the arrow-key
# history search and the Claude widgets, since nothing else binds them.
apply_shell_keybindings() {
  bindkey "^[[A" up-line-or-beginning-search    # Up arrow
  bindkey "^[[B" down-line-or-beginning-search  # Down arrow
  # Re-apply fzf keybindings (Ctrl+R, Ctrl+T, Alt+C), which vi-mode has just
  # overwritten. Reads the cache written during startup rather than re-running fzf.
  cache_eval fzf fzf --zsh
  # atuin has to follow fzf here for the same reason it does at startup: both bind
  # Ctrl-R and the last one loaded wins. vi-mode runs this after the whole rc file,
  # so re-applying fzf alone handed Ctrl-R back to it and the atuin binding set
  # during startup never survived into the shell the user actually typed in.
  flag_enabled SHELL_HISTORY_DB && cache_eval atuin atuin init zsh --disable-up-arrow
  # Claude widgets, defined in the SHELL CONFIG section. Ctrl-X chords rather
  # than Meta: ^[ is vi-cmd-mode, so every Alt binding costs a KEYTIMEOUT wait
  # before Escape takes effect. ^X^A and ^X^E are the free ones — the rest of
  # the ^X space belongs to zsh's completion-debug bindings.
  bindkey "^X^A" doshell-ask-widget
  bindkey "^X^E" doshell-explain-widget
  return 0
}

# zsh-vi-mode hook: re-apply bindings after vi-mode overwrites the keymap
zvm_after_init() { apply_shell_keybindings }

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
export PAGER="bat"
# col -bx strips the backspace overstrike man page formatters still emit for
# bold (`N^HNA^HAM^HME^HE`); bat prints those bytes literally and only less
# decodes them. Filtering first leaves bat's theme as the only source of color.
# awscli reads MANPAGER before PAGER, so this fixes `aws <cmd> help` too.
export MANPAGER="sh -c 'col -bx | bat --language=man'"
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

# Rust keeps _cargo inside the toolchain rather than anywhere already on fpath,
# so it is the one completion that arrives as a file to autoload instead of as a
# generator to run. This has to precede compinit, which scans fpath once to build
# the dump — anything added after it is never registered. Stable explicitly: with
# a nightly toolchain also installed both would match, and nightly's _cargo lists
# flags the stable cargo rejects.
fpath+=(~/.rustup/toolchains/stable-*/share/zsh/site-functions(N))

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
  # `-b BIN` names the binary when it differs from the cache key, which is what
  # a tool generating two blocks needs: one key per block, both aged against the
  # one binary. doit does this — a completion and a startup nudge, loaded at
  # different points because the nudge prints.
  local bin_name=""
  [[ "$1" == -b ]] && { bin_name="$2"; shift 2; }
  local name="$1"; shift
  : "${bin_name:=$name}"
  local cache="$ZSH_COMPLETION_CACHE/$name.zsh" bin err ret
  # Its own statement: zsh expands every word of a `local` before assigning any
  # of them, so $cache on that line is still empty and this becomes ./.failed.
  local failed="$cache.failed"

  # Staleness is measured against the binary, not $1: a generator invoked as
  # `env VAR=x tool` would otherwise stat env(1), whose mtime never moves, and
  # the cache would outlive every upgrade of the tool itself.
  if ! bin="$(command -v "$bin_name")"; then
    log "Skip" "$bin_name not installed"
    return 0
  fi

  # Being on PATH does not mean the tool can generate anything: WSL ships a
  # /usr/bin/docker stub for Docker Desktop's distro integration that exits 1
  # for every subcommand, so `command -v` finds it and generation can never
  # succeed. Remember the failure against the tool that caused it, or that costs
  # a subprocess and an error line in every shell forever. The marker holds the
  # resolved target, so swapping a stub for the real binary retries even when
  # the replacement's mtime predates the marker — enabling the integration fixes
  # completion on the next shell without anything to clear by hand.
  if [[ -f "$failed" && "$(<"$failed")" == "${bin:A}" && ! "$bin" -nt "$failed" ]]; then
    log "Skip" "$name generated nothing last time"
  elif [[ ! -s "$cache" || "$bin" -nt "$cache" ]]; then
    # `2>&1 >file` splits the streams: stdout to the cache, stderr into $err.
    err="$("$@" 2>&1 >"$cache.new")"
    ret=$?
    if (( ret == 0 )) && [[ -s "$cache.new" ]]; then
      mv -f "$cache.new" "$cache"
      rm -f "$failed"
    else
      # A tool that answers an unknown subcommand with its usage text writes it
      # to stdout and exits non-zero, leaving stderr empty — report whichever
      # stream said something, and the status either way, or the failure is
      # indistinguishable from a generator that legitimately printed nothing.
      [[ -n "$err" ]] || err="$(head -n1 "$cache.new" 2>/dev/null)"
      rm -f "$cache.new"
      print -r -- "${bin:A}" >| "$failed"
      log_error "Setup" "$name: exit $ret: ${err:-generated nothing}"
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

# Own cobra tools.
cache_eval forge forge completion zsh
cache_eval todoui todoui completion zsh
cache_eval icb icb completion zsh
cache_eval learning learning completion zsh
cache_eval meso meso completion zsh
cache_eval nomad nomad completion zsh
cache_eval toolbox toolbox completion zsh
# ifiles completes remote paths by calling the server, so each Tab there is a
# request rather than a lookup. The generated script is static; the network call
# happens inside `ifiles __complete`.
cache_eval ifiles ifiles completion zsh

# Own Typer tools. The shell is named through the env var rather than with
# --show-completion, which detects it from the parent process and answers
# "Shell  not supported." when generated from anything but an interactive shell.
# Each Tab spawns Python, so these are the slow ones.
cache_eval dectl env _DECTL_COMPLETE=source_zsh dectl
cache_eval indy env _INDY_COMPLETE=source_zsh indy
cache_eval relate env _RELATE_COMPLETE=source_zsh relate
cache_eval syncer env _SYNCER_COMPLETE=source_zsh syncer

# doit writes its own rather than using Typer's generator, so that completing a
# pursuit name reads doit's flat name cache instead of spawning Python on Tab.
cache_eval doit doit completion zsh

# Third party, kept to what is typed at a prompt rather than run from a Taskfile
# or a hook. task completes task names out of the Taskfile and sesh completes
# session names, which is most of the value here.
cache_eval task task --completion zsh
cache_eval sesh sesh completion zsh
cache_eval tenv tenv completion zsh
cache_eval trivy trivy completion zsh
cache_eval yq yq completion zsh
cache_eval cheat cheat --completion zsh
cache_eval ruff ruff generate-shell-completion zsh
# docker covers `docker compose` too — the compose plugin has no completion of
# its own. brew ships no _docker, and neither does OrbStack.
cache_eval docker docker completion zsh
cache_eval rustup rustup completions zsh

log "Setup" "Completions"

# ------------------------------------------------------------------ #
# PROMPT
# ------------------------------------------------------------------ #
my_prompt="$HOME/.local/shell/prompt.zsh"
[[ -f $my_prompt ]] && source $my_prompt && log "Load" $my_prompt || log_error "Load" $my_prompt

# ------------------------------------------------------------------ #
# PLUGIN REPLACEMENTS
# ------------------------------------------------------------------ #

# colored-man-pages (LESS_TERMCAP_* + GROFF_NO_SGR=1) was removed: it forced
# groff to keep emitting overstrike so less could paint it, which is what leaked
# `^H` into every pager that is not less. bat colors from the theme now.

# ------------------------------------------------------------------ #
# SHELL CONFIG
# ------------------------------------------------------------------ #

SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"

# Shell code (symlinked from dotfiles/shell/ by symlinks manager)
[[ -f "$SHELL_DIR/functions.sh" ]] && source "$SHELL_DIR/functions.sh" && log "Load" "$SHELL_DIR/functions.sh" || log_error "Load" "$SHELL_DIR/functions.sh"
[[ -f "$SHELL_DIR/aliases.sh" ]] && source "$SHELL_DIR/aliases.sh" && log "Load" "$SHELL_DIR/aliases.sh" || log_error "Load" "$SHELL_DIR/aliases.sh"
[[ -f "$SHELL_DIR/$PLATFORM.sh" ]] && source "$SHELL_DIR/$PLATFORM.sh" && log "Load" "$SHELL_DIR/$PLATFORM.sh" || log_error "Load" "$SHELL_DIR/$PLATFORM.sh"

# Role overlay, after the platform one because a role can build on what the
# platform exported (work's aws-login reads $winchris from wsl.sh). Every role
# file is linked on every machine and MACHINE_ROLE picks one, so switching role
# is a ~/.env edit rather than a relink. Optional, like a platform overlay:
# `personal` and `server` have nothing to add yet.
role_file="$SHELL_DIR/roles/$MACHINE_ROLE.sh"
[[ -f "$role_file" ]] && source "$role_file" && log "Load" "$role_file"

# Claude on the prompt line. doshell(1) makes you decide to ask before you start
# typing; these catch you mid-line instead, which is when you actually get stuck.
# Both are deliberately explicit keypresses rather than anything ambient — a
# round trip is seconds, not milliseconds, so nothing may fire per keystroke.
# Defined here (functions.sh is loaded above) but bound in zvm_after_init,
# because vi-mode wipes the keymap after this file finishes.

# Replace the English on the line with the command that does it.
doshell-ask-widget() {
  [[ -z "$BUFFER" ]] && return
  local request="$BUFFER" suggestion
  # zle paints nothing while a widget blocks, so without this the prompt just
  # freezes for several seconds and reads as a hang.
  zle -R "⋯ asking claude"
  suggestion=$(doshell_suggest_command "$request")
  if [[ -n "$suggestion" ]]; then
    BUFFER="$suggestion"
    CURSOR=${#BUFFER}
  else
    zle -M "doshell: no command returned"
  fi
  zle -R
}
zle -N doshell-ask-widget

# The other direction: keep the line, print what it would do underneath.
doshell-explain-widget() {
  [[ -z "$BUFFER" ]] && return
  local explanation
  zle -R "⋯ asking claude"
  explanation=$(doshell_explain_command "$BUFFER")
  zle -M "${explanation:-doshell: no explanation returned}"
}
zle -N doshell-explain-widget

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

# Not cache_eval'd: `fnm env` emits a per-shell multishell directory in its
# PATH, so a cached copy would point every later shell at the first shell's
# directory, which is removed when that shell exits.
#
# --use-on-cd reads .nvmrc on entering a directory, which is the whole point:
# ichrisbirch, nomad and timeline pin 24 while meso pins 26. .zshenv already
# puts the default alias on PATH for non-interactive shells; this layers
# per-directory switching over it for interactive ones.
if command -v fnm >/dev/null 2>&1; then
  eval "$(fnm env --use-on-cd --shell zsh)"
fi

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
# audit-flow analysis. atuin owns Ctrl-R (its DB-backed search shows time, cwd,
# and exit — richer than fzf's flat fuzzy match; it overrides fzf's Ctrl-R since
# this sources after the fzf block). Up-arrow stays the prefix-search bound above
# (--disable-up-arrow) rather than atuin's launch-a-TUI-every-press. To revert
# Ctrl-R to fzf, add --disable-ctrl-r; to also hand up-arrow to atuin, drop the
# flag.
# What atuin emits here depends on ~/.config/atuin/config.toml — [ai].enabled
# decides whether it also claims `?`. cache_eval only ages the cache against the
# binary's mtime, so editing that config changes nothing until the cache entry is
# removed: rm ~/.cache/zsh/completions/atuin.zsh
flag_enabled SHELL_HISTORY_DB && cache_eval atuin atuin init zsh --disable-up-arrow

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
autosuggestions_file="$ZSH_PLUGINS_DIR/zsh-autosuggestions/zsh-autosuggestions.zsh"
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
# A flag that is off skips silently; a plugin that is wanted but missing is
# still an error, because that is a broken install rather than a preference.
if ! flag_enabled SHELL_VI_MODE; then
  log "Skip" "zsh-vi-mode (SHELL_VI_MODE)"
elif [[ -f "$zsh_vi_mode_file" ]]; then
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
# forgit interpolates this after its own defaults, so these win on conflicts —
# which is the point: ctrl-d/ctrl-u are fzf's delete-char/unix-line-discard, and
# scrolling the diff matters more than editing the query in these pickers.
export FORGIT_FZF_DEFAULT_OPTS="--bind='ctrl-d:preview-half-page-down,ctrl-u:preview-half-page-up'"
export FORGIT_DIFF_FZF_OPTS="--preview-window='right:70%'"

if ! flag_enabled SHELL_FORGIT; then
  log "Skip" "forgit (SHELL_FORGIT)"
elif [[ -f "$forgit_file" ]]; then
  source "$forgit_file"
  log "Load" "$forgit_file"
  fpath+=($forgit_completions)
  # compinit ran hundreds of lines ago and scanned fpath once, so the directory
  # alone registered nothing and `git forgit <TAB>` was silent. Autoloading the
  # function is what makes zsh's _git dispatch to it, and the compdef binds the
  # git-forgit command that forgit also puts on PATH.
  autoload -Uz _git-forgit && compdef _git-forgit git-forgit
  log "Load" "$forgit_completions"
else
  log_error "Load" "$forgit_file"
fi

# zsh-autosuggestions — inline ghost text ahead of the cursor. Distinct from
# atuin, which owns Ctrl-R: atuin is a deliberate search, this is the passive
# offer. `completion` backs `history` up so a command you have never run still
# suggests, at the cost of a completion call per keystroke.
ZSH_AUTOSUGGEST_STRATEGY=(history completion)
# Above this many characters the per-keystroke history scan is felt rather than
# free; 20 is upstream's recommendation and keeps large pastes instant.
ZSH_AUTOSUGGEST_BUFFER_MAX_SIZE=20
if ! flag_enabled SHELL_AUTOSUGGESTIONS; then
  log "Skip" "zsh-autosuggestions (SHELL_AUTOSUGGESTIONS)"
elif [[ -f "$autosuggestions_file" ]]; then
  source "$autosuggestions_file"
  log "Load" "$autosuggestions_file"
else
  log_error "Load" "$autosuggestions_file"
fi

# zsh-syntax-highlighting (MUST load last)
if ! flag_enabled SHELL_SYNTAX_HIGHLIGHTING; then
  log "Skip" "zsh-syntax-highlighting (SHELL_SYNTAX_HIGHLIGHTING)"
elif [[ -f "$syntax_highlighting_file" ]]; then
  source "$syntax_highlighting_file"
  log "Load" "$syntax_highlighting_file"
else
  log_error "Load" "$syntax_highlighting_file"
fi

# vi-mode calls apply_shell_keybindings from its own post-init hook. With the
# flag off nothing would, so the arrow-key history search and the Claude widgets
# have to be bound here instead — after the widgets above exist.
flag_enabled SHELL_VI_MODE || apply_shell_keybindings

if flag_enabled ZSHRC_DEBUG 0; then
  printf " 🟰🟰🟰🟰🟰 ZSH Configuration Loaded in %.0fms 🟰🟰🟰🟰🟰🟰\n" \
    $(( (EPOCHREALTIME - ZSHRC_START) * 1000 ))
else
  echo " ✓ zsh loaded"
fi

# ------------------------------------------------------------------ #
# DOIT REVIEW - What's Due to Revisit (Shell Startup)
# ------------------------------------------------------------------ #
# Surface the review register's due items on the first shell of each interval —
# only when something is due, so a clear day adds no startup noise. The gate is
# a marker-mtime check, so doit itself spawns once per interval rather than once
# per shell. Marker and interval live in the synced doit state dir, making the
# rolling schedule (default 4h; set with `doit review nudge-every <dur>`) shared
# across machines rather than per machine.
#
# doit owns the block and this only caches it: the gate is generated with an
# absolute state path resolved on the machine that generated it, so it must not
# be committed here. Cached rather than eval'd for the reason every generator in
# this file is — an eval would put a Python start in front of every shell.
#
# An `if` rather than `flag_enabled && cache_eval`: this is the last line of the
# file, and the && form would leave .zshrc exiting non-zero whenever the flag is
# off, which the prompt renders as a failed command on the first line.
if flag_enabled SHELL_NUDGE; then
  cache_eval -b doit doit-nudge doit shell-init zsh
fi
