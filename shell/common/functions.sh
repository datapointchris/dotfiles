# shellcheck shell=bash
# shellcheck disable=all
# SC2016 = fzf preview commands use single quotes intentionally
# SC2154 = Variables referenced but not assigned (from sourced files)
# disable=all applied for fzf external functions compatibility

SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
source "$SHELL_DIR/colors.sh"

#@package-lambda
#--> package-lambda name_of_function.py [requirements.txt]
function package-lambda() {
  if [ $# -eq 0 ]; then
    echo "Usage: package-lambda name_of_function.py [requirements.txt]"
    echo "name_of_function.py is required"
    echo "Specify location of requirements.txt as second argument if different from project root"
    return 1
  fi
  echo "Using $(python -V) $(which python)"
  echo "Removing deploy_package.zip and ./package folder"
  rm -f deploy_package.zip
  rm -rf ./package
  # If flag is not no-requirements
  if [ "$2" != "no-requirements" ]; then
    echo "Installing requirements into ./package directory..."
    mkdir -p package
    # If requirements.txt location supplied
    if [ -n "$2" ]; then
      pip install -r "$2" --target package/ --upgrade --quiet
    # otherwise find it in root
    else
      pip install -r "$(git rev-parse --show-toplevel)/requirements.txt" --target package/ --upgrade --quiet
    fi
    cd package || exit
    echo "Zipping up package..."
    zip -r --quiet ../deploy_package.zip . -x \*__pycache__\*
    cd .. || exit
  else
    echo "Not installing any requirements"
  fi
  echo "Adding function to zip..."
  # If function is named other than lambda_function.py copy into zip then delete
  if [ "$1" != "lambda_function.py" ]; then
    cp "$1" lambda_function.py
    zip --quiet deploy_package.zip lambda_function.py
    rm lambda_function.py
  else
    zip --quiet deploy_package.zip lambda_function.py
  fi
  echo "deploy_package.zip $(du -sh deploy_package.zip | awk '{print $1}')"
}

#@make-lambda-layer
#--> make-lambda-layer name_of_function.py [requirements.txt]
function make-lambda-layer() {
  if [ $# -lt 2 ]; then
    echo "Usage: make-lambda-layer layer-name [packages]"
    echo "Layer name and at least one package is required"
    return 1
  fi
  layer_name="$1"
  shift
  echo "Using $(python -V) $(which python)"
  mkdir python
  echo "Installing packages into ./python directory..."
  pip install "$@" --target python/ --upgrade --quiet
  echo "Zipping up layer..."
  zip -r --quiet "$layer_name.zip" python/
  echo "Deleting python directory..."
  rm -rf python
  du -sh "$layer_name.zip"

}

#@ubuntu-docker
#--> Make a new Ubuntu Docker container and ssh into it
function ubuntu-docker() {
  container_id=$(docker run -itd ubuntu)
  docker exec -it "$container_id" bash
}

#@findup
#--> Find file or directory searching up
function findup() {
  dirpath=$(pwd)
  while [[ "$dirpath" != "" && ! -e "$dirpath/$1" ]]; do
    dirpath=${dirpath%/*}
  done
  echo "$dirpath"
}

#@mkd
#--> Create a new directory and enter it
function mkd() {
  mkdir -p "$1" && cd "$1" || exit
}

#@cl
#--> Move to new directory and list contents
function cl() {
  cd "$1" && ls
}

#@pkill
#--> Kill process by name
function pkill() {
  local pid
  pid=$(ps aux | fzf --height 40% \
    --layout=reverse \
    --header-lines=1 \
    --prompt="Select process to kill: " \
    --preview 'echo {}' \
    --preview-window up:3:hidden:wrap \
    --bind 'F2:toggle-preview' | awk '{print $2}')

  [[ -z "$pid" ]] && return

  if ! kill "$pid" 2>/dev/null; then
    echo "Regular kill failed. Attempting with sudo..."
    sudo kill "$pid" || echo "Failed to kill process $pid" >&2
  fi
}

#@touchdate
#--> Make new file prefixed with date
function touchdate() {
  touch "$(date +"%Y-%m-%d_%H%M%S")-$1"
}

#@sizeof
#--> Determine size of a file or total size of a directory
function sizeof() {
  if du -b /dev/null >/dev/null 2>&1; then
    local arg=-sbh
  else
    local arg=-sh
  fi
  if [[ -n "$*" ]]; then
    du $arg -- "$@"
  else
    du $arg .[^.]* ./*
  fi
}

#@gzipsize
#--> Compare original and gzipped file size
function gzipsize() {
  local origsize
  local gzipsize
  local ratio
  origsize=$(wc -c <"$1")
  gzipsize=$(gzip -c "$1" | wc -c)
  ratio=$(echo "$gzipsize * 100 / $origsize" | bc -l)
  printf "orig: %d bytes\n" "$origsize"
  printf "gzip: %d bytes (%2.2f%%)\n" "$gzipsize" "$ratio"
}

#@extract
#--> Auto extract any type of file
function extract() {
  if [[ -f $1 ]]; then
    case $1 in
      *.tar.bz2) tar -xjf "$1" ;;
      *.tar.gz) tar -xzf "$1" ;;
      *.tar.zsr) tar --use-compress-program=unzstd -xvf "$1" ;;
      *.rar) unrar -e "$1" ;;
      *.gz) gunzip "$1" ;;
      *.tar) tar -xf "$1" ;;
      *.tbz2) tar -xjf "$1" ;;
      *.tgz) tar -xzf "$1" ;;
      *.zip) unzip "$1" ;;
      *.Z) uncompress "$1" ;;
      *) echo "'$1' cannot be extracted via ´ex´" ;;
    esac
  else
    echo "'$1' is not a valid file"
  fi
}

# Use Git's colored diff when available
if hash git &>/dev/null; then
  function diff() {
    git diff --no-index --color-words "$@"
  }
fi

#@server
#--> Start an HTTP server from a directory, port 2222
function server() {
  python -m http.server 2222 &
  sleep 1 && open "http://localhost:2222"
}

#@f
#--> Pick a command's path/file args with fzf, e.g. f vim (choose files) or f cd (choose dir)
f() {
  # Run command/application and choose paths/files with fzf.
  # Always return control of the terminal to user (e.g. when opening GUIs).
  # The full command that was used will appear in your history just like any
  # other (N.B. to achieve this I write the shell's active history to
  # ~/.bash_history)
  #
  # Usage:
  # f cd [OPTION]... (hit enter, choose path)
  # f cat [OPTION]... (hit enter, choose files)
  # f vim [OPTION]... (hit enter, choose files)
  # f vlc [OPTION]... (hit enter, choose files)

  # Store the program
  program="$1"

  # Remove first argument off the list
  shift

  # Store option flags with separating spaces, or just set as single space
  options="$@"
  if [ -z "${options}" ]; then
    options=" "
  else
    options=" $options "
  fi

  # Store the arguments from fzf
  arguments="$(fzf --multi)"

  # If no arguments passed (e.g. if Esc pressed), return to terminal
  if [ -z "${arguments}" ]; then
    return 1
  fi

  # We want the command to show up in our bash history, so write the shell's
  # active history to ~/.bash_history. Then we'll also add the command from
  # fzf, then we'll load it all back into the shell's active history
  history -w

  # ADD A REPEATABLE COMMAND TO THE BASH HISTORY ############################
  # Store the arguments in a temporary file for sanitising before being
  # entered into bash history
  : >/tmp/fzf_tmp
  for file in "${arguments[@]}"; do
    echo "$file" >>/tmp/fzf_tmp
  done

  # Put all input arguments on one line and sanitise the command by putting
  # single quotes around each argument, also first put an extra single quote
  # next to any pre-existing single quotes in the raw argument
  sed -i "s/'/''/g; s/.*/'&'/g; s/\n//g" /tmp/fzf_tmp

  # If the program is on the GUI list, add a '&' to the command history
  if [[ "$program" =~ ^(nautilus|zathura|evince|vlc|eog|kolourpaint)$ ]]; then
    sed -i '${s/$/ \&/}' /tmp/fzf_tmp
  fi

  # Grab the sanitised arguments
  arguments="$(cat /tmp/fzf_tmp)"

  # Add the command with the sanitised arguments to our .bash_history
  echo $program$options$arguments >>~/.bash_history

  # Reload the ~/.bash_history into the shell's active history
  history -r

  # EXECUTE THE LAST COMMAND IN ~/.bash_history #############################
  fc -s -1

  # Clean up temporary variables
  rm /tmp/fzf_tmp
}

# alternative using ripgrep-all (rga) combined with fzf-tmux preview
# This requires ripgrep-all (rga) installed: https://github.com/phiresky/ripgrep-all
# This implementation below makes use of "open" on macOS, which can be replaced by other commands if needed.
# allows to search in PDFs, E-Books, Office documents, zip, tar.gz, etc. (see https://github.com/phiresky/ripgrep-all)
# find-in-file - usage: fif <searchTerm> or fif "string with spaces" or fif "regex"
#@fif
#--> Find in file contents with ripgrep-all + fzf, then open the match. Usage: fif <term>
fif() {
  if [ ! "$#" -gt 0 ]; then
    echo "Need a string to search for!"
    return 1
  fi
  local file
  file="$(rga --max-count=1 --ignore-case --files-with-matches --no-messages "$*" | fzf-tmux +m --preview="rga --ignore-case --pretty --context 10 '"$*"' {}")" && echo "opening $file" && open "$file" || return 1
}

# fgst - pick files from `git status -s`
is_in_git_repo() {
  git rev-parse HEAD >/dev/null 2>&1
}

#@fgst
#--> Fuzzy-pick changed files from git status (to stage or pipe)
fgst() {
  # "Nothing to see here, move along"
  is_in_git_repo || return

  local cmd="${FZF_CTRL_T_COMMAND:-"command git status -s"}"

  eval "$cmd" | FZF_DEFAULT_OPTS="--height ${FZF_TMUX_HEIGHT:-40%} --reverse $FZF_DEFAULT_OPTS $FZF_CTRL_T_OPTS" fzf -m "$@" | while read -r item; do
    echo "$item" | awk '{print $2}'
  done
  echo
}

# gh-watch -- watch the current actions
#@gh-watch
#--> Pick an in-progress GitHub Actions run on this branch and watch it live
gh-watch() {
  gh run list \
    --branch $(git rev-parse --abbrev-ref HEAD) \
    --json status,name,databaseId \
    | jq -r '.[] | select(.status != "completed") | (.databaseId | tostring) + "\t" + (.name)' \
    | fzf -1 -0 | awk '{print $1}' | xargs gh run watch
}

# Ask git rather than read a config file. git resolves system, global, local and
# every [include]/[includeIf] in the chain, so this reports the aliases actually
# in effect here — including a repo-local one, which no single file can show. The
# version this replaced grepped ~/.gitconfig, which the XDG move deleted, and
# took 50 lines of context after [alias] whether there were 7 or 70.
#@git-alias
#--> Every git alias in effect here, from every config scope
git-alias() {
  local blue=$'\033[34m' reset=$'\033[0m' width
  width=$(git config --name-only --get-regexp '^alias\.' | sed 's/^alias\.//' | wc -L)
  git config --get-regexp '^alias\.' | sort | while read -r key body; do
    printf '%-*s  %s%s%s\n' "$width" "${key#alias.}" "$blue" "$body" "$reset"
  done
}

# tm - create new tmux session, or switch to existing one. Works from within tmux too. (@bag-man)
# `tm` will allow you to select your tmux session via fzf.
# `tm irc` will attach to the irc session (if it exists), else it will create it.

#@tm
#--> Switch or create tmux sessions via fzf; tm <name> attaches or creates it
tm() {
  [[ -n "$TMUX" ]] && change="switch-client" || change="attach-session"
  if [ $1 ]; then
    tmux $change -t "$1" 2>/dev/null || (tmux new-session -d -s $1 && tmux $change -t "$1")
    return
  fi
  session=$(tmux list-sessions -F "#{session_name}" 2>/dev/null | fzf --exit-0) && tmux $change -t "$session" || echo "No sessions found."
}

# sesh wrapper: warm up tmux + run resurrect restore synchronously before the
# first sesh attach. Replaces @continuum-boot (which started tmux under systemd
# pre-graphical-session, losing HYPRLAND_INSTANCE_SIGNATURE/WAYLAND_DISPLAY) and
# @continuum-restore (which ran restore backgrounded and raced sesh's attach).
# Inside tmux, the server is already up so this is a no-op passthrough.
# tmux's own run-shell spawns a non-interactive shell that does not source this
# file, so keybinds inside tmux continue to call the real sesh binary directly.
sesh() {
  if ! command tmux info >/dev/null 2>&1; then
    local restore="$HOME/.config/tmux/plugins/tmux-resurrect/scripts/restore.sh"
    if [ -x "$restore" ]; then
      # resurrect's new_session() calls `tmux -S "$(tmux_socket)"` where tmux_socket()
      # parses $TMUX for the socket path. Outside a tmux client $TMUX is unset, so
      # `tmux -S ""` silently fails and no sessions are ever created.
      # Predict the default socket path and inject it. When restore.sh calls
      # new-session and no server exists yet, tmux auto-starts the server and loads
      # tmux.conf — so explicit start-server + source-file are not needed.
      local uid
      uid=$(id -u)
      # Stderr suppressed: no-client errors from resurrect's spinner and switch-client
      # are cosmetic; session/window/pane creation works headlessly.
      TMUX="${TMUX_TMPDIR:-/tmp}/tmux-${uid}/default,0,0" "$restore" 2>/dev/null
    fi
  fi
  command sesh "$@"
}

#@tmux-reload
#--> Reload tmux.conf into every active session
tmux-reload() {
  local config="${XDG_CONFIG_HOME:-$HOME/.config}/tmux/tmux.conf"
  if [[ ! -f "$config" ]]; then
    echo "$(color_red "tmux config not found:") $config" >&2
    return 1
  fi

  local sessions
  sessions=$(tmux list-sessions -F '#{session_name}' 2>/dev/null)
  if [[ -z "$sessions" ]]; then
    echo "$(color_yellow "No active tmux sessions")" >&2
    return 1
  fi

  local session
  while IFS= read -r session; do
    if tmux source-file -t "$session" "$config"; then
      echo "  $(color_green "✓") Reloaded session: $session"
    else
      echo "  $(color_red "✗") Failed to reload session: $session" >&2
    fi
  done <<<"$sessions"
}

#@fzf-man-widget
#--> Fuzzy man-page browser (Ctrl-H); alt-c for cheat.sh, alt-t for tldr in the preview
fzf-man-widget() {
  manpage="echo {} | sed 's/\([[:alnum:][:punct:]]*\) (\([[:alnum:]]*\)).*/\2 \1/'"
  batman="${manpage} | xargs -r man | col -bx | bat --language=man --plain --color always"
  man -k . | sort \
    | awk -v cyan=$(tput setaf 6) -v blue=$(tput setaf 4) -v res=$(tput sgr0) -v bld=$(tput bold) '{ $1=cyan bld $1; $2=res blue $2; } 1' \
    | fzf \
      -q "$1" \
      --ansi \
      --tiebreak=begin \
      --prompt=' Man > ' \
      --preview-window '50%,rounded,<50(up,85%,border-bottom)' \
      --preview "${batman}" \
      --bind "enter:execute(${manpage} | xargs -r man)" \
      --bind "alt-c:+change-preview(cht.sh {1})+change-prompt(ﯽ Cheat > )" \
      --bind "alt-m:+change-preview(${batman})+change-prompt( Man > )" \
      --bind "alt-t:+change-preview(tldr --color=always {1})+change-prompt(ﳁ TLDR > )"
  [[ -n "${ZSH_VERSION:-}" ]] && zle reset-prompt
}
# `Ctrl-H` keybinding to launch the widget (zsh only)
if [[ -n "${ZSH_VERSION:-}" ]]; then
  bindkey '^h' fzf-man-widget
  zle -N fzf-man-widget
fi
# Icon used is nerdfont

#@fad
#--> Git add modified files matching pattern
function fad() {
  if [ -z "$1" ]; then
    echo "Usage: fad <pattern>"
    echo "Example: fad init"
    return 1
  fi

  git status --short | grep -E '^ ?M' | awk '{print $2}' | grep -i "$1" | xargs -r git add
  git status --short | grep -E '^[AM]'
}

#@gm
#--> Git commit with message
function gm() {
  git commit -m "$1"
}

#@git-old-branches
#--> Look for old branches that have been merged into master, --remote to check remote branches
function git-old-branches() {
  if [ "$1" = "--remote" ]; then
    option="-r"
  else
    option=""
  fi
  for k in $(git branch $option --format="%(refname:short)" --merged master); do
    if (($(git log -1 --since='1 month ago' -s "$k" | wc -l) == 0)); then
      echo "$k"
    fi
  done
}

#@listening
#--> List what applications are listening on specific port or pattern
function listening() {
  if [ $# -eq 0 ]; then
    sudo lsof -iTCP -sTCP:LISTEN -n -P
  elif [ $# -eq 1 ]; then
    sudo lsof -iTCP -sTCP:LISTEN -n -P | grep -i --color "$1"
  else
    echo "Usage: listening [pattern]"
  fi
}

#@hosts
#--> Print /etc/hosts file
function hosts() {
  if [ -n "$1" ]; then
    grep -i "$1" </etc/hosts
  else
    bat /etc/hosts
  fi
}

#@resetroute
#--> Reset the network and flush routing table
function resetroute() {
  echo "Flushing routes..."
  for i in $(ifconfig | grep -E -o "^[a-z].+\d{1}:" | sed 's/://'); do
    sudo ifconfig "$i" down
  done
  sudo route -n flush
  for i in $(ifconfig | grep -E -o "^[a-z].+\d{1}:" | sed 's/://'); do
    sudo ifconfig "$i" up
  done
}

#@external-ip
#--> External IP
function external-ip() {
  curl https://ipinfo.io/ip
  echo
}

#@local-ip
#--> Local IP
function local-ip() {
  ifconfig | awk '/inet / && !/127.0.0.1/ {print $2}'
}

#@all-local-ips
#--> All local IPs
function all-local-ips() {
  ifconfig -a | awk '/inet / {print $2} /inet6 / {print $2}'
}

#@ifactive
#--> Show active network interfaces
function ifactive() {
  ifconfig | pcregrep -M -o '^[^\t:]+:([^\n]|\n\t)*status: active'
}

#@digga
#--> Run dig and display the most useful info
function digga() {
  dig +nocmd "$1" any +multiline +noall +answer
}
#@checknode
#--> Check node and npm location and version
function checknode() {
  echo
  echo "$(color_blue "Node") - $(color_green "$(node -v)")"
  which node
  echo
  echo "$(color_blue "npm") - $(color_green "$(npm -v)")"
  which npm
}

#@venv
#--> Activate venv, searching up directories
function venv() {
  venvdir=$(findup .venv)
  script='/.venv/bin/activate'
  echo "$venvdir/.venv"
  source "$venvdir$script"
}

#@pytestloop
#--> Run pytest in a loop forever
function pytestloop() {
  venv    # activate venv
  testing # set ENVIRONMENT to testing
  loops=0
  while true; do
    color_blue "Starting new testing session..."
    pytest
    loops=$((loops + 1))
    color_green "Completed testing session $loops"
    sleep "$wait_time"
  done
}

#@colored-log
#--> Use in place of tail -f to get colored log output
function colored-log() {
  RED_ERROR="$(color_red "[ERROR]")"
  YELLOW_WARNING="$(color_yellow "[WARNING]")"
  BLUE_INFO="$(color_blue "[INFO]")"
  GREEN_DEBUG="$(color_green "[DEBUG]")"
  MAGENTA_CRITICAL="$(color_magenta "[CRITICAL]")"

  tail -f "$1" | awk -v error="$RED_ERROR" -v warning="$YELLOW_WARNING" -v debug="$GREEN_DEBUG" -v info="$BLUE_INFO" -v critical="$MAGENTA_CRITICAL" '{
        if (match($0, /\[ERROR\]/))     { gsub(/\[ERROR\]/, error); }
        else if (match($0, /\[WARNING\]/)) { gsub(/\[WARNING\]/, warning); }
        else if (match($0, /\[DEBUG\]/)) { gsub(/\[DEBUG\]/, debug); }
        else if (match($0, /\[INFO\]/)) { gsub(/\[INFO\]/, info); }
        else if (match($0, /\[CRITICAL\]/)) { gsub(/\[CRITICAL\]/, critical); }
        print $0;
    }'
}

#@commithelp
#--> Suggest commit type based on staged files
function commithelp() {
  echo ""
  color_green "$(print_section "Commit Type Suggestions")"
  echo ""

  # Get staged files
  local staged_files
  staged_files=$(git diff --cached --name-only 2>/dev/null)

  if [ -z "$staged_files" ]; then
    color_yellow "No files staged for commit"
    echo "Use 'git add <files>' to stage changes first"
    echo ""
    return 1
  fi

  # Show staged files
  color_blue "Staged files:"
  echo "$staged_files" | while read -r file; do
    echo "  - $file"
  done
  echo ""

  # Analyze patterns and suggest commit types
  local suggestions=()
  # shellcheck disable=SC2034  # confidence reserved for future use
  local confidence=""

  # Check for dependency files (high confidence)
  if echo "$staged_files" | grep -qE '(package\.json|package-lock\.json|requirements\.txt|Pipfile\.lock|go\.mod|go\.sum|Gemfile\.lock|composer\.lock|yarn\.lock|pnpm-lock\.yaml|uv\.lock)$'; then
    suggestions+=("$(color_green "✓") $(color_blue "deps:") Update package versions")
    confidence="high"
  fi

  # Check for lock files only (very high confidence for deps)
  if echo "$staged_files" | grep -qE '(package-lock\.json|Pipfile\.lock|go\.sum|Gemfile\.lock|yarn\.lock|pnpm-lock\.yaml|uv\.lock)$'; then
    if [ ${#suggestions[@]} -eq 0 ]; then
      suggestions+=("$(color_green "✓✓") $(color_blue "deps:") Lock file updates (very likely)")
      # shellcheck disable=SC2034
      confidence="very-high"
    fi
  fi

  # Check for CI/CD and infrastructure files
  if echo "$staged_files" | grep -qE '(\.github/workflows/|Dockerfile|docker-compose|terraform/|\.tf$|kubernetes/|k8s/|\.yml$|\.yaml$)'; then
    suggestions+=("$(color_green "✓") $(color_blue "ops:") Infrastructure/CI-CD changes")
  fi

  # Check for build configuration
  if echo "$staged_files" | grep -qE '(webpack\.config|vite\.config|rollup\.config|tsconfig\.json|babel\.config|\.babelrc|Makefile|CMakeLists\.txt|build\.gradle|pom\.xml)'; then
    suggestions+=("$(color_green "✓") $(color_blue "build:") Build system configuration")
  fi

  # Check for test files
  if echo "$staged_files" | grep -qE '(test_|_test\.|\.test\.|\.spec\.|tests?/|__tests__/)'; then
    suggestions+=("$(color_green "✓") $(color_blue "test:") Test changes")
  fi

  # Check for documentation
  if echo "$staged_files" | grep -qE '(README|CHANGELOG|\.md$|docs?/|LICENSE)'; then
    suggestions+=("$(color_green "✓") $(color_blue "docs:") Documentation")
  fi

  # Check for gitignore and common chore files
  if echo "$staged_files" | grep -qE '(\.gitignore|\.editorconfig|\.nvmrc|\.python-version)'; then
    suggestions+=("$(color_green "✓") $(color_blue "chore:") Configuration/maintenance")
  fi

  # Check for formatting config files
  if echo "$staged_files" | grep -qE '(\.prettierrc|\.eslintrc|\.pylintrc|\.flake8|\.black|pyproject\.toml|\.editorconfig)'; then
    # If only config files, it's chore; if code files too, it might be style
    local code_files
    code_files=$(echo "$staged_files" | grep -vE '\.(json|yaml|yml|toml|ini|cfg|rc)$')
    if [ -z "$code_files" ]; then
      suggestions+=("$(color_green "✓") $(color_blue "chore:") Formatting configuration")
    else
      suggestions+=("$(color_yellow "?") $(color_blue "style:") If you ran a formatter (prettier/eslint/black)")
    fi
  fi

  # Check file extensions for code vs docs vs config
  local has_code=false
  # shellcheck disable=SC2034  # has_docs/has_config reserved for future use
  local has_docs=false
  local has_config=false

  if echo "$staged_files" | grep -qE '\.(js|ts|py|go|rs|java|cpp|c|rb|php|swift|kt|sh|bash|zsh)$'; then
    has_code=true
  fi

  if echo "$staged_files" | grep -qE '\.(md|txt|rst|adoc)$'; then
    # shellcheck disable=SC2034
    has_docs=true
  fi

  if echo "$staged_files" | grep -qE '\.(json|yaml|yml|toml|ini|cfg)$'; then
    # shellcheck disable=SC2034
    has_config=true
  fi

  # General suggestions based on file types
  if [ "$has_code" = true ]; then
    suggestions+=("$(color_yellow "?") $(color_blue "feat:") If adding new functionality")
    suggestions+=("$(color_yellow "?") $(color_blue "fix:") If fixing a bug")
    suggestions+=("$(color_yellow "?") $(color_blue "refactor:") If restructuring without behavior change")
    suggestions+=("$(color_yellow "?") $(color_blue "perf:") If improving performance")
  fi

  # Display suggestions
  if [ ${#suggestions[@]} -gt 0 ]; then
    color_yellow "Suggested commit types:"
    printf '%s\n' "${suggestions[@]}"
  else
    color_yellow "No specific suggestions based on file patterns"
    echo "Review 'lscommits' for all commit types"
  fi

  echo ""
  color_bright_black "Legend:"
  echo "  $(color_green "✓✓") Very high confidence"
  echo "  $(color_green "✓")  High confidence based on file patterns"
  echo "  $(color_yellow "?")  Possible - depends on your changes"
  echo ""
  color_bright_black "Tip: Use 'workflows show git-conventional-commits' for full list"
  echo ""
}

#@layers
#--> Render ZMK keyboard layers: no argument picks one, a name draws it, "all" draws every layer
function layers() {
  local keymap_yaml="${KEYMAP_YAML:-$HOME/code/zmk/corne42/corne_keymap.yaml}"
  if [[ ! -f "$keymap_yaml" ]]; then
    echo "Keymap not found: $keymap_yaml" >&2
    echo "Set KEYMAP_YAML to point to your keymap_drawer YAML file" >&2
    return 1
  fi

  # Without -c this renders with keymap-drawer's defaults, which are white keys
  # and black legends — the repo's own dark palette never reaches the terminal.
  # The config sits beside the yaml, so it is found for any board.
  local drawer_config="${keymap_yaml%/*}/keymap_drawer.config.yaml"
  local draw_args=(draw "$keymap_yaml")
  [[ -f "$drawer_config" ]] && draw_args=(-c "$drawer_config" "${draw_args[@]}")

  local available
  available=$(yq '.layers | keys | sort | .[]' "$keymap_yaml" | tr -d '"')

  local requested="${1:-}"

  # "all" draws every layer, which is the whole reason the width is capped.
  if [[ "$requested" != "all" ]]; then
    local layer
    if [[ -n "$requested" ]]; then
      layer=$(echo "$requested" | tr '[:lower:]' '[:upper:]')
      if ! echo "$available" | grep -qx "$layer"; then
        echo "No layer '$requested' in $keymap_yaml" >&2
        echo "Available: $(echo "$available" | tr '\n' ' ')all" >&2
        return 1
      fi
    else
      layer=$(echo "$available" | gum choose --header="Select a keyboard layer")
      [[ -z "$layer" ]] && return 0
    fi
    draw_args+=(-s "$layer")
  fi

  # --fit-width fills every column it is given, and the drawing is taller than
  # it is wide, so a wide terminal buys height rather than detail. Capping the
  # width caps the scrolling with it. zsh reports COLUMNS as 0 when stdout is
  # not a TTY, which is why the floor is checked rather than just the ceiling.
  local max_width="${LAYERS_MAX_WIDTH:-110}"
  local width="$max_width"
  if [[ "${COLUMNS:-0}" -gt 0 && "${COLUMNS:-0}" -lt "$max_width" ]]; then
    width="$COLUMNS"
  fi

  keymap "${draw_args[@]}" 2>/dev/null \
    | chafa --view-size "${width}x40" --fit-width -
}

#@yt-transcript
#--> Print a YouTube video's transcript as plain text to stdout (pipe into claude, a file, etc.)
function yt-transcript() {
  if [ $# -eq 0 ]; then
    echo "Usage: yt-transcript <youtube-url> [lang]" >&2
    echo "  Emits the transcript as plain text on stdout." >&2
    echo "  lang defaults to 'en'. Prefers human captions, falls back to auto-generated." >&2
    return 1
  fi
  local url="$1"
  local lang="${2:-en}"
  local tmp
  tmp="$(mktemp -d)" || return 1
  local sub=""
  # Two passes so human captions win over auto-generated without concatenating both.
  # json3 avoids the rolling-duplicate lines that auto-caption VTT emits.
  local subflag
  for subflag in --write-subs --write-auto-subs; do
    yt-dlp --skip-download "$subflag" --sub-langs "$lang" --sub-format json3 \
      -o "$tmp/%(id)s.%(ext)s" "$url" >/dev/null 2>&1
    sub=$(find "$tmp" -maxdepth 1 -name '*.json3' | head -1)
    [[ -n "$sub" ]] && break
  done
  if [[ -z "$sub" ]]; then
    echo "yt-transcript: no '$lang' captions available for that video" >&2
    rm -rf "$tmp"
    return 1
  fi
  jq -r '.events[]?.segs[]?.utf8 // empty' "$sub" | tr '\n' ' ' | sed 's/  */ /g'
  echo
  rm -rf "$tmp"
}

# Shared by doshell and the doshell-ask ZLE widget bound in .zshrc. Passes the OS
# so Claude returns GNU-vs-BSD-correct commands (both are in play), and names the
# installed tools because otherwise it reaches for find/grep and the suggestion
# comes back as something the prefer-fast-tools hook refuses to run.
doshell_suggest_command() {
  # Strip any stray ``` fence lines defensively so the result lands clean on the
  # prompt line even when the model ignores the no-fences instruction.
  claude -p "You are a shell expert on $(uname -s) with GNU coreutils, fd, rg, eza, jq and yq installed. Prefer fd over find, rg over grep and eza over ls. Give a single shell command or short pipeline that accomplishes: $*. Output ONLY the command — no markdown fences, no explanation, no leading prompt." | sed '/^```/d'
}

# Backs the doshell-explain widget. Kept terse on purpose: the answer is painted
# below the prompt by `zle -M`, so anything longer than a few lines shoves the
# prompt off the screen.
doshell_explain_command() {
  claude -p "Explain concisely what this shell command does, on $(uname -s): $*. Answer in at most four short lines of plain text — no markdown, no fences, no preamble. Name what each flag or stage contributes. If the command is destructive or would lose data, say so first."
}

#@doshell
#--> doshell <task> — ask Claude for a shell command and preload it at your next prompt to edit or run
function doshell() {
  if [ $# -eq 0 ]; then
    echo "Usage: doshell <what you want to do>"
    echo "Loads a suggested command at your next prompt — review it, then Enter to run (or edit first)."
    return 1
  fi
  local cmd
  cmd=$(doshell_suggest_command "$@")
  if [[ -z "$cmd" ]]; then
    echo "doshell: no command returned" >&2
    return 1
  fi
  # print -z pushes the command onto the zsh line-editor buffer, so it appears at
  # your NEXT prompt ready to run (Enter) or edit — nothing executes on its own.
  # This needs no clipboard, so it works even where copy/paste is flaky. Also
  # copy it to the system clipboard when a clipboard command is available.
  if command -v pbcopy >/dev/null 2>&1; then
    printf '%s' "$cmd" | pbcopy
  elif command -v wl-copy >/dev/null 2>&1; then
    printf '%s' "$cmd" | wl-copy
  elif command -v xclip >/dev/null 2>&1; then
    printf '%s' "$cmd" | xclip -selection clipboard
  fi
  if [[ -n "${ZSH_VERSION:-}" ]]; then
    print -z "$cmd"
  else
    printf '%s\n' "$cmd" # non-zsh: just print it
  fi
}

# Bypass is the permission mode for every session, set once as
# permissions.defaultMode in ~/.claude/settings.json rather than repeated as a
# flag here — a session started any other way (an editor, a resume, a scheduled
# run) then lands in the same permission class, which is what lets cross-session
# messages deliver instead of being held.
#
# A bare first argument is taken as the session name rather than passed through,
# so `cc planner` reads naturally. Anything starting with `-` is a real flag and
# falls through untouched, which keeps `cc -p '...'` working. The array form is
# deliberate: zsh does not word-split an unquoted `${x:+--name $x}`, so the flag
# and its value would arrive as one argument.
#
# Never auto-generate that name. `--name` is one field wearing two hats: claude
# writes it as the peer address *and* as the conversation's title, and a title
# set by hand suppresses the generated one outright — so a session named from a
# word pool is unfindable in /resume forever after, showing `frito` where the
# subject should be. Bare `cc` passes nothing and claude derives
# `<dirname>-<hex>` for the address, which `claude-sessions` prints; pass a
# name only when the name is also the title you want.
#@cc
#--> cc [name] — start claude; unnamed, it takes an address from the directory and keeps a real title
cc() {
  local -a name=()
  if [[ -n $1 && $1 != -* ]]; then
    name=(--name "$1")
    shift
  fi
  claude "${name[@]}" "$@"
}

# Resume derives a fresh address rather than restoring the old one, so a session
# is addressed by whatever `claude-sessions` prints for it now, never by what
# it was called before. Naming a resume retitles the conversation for good, which on one old
# enough to have forgotten costs the only way back to it.
#@ccr
#--> ccr [name] — resume a claude session by picker; naming it retitles the conversation
ccr() {
  local -a name=()
  if [[ -n $1 && $1 != -* ]]; then
    name=(--name "$1")
    shift
  fi
  claude --resume "${name[@]}" "$@"
}

#@find-commit
#--> find-commit [-d DIR] [--msg|--code] <query> — search commits across every repo in a dir, newest first; Enter opens the diff in nvim
function find-commit() {
  local dir="." depth=3 limit=300 mode="all" query=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -d)
        dir="$2"
        shift 2
        ;;
      -n)
        limit="$2"
        shift 2
        ;;
      -L)
        depth="$2"
        shift 2
        ;;
      --msg)
        mode="msg"
        shift
        ;;
      --code)
        mode="code"
        shift
        ;;
      --all)
        mode="all"
        shift
        ;;
      -h | --help)
        echo "Usage: find-commit [-d DIR] [-n N] [-L N] [--msg|--code|--all] <query>"
        echo "  Search commit messages (--msg, git log --grep) and/or diff content"
        echo "  (--code, git log -G pickaxe) across every git repo under DIR, newest"
        echo "  first. Enter opens the commit in nvim (Diffview); Ctrl-Y yanks the sha."
        return 0
        ;;
      *)
        query="${query:+$query }$1"
        shift
        ;;
    esac
  done
  [[ -n "$query" ]] || {
    echo "Usage: find-commit [-d DIR] [--msg|--code] <query>" >&2
    return 1
  }

  # One match line per commit: "repo sha date subject" (shown) + hidden repo-path
  # and sha fields. Messages and diffs are searched separately (git has no single
  # flag that ORs them) and deduped per repo, then the whole set is sorted newest
  # first across ALL repos so a recent commit never hides below an older repo's.
  local fmt='%H%x09%ad%x09%s' index
  index=$(
    fd -t d -t f -H --max-depth "$depth" '^\.git$' "$dir" 2>/dev/null | while IFS= read -r gitpath; do
      repo=$(dirname "$gitpath")
      {
        [[ "$mode" == msg || "$mode" == all ]] && git -C "$repo" log -n "$limit" --date=short --pretty="$fmt" --grep="$query" -i 2>/dev/null
        [[ "$mode" == code || "$mode" == all ]] && git -C "$repo" log -n "$limit" --date=short --pretty="$fmt" -G"$query" 2>/dev/null
      } | awk -F'\t' -v repo="${repo##*/}" -v path="$repo" \
        'NF && !seen[$1]++ {printf "%s\t%s\t%s\t%s\t%s\n", repo, substr($1,1,9), $2, $3, path}'
    done | sort -t$'\t' -k3,3r | awk -F'\t' '{printf "%-16s %-10s %s  %s\t%s\t%s\n", $1, $2, $3, $4, $5, $2}'
  )
  [[ -n "$index" ]] || {
    echo "find-commit: no commits matched '$query' under $dir (mode: $mode)" >&2
    return 1
  }

  local selected
  selected=$(printf '%s\n' "$index" | fzf --delimiter='\t' --with-nth=1 \
    --no-sort --no-hscroll \
    --preview 'git -C {2} show --color=always {3} | delta --paging=never 2>/dev/null || git -C {2} show --color=always {3}' \
    --preview-window='right:60%,border-left' \
    --prompt='find-commit ❯ ' \
    --header="$mode '$query' · newest first · Enter opens nvim · Ctrl-Y yanks sha" \
    --bind='ctrl-y:execute-silent(printf %s {3} | pbcopy 2>/dev/null || printf %s {3} | wl-copy 2>/dev/null || printf %s {3} | xclip -selection clipboard 2>/dev/null)' \
    --bind='ctrl-/:toggle-preview')
  [[ -n "$selected" ]] || return 0

  # -C<repo> points Diffview at the repo (no cd needed); ^! = just this commit.
  # Inside neovim's terminal ($NVIM = server socket), hand the diff to the parent
  # editor over RPC rather than nesting a second nvim.
  local repo_path sha
  repo_path=$(cut -f2 <<<"$selected")
  sha=$(cut -f3 <<<"$selected")
  if [[ -n "${NVIM:-}" ]]; then
    nvim --server "$NVIM" --remote-expr "execute('DiffviewOpen -C${repo_path} ${sha}^!')" >/dev/null 2>&1
  else
    nvim -c "DiffviewOpen -C${repo_path} ${sha}^!"
  fi
}

#@aws-profiles
#--> Pick an AWS profile and export it into this shell
# A function rather than a command because exporting into the shell you are
# sitting in is the one thing a subprocess cannot do — the same reason zoxide,
# fnm and atuin are wired through eval in .zshrc. `_aws-profiles` draws the menu
# on stderr and prints its decision on stdout, so the answer can be captured
# without hiding the interface.
#
# This replaced a macOS-only `alias aws-profiles='source ...'`. Everywhere else
# the command ran in its own process, announced that it had set the profile, and
# exited without having set anything.
function aws-profiles() {
  local decision action profile region
  decision=$(_aws-profiles "$@") || return 1

  IFS=$'\t' read -r action profile region <<<"$decision"
  case "${action:-}" in
    set)
      export AWS_PROFILE="$profile"
      if [[ -n "$region" ]]; then
        export AWS_REGION="$region"
        export AWS_DEFAULT_REGION="$region"
        echo "AWS profile $profile and region $region have been set."
      else
        echo "AWS profile $profile has been set."
      fi
      ;;
    clear)
      unset AWS_PROFILE AWS_REGION AWS_DEFAULT_REGION
      echo "The AWS profile has been cleared."
      ;;
  esac
}
