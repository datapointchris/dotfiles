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
# Guarded, and one of the three that stays: `~/.env` is written by `dotfiles env
# apply`, a different resource from the one that deploys this file, and
# `install.sh` reads MACHINE out of it before either has run. A shell before the
# first apply is bootstrap ordering rather than a fault to report.
env_file="$HOME/.env"
[[ -f $env_file ]] && source $env_file

# Exported before the libraries load, not with the other exports further down:
# formatting.sh resolves colors.sh through SHELL_DIR and falls back to a
# $(dirname) fork per shell startup when it is unset.
export SHELL_DIR="$HOME/.local/shell"

# flags.sh next, because every gate below this point is a flag_enabled call.
# Unguarded: it is deployed by the same `symlinks apply` that deploys this file,
# so a shell running here has it.
flags_file="$SHELL_DIR/flags.sh"
source $flags_file

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

# Log environment. The two already sourced above are logged here, now that log()
# exists; `~/.env` only when it was there, because absent is legitimate for it
# alone.
colors_file="$SHELL_DIR/colors.sh"
formatting_file="$SHELL_DIR/formatting.sh"
[[ -f $env_file ]] && log "Load" "$env_file"
log "Load" "$flags_file"
source $colors_file && log "Load" "$colors_file"
source $formatting_file && log "Load" "$formatting_file"

# Shared prompt utilities (used by prompt.zsh)
prompt_lib_file="$SHELL_DIR/prompt-lib.sh"
source $prompt_lib_file && log "Load" "$prompt_lib_file"

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
  # Prompt-line widgets, defined in the SHELL CONFIG section. Ctrl-X chords
  # rather than Meta: ^[ is vi-cmd-mode, so every Alt binding costs a KEYTIMEOUT
  # wait before Escape takes effect. ^X^A, ^X^E and ^X^D are undefined-key in
  # zsh's emacs keymap with and without compinit; most of the rest of the ^X
  # space is taken, and ^X^K — the obvious pick for a picker — is kill-buffer.
  bindkey "^X^A" doshell-ask-widget
  bindkey "^X^E" doshell-explain-widget
  bindkey "^X^D" doit-choose-widget
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

# Not $XDG_STATE_HOME, which typos would otherwise default to: these sessions are
# a typing record worth keeping across a rebuild, and ~/shart is the Syncthing
# folder that already replicates and backs up. Declared here rather than in the
# nvim spec because the capture plugin and the `typos` CLI both read it, and they
# have to agree on one path.
export TYPOS_DATA_DIR="$HOME/shart/typing"

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
# `no` rather than `select`: selection turned the second Tab into an interactive
# highlighted picker that inserts the first candidate, so backing out of it costs
# a backspace. `no` also overrides AUTO_MENU, which would otherwise cycle
# candidates into the line. Repeated Tab now just re-lists.
zstyle ':completion:*' menu no
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
  # a tool generating more than one block needs: one key per block, all aged
  # against the one binary. doit does this, and its blocks load at different
  # points in this file because only the nudge prints.
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
cache_eval doit doit shell completion zsh

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
source $my_prompt && log "Load" $my_prompt

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

# Shell code, deployed by `dotfiles symlinks apply`. Sourced without testing that
# any of it is there: what should exist is the declaration's question, and
# `dotfiles symlinks check` answers it by name — `shell/common/aliases.sh` is
# missing, and where it should be. A guard here can only say a path is absent to
# someone already sitting at the shell, and cannot say what was meant to fill it.
source "$SHELL_DIR/functions.sh" && log "Load" "$SHELL_DIR/functions.sh"
source "$SHELL_DIR/aliases.sh" && log "Load" "$SHELL_DIR/aliases.sh"

# The coordinate layers, read off the disk rather than off a list. `symlinks
# apply` deploys only the directories this machine's coordinates select and
# prunes the ones it no longer does, so this tree is the resolved answer and
# needs no second copy in `~/.env` to disagree with.
# The (N) qualifier makes an unmatched glob expand to nothing rather than
# erroring — a machine whose every axis matches `common/` has no nested layer at
# all, which is normal.
for layer_file in "$SHELL_DIR"/*/*/*.sh(N); do
  source "$layer_file" && log "Load" "$layer_file"
done
unset layer_file

# Machine-local overlay, last so it can build on what the platform exported (the
# work box's aws-login reads $winchris from wsl.sh). A real file, not a symlink:
# it holds shell code that deliberately never enters this repo — employer
# hostnames and the like — and it is restored by safekeep rather than installed.
# `relink` only removes symlinks that resolve into the repo, so it survives
# untouched. Absent on every machine that does not declare one, and the last of
# the three guards that stays: this file is restored, never deployed, so
# `symlinks check` has nothing to say about it and its absence is not drift.
local_file="$SHELL_DIR/local.sh"
[[ -f "$local_file" ]] && source "$local_file" && log "Load" "$local_file"

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

# The line-editor half of `doit choose`: a ZLE widget that apply_shell_keybindings
# binds, plus dochoose for the same pick without a chord. A subprocess cannot
# reach into its parent's line editor, so doit emits the block and this only
# caches it — the same split the completion and the startup nudge already use,
# and `-b doit` ages its own cache key against the one binary.
#
# Here rather than among the completions because this is a prompt-line widget,
# and it sits with the two it is bound beside. Ungated, unlike the nudge: this
# only defines two functions, and a keybinding that disappears when a reminder
# toggle is turned off is a keybinding nobody trusts.
cache_eval -b doit doit-widgets doit shell widgets zsh

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
you_should_use_file="$ZSH_PLUGINS_DIR/zsh-you-should-use/you-should-use.plugin.zsh"
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

# clisteno — what is on the line, and the fast way to type it.
#
# Complementary to zsh-autosuggestions rather than competing with it: that owns
# the inline space ahead of the cursor, this owns the line under the prompt, and
# neither needs a keystroke. Type the long form and it offers the short one;
# type the short one and it says what that command does.
#
# `zle -M` rather than RPROMPT. A line-pre-redraw widget is documented not to
# call `zle reset-prompt`, and measured here it does not repaint at all — the
# hook fires on every keystroke and the right margin never changes. -M paints.
#
# Nothing forks per keystroke. A tool's index is read once per shell into an
# assoc array through the `read` builtin, and every keystroke after that is a
# hash lookup — the same rule this file states for the doshell widgets.
typeset -g _clisteno_shown=''
typeset -gA _clisteno_meaning _clisteno_sequence _clisteno_loaded

_clisteno_load() {
  local tool=$1 file typed command summary key
  [[ -n ${_clisteno_loaded[$tool]} ]] && return
  # Marked before the readability check, so a tool with no index is looked for
  # once rather than stat-ed on every keystroke for the life of the shell.
  _clisteno_loaded[$tool]=1
  file="${XDG_CACHE_HOME:-$HOME/.cache}/clisteno/${tool}.tsv"
  [[ -r $file ]] || return
  # The key goes into a variable and the subscript is left unquoted: zsh reads a
  # quoted subscript literally, so arr["a b"] stores the quotes as part of the
  # key and every later lookup silently misses.
  while IFS=$'\t' read -r typed command summary; do
    key="$tool $typed"
    _clisteno_meaning[$key]=$summary
    key="$command"
    _clisteno_sequence[$key]=$typed
  done <$file
}

# The shallowest command the line could still become, when exactly one qualifies.
# Without this the hint only fires on exact boundaries, which makes it a receipt
# for what was typed rather than an offer about what is being typed: `dectl exa`
# showed nothing, and `exg` never appeared until `glue` was already complete.
# `(I)` matches keys inside the shell rather than looping over them, and `(b)`
# stops a `*` or `[` in the buffer being read as pattern. Answers in REPLY: a
# printing function has to be read back through `$(...)`, which forks per
# keystroke and cost 0.68ms against 0.10ms for the same work assigned.
_clisteno_best() {
  REPLY=''
  local -a matches
  matches=(${(k)_clisteno_sequence[(I)${(b)1}*]})
  local best='' candidate count=0 fewest=0 depth
  for candidate in $matches; do
    depth=${#${(z)candidate}}
    if (( fewest == 0 || depth < fewest )); then
      fewest=$depth
      best=$candidate
      count=1
    elif (( depth == fewest )); then
      # A tie is a genuine fork — `dectl e` is still both env and
      # example-pipeline — and answering it with either is a guess.
      (( count++ ))
    fi
  done
  (( count == 1 )) && REPLY=$best
}

_clisteno_hint() {
  local -a words
  # REPLY is scoped here so _clisteno_best writes the caller's local rather than
  # clobbering the global every keystroke.
  local REPLY
  words=(${(z)BUFFER})
  local shown=''
  if (( ${#words} >= 2 )); then
    _clisteno_load $words[1]
    local line="${(j: :)words}"
    local offer=${_clisteno_sequence[$line]}
    local meaning=${_clisteno_meaning[$line]}
    if [[ -n $offer ]]; then
      shown="⌁ ${words[1]} ${offer}"
    elif [[ -n $meaning ]]; then
      shown="$meaning"
    else
      _clisteno_best "$line"
      [[ -n $REPLY ]] && shown="⌁ ${words[1]} ${_clisteno_sequence[$REPLY]}"
    fi
  fi
  # Only on change, but including empty: the message survives until something
  # replaces it, so skipping a real change leaves the previous command's summary
  # under a line that no longer means it — while repainting an unchanged one
  # erases the completion list, which zsh draws in this same area. The hook fires
  # on the redraw a Tab causes, so an unconditional -M wiped every listing the
  # instant it appeared.
  if [[ $shown != $_clisteno_shown ]]; then
    _clisteno_shown=$shown
    zle -M "$shown"
  fi
}

if flag_enabled SHELL_CLISTENO; then
  autoload -Uz add-zle-hook-widget
  zle -N _clisteno_hint
  add-zle-hook-widget line-pre-redraw _clisteno_hint
  log "Setup" "clisteno hint"
else
  log "Skip" "clisteno hint (SHELL_CLISTENO)"
fi

# zsh-you-should-use — the alias that already existed for what was just typed.
#
# Distinct from clisteno above rather than a second copy of it: clisteno indexes
# a *tool's* own subcommand short forms from its TSV, while this reads the shell's
# alias table. `git status` earns the `gst` reminder here precisely because
# clisteno has no index for it.
#
# `after` buffers the reminder and flushes it from precmd instead of writing it
# during preexec, so the nudge lands once the command has already run and never
# delays or interrupts what was typed.
YSU_MESSAGE_POSITION=after

# `gp` and `gl` were never adopted rather than being missed, so a reminder about
# them teaches a habit instead of enforcing one. Measured over August 2026:
# `git pull` typed 10 times and `git push` 4, against zero uses of either alias,
# while `gst` won 17 to 2 and needs no help. Ignoring the two keeps the nudge for
# aliases added later, which is the only thing it is any use for here.
YSU_IGNORED_ALIASES=(gp gl)
if ! flag_enabled SHELL_YOU_SHOULD_USE; then
  log "Skip" "zsh-you-should-use (SHELL_YOU_SHOULD_USE)"
elif [[ -f "$you_should_use_file" ]]; then
  source "$you_should_use_file"
  log "Load" "$you_should_use_file"
else
  log_error "Load" "$you_should_use_file"
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
  cache_eval -b doit doit-nudge doit shell init zsh
fi

# Fires on an Issue only — a checker that could not run, a declaration that will
# not parse — never on drift, which is the normal state of a machine between
# applies and would train the nudge away inside a week. The snippet reads a file
# the scheduled check writes; nothing here runs a check at a prompt.
if flag_enabled DOTFILES_NUDGE; then
  cache_eval -b dotfiles dotfiles-nudge dotfiles shell-init zsh
fi
