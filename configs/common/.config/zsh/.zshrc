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

# Two caches, and the difference is who reads them.
#
# `ZSH_COMPLETION_FPATH` holds completion functions, one file per tool, named
# `_<tool>` the way zsh's own completion system names them. compinit indexes the
# directory and each function's body is read the first time a Tab asks for it —
# never at startup. `ruff` and `uv` are 668K and 516K of generated clap
# definitions, so sourcing the pair cost 53ms of a 160ms start, and the whole set
# is over a megabyte parsed per shell for functions most shells never call.
#
# `ZSH_COMPLETION_CACHE` holds the blocks that are not completions — zoxide's
# `cd` wrapper, direnv's hook, fzf's keybindings, atuin's init, doit's widgets.
# Those define aliases, hooks and keybindings that have to exist before the first
# prompt, so they are sourced where they sit and their order is load-bearing.
ZSH_COMPLETION_FPATH="$XDG_CACHE_HOME/zsh/functions"
ZSH_COMPLETION_CACHE="$XDG_CACHE_HOME/zsh/completions"
[[ -d "$ZSH_COMPLETION_FPATH" ]] || mkdir -p "$ZSH_COMPLETION_FPATH"
[[ -d "$ZSH_COMPLETION_CACHE" ]] || mkdir -p "$ZSH_COMPLETION_CACHE"

# Regenerate `$2` from the generator in `$3...` when the binary that produces it
# is newer, and say nothing when there is nothing to say. `$1` is the binary to
# age against and to look for, which differs from the output path whenever a tool
# generates more than one block. Answers 0 when a usable file is on disk.
#
# Staleness is measured against the binary rather than against the generator's
# first word: `env VAR=x tool` would otherwise stat env(1), whose mtime never
# moves, and the cache would outlive every upgrade of the tool itself.
cache_generate() {
  local bin_name="$1" out="$2"; shift 2
  local bin err ret
  # Its own statement: zsh expands every word of a `local` before assigning any
  # of them, so $out on that line is still empty and this becomes ./.failed.
  local failed="$out.failed"

  if ! bin="$(command -v "$bin_name")"; then
    log "Skip" "$bin_name not installed"
    return 1
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
    log "Skip" "$bin_name generated nothing last time"
  elif [[ ! -s "$out" || "$bin" -nt "$out" ]]; then
    # `2>&1 >file` splits the streams: stdout to the file, stderr into $err.
    err="$("$@" 2>&1 >"$out.new")"
    ret=$?
    if (( ret == 0 )) && [[ -s "$out.new" ]]; then
      mv -f "$out.new" "$out"
      rm -f "$failed"
    else
      # A tool that answers an unknown subcommand with its usage text writes it
      # to stdout and exits non-zero, leaving stderr empty — report whichever
      # stream said something, and the status either way, or the failure is
      # indistinguishable from a generator that legitimately printed nothing.
      [[ -n "$err" ]] || err="$(head -n1 "$out.new" 2>/dev/null)"
      rm -f "$out.new"
      print -r -- "${bin:A}" >| "$failed"
      log_error "Setup" "${out:t}: exit $ret: ${err:-generated nothing}"
    fi
  fi

  # A failed regeneration above still leaves the previous file usable.
  [[ -s "$out" ]]
}

# A completion function on fpath, for compinit to index and zsh to autoload.
# Nothing is sourced here, so the size of what a tool generates costs the shell
# nothing — which is the whole reason these are split from cache_eval.
cache_completion() {
  local name="$1"; shift
  cache_generate "$name" "$ZSH_COMPLETION_FPATH/_$name" "$@" && log "Setup" "$name"
  return 0
}

# A block that is not a completion, sourced where it sits. `-b BIN` names the
# binary when it differs from the cache key, which is what a tool generating more
# than one block needs: one key per block, all aged against the one binary.
cache_eval() {
  local bin_name=""
  [[ "$1" == -b ]] && { bin_name="$2"; shift 2; }
  local name="$1"; shift
  : "${bin_name:=$name}"
  local cache="$ZSH_COMPLETION_CACHE/$name.zsh"

  if cache_generate "$bin_name" "$cache" "$@"; then
    source "$cache"
    log "Setup" "$name"
  fi
  return 0
}

# Every completion is generated before compinit, because compinit scans fpath
# once to build its dump and a file written afterwards is never registered. A
# tool upgraded since the last shell rewrites its function here, which moves the
# directory's mtime, which is what makes compinit rebuild rather than reuse — so
# the one shell after an upgrade pays for the rebuild and no other shell does.
cache_completion gh gh completion -s zsh

# Own cobra tools.
cache_completion forge forge completion zsh
cache_completion todoui todoui completion zsh
cache_completion icb icb completion zsh
cache_completion learning learning completion zsh
cache_completion meso meso completion zsh
cache_completion nomad nomad completion zsh
# ifiles completes remote paths by calling the server, so each Tab there is a
# request rather than a lookup. The generated script is static; the network call
# happens inside `ifiles __complete`.
cache_completion ifiles ifiles completion zsh

# Own Typer tools. The shell is named through the env var rather than with
# --show-completion, which detects it from the parent process and answers
# "Shell  not supported." when generated from anything but an interactive shell.
# Each Tab spawns Python, so these are the slow ones.
cache_completion dectl env _DECTL_COMPLETE=source_zsh dectl
cache_completion indy env _INDY_COMPLETE=source_zsh indy
cache_completion relate env _RELATE_COMPLETE=source_zsh relate
cache_completion syncer env _SYNCER_COMPLETE=source_zsh syncer

# doit writes its own rather than using Typer's generator, so that completing a
# pursuit name reads doit's flat name cache instead of spawning Python on Tab.
cache_completion doit doit shell completion zsh

# Third party, kept to what is typed at a prompt rather than run from a Taskfile
# or a hook. task completes task names out of the Taskfile and sesh completes
# session names, which is most of the value here.
cache_completion task task --completion zsh
cache_completion sesh sesh completion zsh
cache_completion tenv tenv completion zsh
cache_completion trivy trivy completion zsh
cache_completion yq yq completion zsh
cache_completion cheat cheat --completion zsh
cache_completion ruff ruff generate-shell-completion zsh
cache_completion uv uv generate-shell-completion zsh
# docker covers `docker compose` too — the compose plugin has no completion of
# its own. brew ships no _docker, and neither does OrbStack.
cache_completion docker docker completion zsh
cache_completion rustup rustup completions zsh

log "Setup" "Completions"

# The generated functions above, plus the one completion that arrives as a file
# rather than as a generator: Rust keeps _cargo inside the toolchain, where
# nothing else on fpath reaches. Stable explicitly — with a nightly toolchain
# also installed both would match, and nightly's _cargo lists flags the stable
# cargo rejects.
fpath=("$ZSH_COMPLETION_FPATH" ~/.rustup/toolchains/stable-*/share/zsh/site-functions(N) $fpath)

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

# bashcompinit and `complete -C` are a bash bridge rather than a zsh function, so
# terraform cannot go on fpath with the rest and has to follow compinit.
if command -v terraform >/dev/null 2>&1; then
    autoload -U +X bashcompinit && bashcompinit
    complete -o nospace -C terraform terraform
    log "Setup" "terraform completions"
fi

# ------------------------------------------------------------------ #
# PROMPT
# ------------------------------------------------------------------ #
my_prompt="$HOME/.local/shell/prompt.zsh"
source $my_prompt && log "Load" $my_prompt

# ------------------------------------------------------------------ #
# PLUGIN REPLACEMENTS
# ------------------------------------------------------------------ #

# No colored-man-pages (LESS_TERMCAP_* + GROFF_NO_SGR=1): it forces groff to keep
# emitting overstrike so less can paint it, which leaks `^H` into every pager that
# is not less. bat colors come from the theme instead.

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

# Machine-local file, last so it can build on what the layers exported (the
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
# caches it — the same split doit's completion block uses, and `-b doit` ages its
# own cache key against the one binary.
#
# Here rather than among the completions because this is a prompt-line widget,
# and it sits with the two it is bound beside. Ungated: this only defines two
# functions, and it prints nothing until a key is pressed.
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
else
  add_path "/snap/bin"
fi

# Go is not platform-specific: go.dev's macOS installer and this repo's tarball
# both unpack to /usr/local/go, and providers/toolchain.py has no branch for it.
# These two sat in the else-branch from when macOS took Go from brew, and stayed
# after that stopped being true — so no Mac shell could reach `go` at all.
# Ahead of tier 3, so the repo's toolchain wins over a distro /usr/bin/go.
add_path "/usr/local/go/bin"
add_path "$HOME/go/bin"

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

cache_eval direnv direnv hook zsh

# An integration below is offered, not required: a manifest that never declares
# the tool is a machine that does not want it, so its absence is a skip and not
# a fault. log_error writes whatever ZSHRC_DEBUG says, while log stays quiet, so
# reporting an absence through log_error puts a line on every start of every
# shell that a reader can do nothing about — and teaches them to stop reading
# stderr, which is where the real faults go. Measured 2026-08-16 on
# scheduler-lxc, whose manifest declares neither yazi nor broot.
#
# The flag-gated plugin blocks further down are a different case and stay as
# they are: a plugin whose flag is on and whose file is missing is a machine
# that asked for something and did not get it.

# yazi
if command -v yazi >/dev/null 2>&1; then
  y() {
    YAZI_LAUNCH_DIR="$PWD" yazi "$@"
  }
  log "Setup" "yazi"
else
  log "Skip" "yazi (not installed)"
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
  log "Skip" "broot (not installed)"
fi

# worktree — a child process cannot move the shell that spawned it, so `choose`
# prints the path and this is what walks into it. Named apart from the binary
# rather than wrapping it: `worktree` is already a git subcommand, and a function
# shadowing it would make `worktree remove` fail somewhere new.
if command -v worktree >/dev/null 2>&1; then
  wt() {
    local chosen
    chosen=$(worktree choose "$@") || return
    # Backing out of the picker is a decision, not a failure. Returning the empty
    # test's 1 would light the prompt's status indicator every time.
    [[ -n "$chosen" ]] || return 0
    cd "$chosen"
  }
  log "Setup" "worktree"
else
  log "Skip" "worktree (not installed)"
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
fi
