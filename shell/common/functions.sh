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

#@opendir
#--> Open current directory or given location
function opendir() {
  if [ $# -eq 0 ]; then
    open .
  else
    open "$@"
  fi
}

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
    : > /tmp/fzf_tmp
    for file in "${arguments[@]}"; do
        echo "$file" >> /tmp/fzf_tmp
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
    echo $program$options$arguments >> ~/.bash_history

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
fif() {
    if [ ! "$#" -gt 0 ]; then echo "Need a string to search for!"; return 1; fi
    local file
    file="$(rga --max-count=1 --ignore-case --files-with-matches --no-messages "$*" | fzf-tmux +m --preview="rga --ignore-case --pretty --context 10 '"$*"' {}")" && echo "opening $file" && open "$file" || return 1;
}

# fco_preview - checkout git branch/tag, with a preview showing the commits between the tag/branch and HEAD
fco_preview() {
  local tags branches target
  branches=$(
    git --no-pager branch --all \
      --format="%(if)%(HEAD)%(then)%(else)%(if:equals=HEAD)%(refname:strip=3)%(then)%(else)%1B[0;34;1mbranch%09%1B[m%(refname:short)%(end)%(end)" \
    | sed '/^$/d') || return
  tags=$(
    git --no-pager tag | awk '{print "\x1b[35;1mtag\x1b[m\t" $1}') || return
  target=$(
    (echo "$branches"; echo "$tags") |
    fzf --no-hscroll --no-multi -n 2 \
        --ansi --preview="git --no-pager log -150 --pretty=format:%s '..{2}'") || return
  git checkout $(awk '{print $2}' <<<"$target" )
}

alias glNoGraph='git log --color=always --format="%C(auto)%h%d %s %C(black)%C(bold)%cr% C(auto)%an" "$@"'
_gitLogLineToHash="echo {} | grep -o '[a-f0-9]\{7\}' | head -1"
_viewGitLogLine="$_gitLogLineToHash | xargs -I % sh -c 'git show --color=always % | diff-so-fancy'"

# fcoc_preview - checkout git commit with previews
fcoc_preview() {
  local commit
  commit=$( glNoGraph |
    fzf --no-sort --reverse --tiebreak=index --no-multi \
        --ansi --preview="$_viewGitLogLine" ) &&
  git checkout $(echo "$commit" | sed "s/ .*//")
}

# fshow_preview - git commit browser with previews
fshow_preview() {
    glNoGraph |
        fzf --no-sort --reverse --tiebreak=index --no-multi \
            --ansi --preview="$_viewGitLogLine" \
                --header "enter to view, alt-y to copy hash" \
                --bind "enter:execute:$_viewGitLogLine   | less -R" \
                --bind "alt-y:execute:$_gitLogLineToHash | xclip"
}

# fstash - easier way to deal with stashes
# type fstash to get a list of your stashes
# enter shows you the contents of the stash
# ctrl-d shows a diff of the stash against your current HEAD
# ctrl-b checks the stash out as a branch, for easier merging
fstash() {
  local out q k sha
  while out=$(
    git stash list --pretty="%C(yellow)%h %>(14)%Cgreen%cr %C(blue)%gs" |
    fzf --ansi --no-sort --query="$q" --print-query \
        --expect=ctrl-d,ctrl-b);
  do
    mapfile -t out <<< "$out"
    q="${out[0]}"
    k="${out[1]}"
    sha="${out[-1]}"
    sha="${sha%% *}"
    [[ -z "$sha" ]] && continue
    if [[ "$k" == 'ctrl-d' ]]; then
      git diff $sha
    elif [[ "$k" == 'ctrl-b' ]]; then
      git stash branch "stash-$sha" $sha
      break;
    else
      git stash show -p $sha
    fi
  done
}

# fgst - pick files from `git status -s`
is_in_git_repo() {
  git rev-parse HEAD > /dev/null 2>&1
}

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
gh-watch() {
    gh run list \
      --branch $(git rev-parse --abbrev-ref HEAD) \
      --json status,name,databaseId |
      jq -r '.[] | select(.status != "completed") | (.databaseId | tostring) + "\t" + (.name)' |
      fzf -1 -0 | awk '{print $1}' | xargs gh run watch
}

# tm - create new tmux session, or switch to existing one. Works from within tmux too. (@bag-man)
# `tm` will allow you to select your tmux session via fzf.
# `tm irc` will attach to the irc session (if it exists), else it will create it.

tm() {
  [[ -n "$TMUX" ]] && change="switch-client" || change="attach-session"
  if [ $1 ]; then
    tmux $change -t "$1" 2>/dev/null || (tmux new-session -d -s $1 && tmux $change -t "$1"); return
  fi
  session=$(tmux list-sessions -F "#{session_name}" 2>/dev/null | fzf --exit-0) &&  tmux $change -t "$session" || echo "No sessions found."
}


fzf-man-widget() {
  manpage="echo {} | sed 's/\([[:alnum:][:punct:]]*\) (\([[:alnum:]]*\)).*/\2 \1/'"
  batman="${manpage} | xargs -r man | col -bx | bat --language=man --plain --color always --theme=\"Monokai Extended\""
   man -k . | sort \
   | awk -v cyan=$(tput setaf 6) -v blue=$(tput setaf 4) -v res=$(tput sgr0) -v bld=$(tput bold) '{ $1=cyan bld $1; $2=res blue $2; } 1' \
   | fzf  \
      -q "$1" \
      --ansi \
      --tiebreak=begin \
      --prompt=' Man > '  \
      --preview-window '50%,rounded,<50(up,85%,border-bottom)' \
      --preview "${batman}" \
      --bind "enter:execute(${manpage} | xargs -r man)" \
      --bind "alt-c:+change-preview(cht.sh {1})+change-prompt(ﯽ Cheat > )" \
      --bind "alt-m:+change-preview(${batman})+change-prompt( Man > )" \
      --bind "alt-t:+change-preview(tldr --color=always {1})+change-prompt(ﳁ TLDR > )"
  [[ -n "$ZSH_VERSION" ]] && zle reset-prompt
}
# `Ctrl-H` keybinding to launch the widget (zsh only)
if [[ -n "$ZSH_VERSION" ]]; then
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

#@gdp
#--> Git diff preview for modified files
function gdp() {
  # shellcheck disable=SC2016
  git status --short | awk '{print $2}' | \
    fzf --preview 'git diff --color=always {} | delta --paging=never --width=$FZF_PREVIEW_COLUMNS' \
        --preview-window='up:85%' \
        --bind 'ctrl-d:preview-page-down,ctrl-u:preview-page-up'
}

#@adcomp
#--> Git add all, commit with message and push
function adcomp() {
  git add . && git commit -m "$1" && git push
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
  # shellcheck source=/dev/null
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

#@new-py-project
#--> Make a new python project
function new-py-project() {
  # Create a new project with poetry, make git repository and add new files as first commit

  # Check that the first parameter was provided
  if [ -z "$1" ]; then
    echo "Please provide a project name"
    return 1
  fi
  PROJECT="$1"

  # Replace all hyphens with underscore for package
  PACKAGE="${PROJECT//[-]/_}"

  mkdir -v "$PROJECT"
  touch "$PROJECT/TESTING.ipynb"
  touch "$PROJECT/TESTING.py"
  touch "$PROJECT/.env"

  mkdir -v "$PROJECT/$PACKAGE"
  touch "$PROJECT/$PACKAGE/__init__.py"
  touch "$PROJECT/$PACKAGE/main.py"

  mkdir -v "$PROJECT/tests"
  touch "$PROJECT/tests/test_main.py"

  cd "$PROJECT" || exit

  # Copy template files from Github new-python-project
  # Better than using Github Template in order to customize install before pushing
  TEMPLATE_URL='https://raw.githubusercontent.com/datapointchris/new-python-project/master/'
  TEMPLATE_FILENAMES=('.gitignore' '.markdownlint.json' '.pre-commit-config.yaml' '.shellcheckrc' 'pyproject_settings.toml' 'README.md')

  for FILENAME in "${TEMPLATE_FILENAMES[@]}"; do
    wget --no-verbose --output-document "$FILENAME" "${TEMPLATE_URL}${FILENAME}"
  done

  poetry init --no-interaction --name "$PROJECT" --license "MIT"
  poetry add --group=dev ipykernel ipywidgets black flake8 pytest pre-commit pytest-cov bandit mypy isort bandit
  poetry installmv TEST

  # Add pyproject_settings.toml to pyproject.toml before [build-system]
  awk 'FNR==NR{a[NR]=$0; next} /\[build-system\]/{for (i=1;i<=NR;i++) print a[i]}1' pyproject_settings.toml pyproject.toml >temp && mv temp pyproject.toml

  rm pyproject_settings.toml

  git init
  git add -A
  git commit -m 'init: Initial commit new project'

  poetry run pre-commit install
  poetry run pre-commit autoupdate
  poetry run pre-commit run --all-files

  git add -A
  git commit --amend --no-edit --no-verify

  echo ""
  color_yellow "Using python: $(poetry run python -V)"
  color_blue "PROJECT STRUCTURE:"
  tree -a -I '.git|.venv|.mypy_cache|.ruff_cache' --filesfirst
}

#@lsalias
#--> List all aliases
function lsalias() {
  echo

  local shell_file="$SHELL_DIR/$PLATFORM.sh"

  # Process aliases from the single generated file
  local message=""
  if [[ -f "$shell_file" ]]; then
    message="$(grep '^alias ' "$shell_file" | sed 's/alias//g' | sed 's/=/Ø/')"
  fi

  # Function to format and display aliases
  format_aliases() {
    local msg="$1"
    local filter="$2"

    if [[ -n "$msg" ]]; then
      if [[ -n "$filter" ]]; then
        command echo -E "$msg" | grep -i "$filter" | sort | column -t -s 'Ø' | while read -r c1 c2; do echo -E "$(color_blue "$c1")Ø$c2"; done | column -t -s 'Ø'
      else
        command echo -E "$msg" | sort | column -t -s 'Ø' | while read -r c1 c2; do echo -E "$(color_blue "$c1")Ø$c2"; done | column -t -s 'Ø'
      fi
    fi
  }

  if [[ -n "$message" ]]; then
    color_green "$(print_section "Aliases")"
    format_aliases "$message" "$1"
    echo
  fi

  if [[ -z "$message" ]]; then
    color_yellow "No aliases found"
  fi
}

#@lsfunc
#--> List all functions
function lsfunc() {
  echo ""

  local shell_file="$SHELL_DIR/$PLATFORM.sh"

  # Process functions from the single generated file
  local message=""
  if [[ -f "$shell_file" ]]; then
    message="$(awk '/^#@/{name=substr($0,3)} /^#-->/{print name "|" substr($0,5)}' "$shell_file")"
  fi

  # Function to format and display functions
  format_functions() {
    local msg="$1"
    local filter="$2"

    if [[ -n "$msg" ]]; then
      if [[ -n "$filter" ]]; then
        command echo "$msg" | grep -i "$filter" | sort | column -t -s \|
      else
        command echo "$msg" | sort | column -t -s \|
      fi
    fi
  }

  if [[ -n "$message" ]]; then
    color_green "$(print_section "Functions")"
    format_functions "$message" "$1"
    echo
  fi

  if [[ -z "$message" ]]; then
    color_yellow "No functions found"
  fi
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
#--> Browse ZMK keyboard layers — pick from fzf, render SVG
function layers() {
  local keymap_yaml="${KEYMAP_YAML:-$HOME/code/zmk/corne42/corne_keymap.yaml}"
  if [[ ! -f "$keymap_yaml" ]]; then
    echo "Keymap not found: $keymap_yaml" >&2
    echo "Set KEYMAP_YAML to point to your keymap_drawer YAML file" >&2
    return 1
  fi

  local layer
  layer=$(yq '.layers | keys | .[]' "$keymap_yaml" | tr -d '"' \
    | gum choose --header="Select a keyboard layer")
  [[ -z "$layer" ]] && return 0

  keymap draw "$keymap_yaml" -s "$layer" 2>/dev/null \
    | chafa --size "${COLUMNS:-120}x${LINES:-40}" -
}
