# shellcheck shell=bash
# shellcheck disable=SC2016,SC2154
# SC2016 = fzf preview commands use single quotes intentionally
# SC2154 = Variables referenced but not assigned (from sourced files)

SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
source "$SHELL_DIR/colors.sh"

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
