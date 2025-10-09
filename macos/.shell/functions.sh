# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variable is referenced but not assigned
# *For the word formatting that comes from .color-and-formatting

DOTFILES="$HOME/dotfiles"
SHELLS="$HOME/.shell"
source "$SHELLS/colors.sh"

#@openhands
#--> Run the openhands docker container
function openhands() {
  local code_dir="$HOME/code"
  local default_repo="ichrisbirch"
  if [ -n "$1" ]; then
    repo="$1"
  else
    repo="$default_repo"
  fi
  export WORKSPACE_BASE="$code_dir/$repo"

  echo "Using $(color_blue "$WORKSPACE_BASE") as workspace base"

  docker run -it --rm --pull=always \
    -e SANDBOX_RUNTIME_CONTAINER_IMAGE=docker.all-hands.dev/all-hands-ai/runtime:0.32-nikolaik \
    -e SANDBOX_USER_ID="$(id -u)" \
    -e WORKSPACE_MOUNT_PATH="$WORKSPACE_BASE" \
    -v "$WORKSPACE_BASE:/opt/workspace_base" \
    -e LOG_ALL_EVENTS=true \
    -e LLM_NUM_RETRIES=5 \
    -e LLM_RETRY_MIN_WAIT=30 \
    -e LLM_RETRY_MAX_WAIT=150 \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v ~/.openhands-state:/.openhands-state \
    -p 3000:3000 \
    --add-host host.docker.internal:host-gateway \
    --name openhands-app \
    docker.all-hands.dev/all-hands-ai/openhands:0.32
}

#@ubuntu-docker
#--> Make a new Ubuntu Docker container and ssh into it
function ubuntu-docker() {
  container_id=$(docker run -itd ubuntu)
  docker exec -it "$container_id" bash
}

#@virtubuntu
#--> Make an Ubuntu virtual machine with multipass, provide optional name
function virtubuntu() {
  local name=${1:-ubu}
  multipass launch --name "$name" --disk 30G --memory 24G --cpus 12

  multipass exec "$name" -- mkdir .aws
  multipass transfer ~/.aws/config "$name":.aws/config
  multipass transfer ~/.aws/credentials "$name":.aws/credentials
  multipass shell "$name"
}

#@ephemeral-ec2
#--> Create an ephemeral ec2 instance and ssh into it, provide instance name as argument if desired
function ephemeral-ec2() {
  local instance_name=${1:-ephemeral-ec2}
  local instance_type="t3.xlarge"
  local key_name="ephemeral-ec2"
  local key_file="$HOME/.ssh/ephemeral-ec2.pem"
  local ami_id="ami-085f9c64a9b75eed5" # Ubuntu 24.04
  local wait_time=5

  echo "Creating $(color_yellow "EC2") instance with name: $(color_green "$instance_name"), type: $(color_red "$instance_type")"

  instance_id=$(aws ec2 run-instances \
    --image-id "$ami_id" \
    --instance-type "$instance_type" \
    --key-name "$key_name" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$instance_name}]" \
    --instance-market-options "MarketType=spot" \
    --query 'Instances[0].InstanceId' \
    --output text)

  echo "Instance ID: $(color_blue "$instance_id") created. Waiting for it to become ready..."

  # Wait until the instance is in 'running' state
  echo -n "Waiting"
  while
    instance_state=$(aws ec2 describe-instances \
      --instance-id "$instance_id" \
      --query 'Reservations[0].Instances[0].State.Name' \
      --output text)
    test "$instance_state" != "running"
  do
    echo -n "."
    sleep "$wait_time"
  done

  # Wait until the instance status checks are passed
  while
    instance_status=$(aws ec2 describe-instance-status \
      --instance-id "$instance_id" \
      --query 'InstanceStatuses[0].InstanceStatus.Status' \
      --output text)
    test "$instance_status" != "ok"
  do
    echo -n "."
    sleep "$wait_time"
  done
  echo -ne "\n"

  echo -n "Waiting"
  while
    system_status=$(aws ec2 describe-instance-status \
      --instance-id "$instance_id" \
      --query 'InstanceStatuses[0].SystemStatus.Status' \
      --output text)
    test "$system_status" != "ok"
  do
    echo -n "."
    sleep "$wait_time"
  done
  echo -ne "\n"

  public_ip=$(aws ec2 describe-instances \
    --instance-id "$instance_id" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

  echo "Instance is running. Public IP: $(color_green "$public_ip")"

  echo "Connecting to instance via SSH..."
  ssh -o StrictHostKeyChecking=no -i "$key_file" "ubuntu@$public_ip"

  echo "SSH session ended. To terminate the instance, run:"
  cmd="aws ec2 terminate-instances --instance-ids $instance_id > /dev/null"
  color_bright_red "$cmd"
  echo "Command has been copied to clipboard"
  echo "$cmd" | pbcopy
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

#@adcomp
#--> Git add all, commit with message and push
function adcomp() {
  git add . && git commit -m "$1" && git push
}

function fix_remote() { git remote set-url origin "https://github.com/datapointchris/$1.git"; }

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

#@pkill
#--> Kill process by name
function pkill() {
  fzf --height 40% \
    --layout=reverse \
    --header-lines=1 \
    --prompt="Select process to kill: " \
    --preview 'echo {}' \
    --preview-window up:3:hidden:wrap \
    --bind 'F2:toggle-preview' |
    awk '{print $2}' |
    xargs -r bash -c "
    if ! kill \"$1\" 2>/dev/null; then
        echo \"Regular kill failed. Attempting with sudo...\"
        sudo kill \"$1\" || echo \"Failed to kill process $1\" >&2
    fi
  " --
}

#@touchdate
#--> Make new file prefixed with date
function touchdate() {
  touch "$(date +"%Y-%m-%d_%H%M%S")-$1"
}

#@toichrisbirch
#--> scp file or directory to ichrisbirch home dir
function toichrisbirch() {
  scp -i ~/.ssh/apps.pem "$@" ubuntu@ichrisbirch:~
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

#@development
#--> Set ENVIRONMENT to development
function development() {
  export ENVIRONMENT='development'
  color_blue 'export ENVIRONMENT=development'
}

#@testing
#--> Set ENVIRONMENT to testing
function testing() {
  export ENVIRONMENT='testing'
  color_blue 'export ENVIRONMENT=testing'
}

#@production
#--> Set ENVIRONMENT to production
function production() {
  export ENVIRONMENT='production'
  color_blue 'export ENVIRONMENT=production'
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

#@reload-dev-forever
#--> Reload nginx and supervisor in a loop forever
function reload-dev-forever() {
  local char=":"
  local loops=1
  while true; do
    chars=$(printf "$char%.0s" $(seq 1 $loops))
    echo "Restarting $(color_blue "DEV") $(color_green "NGINX") and $(color_green "Supervisor") $(color_blue ": $loops ${chars}")"
    sudo nginx -s reload && sudo supervisorctl reload >>/dev/null
    loops=$((loops + 1))
    sleep 15
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

#------------------------------ INFO FUNCTIONS (LS FUNCTIONS) ------------------------------#

#@lsalias
#--> List all aliases
function lsalias() {
  echo
  # grep for aliases, remove alias, replace = with special Ø char. Shift+Option+O
  message="$(grep '^alias ' "$SHELLS/aliases.sh" | sed 's/alias//g' | sed 's/=/Ø/')"
  if [ -n "$1" ]; then
    # output message -E do not interpret \backslash, table column with Ø delimiter, read two columns, color first blue, concat with special delim, columns again
    command echo -E "$message" | grep -i "$1" | sort | column -t -s 'Ø' | while read -r c1 c2; do echo -E "$(color_blue "$c1")Ø$c2"; done | column -t -s 'Ø'
  else
    command echo -E "$message" | sort | column -t -s 'Ø' | while read -r c1 c2; do echo -E "$(color_blue "$c1")Ø$c2"; done | column -t -s 'Ø'
  fi
}

#@lsfunc
#--> List all functions
function lsfunc() {
  echo
  message="$("$SHELLS/get-docs.sh" "$SHELLS/functions.sh")"
  if [ -n "$1" ]; then
    command echo "$message" | grep -i "$1" | sort | column -t -s :
  else
    command echo "$message" | sort | column -t -s \|
  fi
}

#@lscommits
#--> List conventional commits
function lscommits() {
  echo ""
  color_green "$(print_section "Conventional Commits")"
  local message
  message=$(
    cat <<-EOF
			$(color_blue "feat: |${normal} Feature work")
			$(color_blue "fix: |${normal} Fix an issue")
			$(color_blue "test: |${normal} Add, modify, refactor tests")
			$(color_blue "refactor: |${normal} Rewrite/restructure your code, however does not change any behavior")
			$(color_blue "perf: |${normal} Refactor to improve performance")
			$(color_blue "style: |${normal} Code style, lint or formatting")
			$(color_blue "docs: |${normal} Documentation")
			$(color_blue "build: |${normal} Build components like build tool, ci pipeline, dependencies, project version")
			$(color_blue "ops: |${normal} Operational components like infrastructure, deployment, backup, recovery")
			$(color_blue "chore: |${normal} Miscellaneous commits e.g. modifying .gitignore moving or renaming files or directories")
		EOF
  )
  echo "$message" | column -t -s \|
}

#@lsterm
#--> Display terminal information, such as commands and workflows
function lsterm() {
  echo
  print_title "Terminal Commands"

  # -------------------- ripgrep -------------------- #

  local ripgrep_commands
  ripgrep_commands=$(
    cat <<-EOF
			  $(color_bright_black "rg foo |${normal} => foo in current directory")
			  $(color_bright_black "rg foo bar |${normal} => foo and bar in current directory")
			  $(color_bright_black "rg -t py foo bar |${normal} => foo and bar in python files")
			  $(color_bright_black "rg fast README.md |${normal} => fast in README.md")
			  $(color_bright_black "rg 'fast\w+' README.md |${normal} => fast followed by one or more word like characters in README.md")
			  $(color_bright_black "rg 'fn write\(' |${normal} => 'fn write(' in all files")
		EOF
  )

  color_green "ripgrep"
  echo "  ripgrep is a line-oriented search tool that recursively searches your current directory for a regex pattern."
  echo
  echo "$ripgrep_commands" | column -t -s \|
  echo
  color_bright_red "  Tutorial"
  echo "  https://codapi.org/try/ripgrep/"
  echo
  echo

  # -------------------- fzf -------------------- #

  local fzf_commands
  fzf_commands=$(
    cat <<-EOF
			  $(color_bright_black "-- Token --|-- Match type --|-- Description --")
			  $(color_bright_black "sbtrkt |${normal} fuzzy-match |${normal} match sbtrkt")
			  $(color_bright_black "'wild |${normal} exact-match (quoted) |${normal} include wild")
			  $(color_bright_black "'wild' |${normal} exact-boundary-match (quoted both ends) |${normal} include wild at word boundaries")
			  $(color_bright_black "^music |${normal} prefix-exact-match |${normal} start with music")
			  $(color_bright_black ".mp3$ |${normal} suffix-exact-match |${normal} end with .mp3")
			  $(color_bright_black "!fire |${normal} inverse-exact-match |${normal} do not include fire")
			  $(color_bright_black "!^music |${normal} inverse-prefix-exact-match |${normal} do not start with music")
			  $(color_bright_black "!.mp3$ |${normal} inverse-suffix-exact-match |${normal} do not end with .mp3")
		EOF
  )
  local fzf_special
  fzf_special=$(
    cat <<-EOF
			  $(color_bright_black "nvim -o \`fzf\` |${normal} open neovim with files selected by fzf")
			  $(color_bright_black "Ctrl + R |${normal} search history of commands (enabled by fzf)")
		EOF
  )

  color_green "fzf"
  echo "  fzf is a general-purpose command-line fuzzy finder."
  echo
  color_blue "  Search Syntax"
  echo "  Unless otherwise specified, fzf starts in "extended-search mode" where you can type in"
  echo "  multiple search terms delimited by spaces."
  echo "  e.g. ^music .mp3$ sbtrkt !fire"
  echo
  echo "$fzf_commands" | column -t -s \|
  echo
  color_blue "  Special Commands"
  echo
  echo "$fzf_special" | column -t -s \|
  echo
  echo

  # -------------------- zoxide -------------------- #

  local zoxide_commands
  zoxide_commands=$(
    cat <<-EOF
			  $(color_bright_black "cd foo |${normal} cd into highest ranked directory matching foo")
			  $(color_bright_black "cd foo bar |${normal} cd into highest ranked directory matching foo and bar")
			  $(color_bright_black "cd foo / |${normal} cd into a subdirectory starting with foo")

			  $(color_bright_black "cd ~/foo |${normal} z also works like a regular cd command")
			  $(color_bright_black "cd foo/ |${normal} cd into relative path")
			  $(color_bright_black "cd .. |${normal} cd one level up")
			  $(color_bright_black "cd - |${normal} cd into previous directory")

			  $(color_bright_black "cdi foo |${normal} cd with interactive selection (using fzf)")

			  $(color_bright_black "cd foo<SPACE><TAB> |${normal} show interactive completions")
		EOF
  )

  color_green "zoxide"
  echo "  zoxide remembers your most used directories and allows you to jump to them with ease."
  color_yellow "  Note: ${normal}z is aliased to 'cd' in .zshrc"
  echo
  echo "$zoxide_commands" | column -t -s \|
  echo
  echo

  # -------------------- watch -------------------- #

  color_green "watch"
  echo "  watch is used to execute a program periodically, showing output in full screen."
  echo
  color_bright_black "  tldr watch |${normal} for more information"
  echo
  echo

  # -------------------- eza -------------------- #

  color_green "eza"
  echo "  eza is a replacement for 'ls' command"
  echo "  after multiple reviews, it is not worth the install and configuration at this time"
  echo "  a combination of tmux and neovim provides a better workflow"
  echo
  echo
}

#@lsneovim
#--> List neovim commands
function lsvim() {
  echo ""
  color_green "$(print_section "Vim / Neovim Commands")"
  local message
  message=$(
    cat <<-EOF
		  $(color_green "Functionality")
        $(color_blue "w |${normal} start of next word, EXCLUDING its first character")
        $(color_blue "e |${normal} end of the current word, INCLUDING the last character")
        $(color_blue "$ |${normal} to the end of the line, INCLUDING the last character")
        $(color_blue "0 |${normal} to the beginning of the line")
        $(color_blue "^ |${normal} to the first non-blank character of the line")
        $(color_blue "gg |${normal} to the top of file")
        $(color_blue "G |${normal} to the bottom of file")
        $(color_blue "H |${normal} to the top of the screen")
        $(color_blue "M |${normal} to the middle of the screen")
        $(color_blue "L |${normal} to the bottom of the screen")

      $(color_green "Basic Movement")
        $(color_blue "Ctrl + u |${normal} Move half page up")
        $(color_blue "Ctrl + d |${normal} Move half page down")
        $(color_blue "Ctrl + b |${normal} Move full page up")
        $(color_blue "Ctrl + f |${normal} Move full page down")
        $(color_blue "Ctrl + y |${normal} Move screen up")
        $(color_blue "Ctrl + e |${normal} Move screen down")

      $(color_green "Editing")
        $(color_blue "i |${normal} Insert mode before cursor")
        $(color_blue "I |${normal} Insert mode at beginning of line")
        $(color_blue "a |${normal} Insert mode after cursor")
        $(color_blue "A |${normal} Insert mode at end of line")
        $(color_blue "o |${normal} Insert line below")
        $(color_blue "O |${normal} Insert line above")
        $(color_blue "r |${normal} Replace character")
        $(color_blue "R |${normal} Replace mode")
        $(color_blue "x |${normal} Delete character")
        $(color_blue "X |${normal} Delete character before cursor")
        $(color_blue "dd |${normal} Delete line")
        $(color_blue "yy |${normal} Yank line")
        $(color_blue "p |${normal} Paste after cursor")
        $(color_blue "P |${normal} Paste before cursor")
        $(color_blue "u |${normal} Undo")
        $(color_blue "Ctrl + r |${normal} Redo")
        $(color_blue ". |${normal} Repeat last command")

      $(color_green "Nouns")
        $(color_blue "w |${normal} Word")
        $(color_blue "s |${normal} Sentence")
        $(color_blue "p |${normal} Paragraph")
        $(color_blue "t |${normal} Tag")
        $(color_blue "b |${normal} Block")

      $(color_green "Verbs")
        $(color_blue "d |${normal} Delete")
        $(color_blue "c |${normal} Change")
        $(color_blue "y |${normal} Yank (copy)")
        $(color_blue "v |${normal} Visual (select)")
        $(color_blue "p |${normal} Put (paste)")

      $(color_green "Modifiers")
        $(color_blue "i |${normal} Inner")
        $(color_blue "a |${normal} Around")
        $(color_blue "t |${normal} Till")
        $(color_blue "f |${normal} Find")

      $(color_green "Combinations")
        $(color_blue "ciw |${normal} Change inner word")
        $(color_blue "cit |${normal} Change inner tag")
        $(color_blue "cip |${normal} Change inner paragraph")
        $(color_blue "ci( |${normal} Change inner parentheses")
        $(color_blue "ci\" |${normal} Change inner quotes")
        $(color_blue "ci{ |${normal} Change inner curly braces")

      $(color_green "Search and Replace")
        $(color_blue "/pattern |${normal} Search forward for pattern")
        $(color_blue "?pattern |${normal} Search backward for pattern")
        $(color_blue "n |${normal} Repeat search in same direction")
        $(color_blue "N |${normal} Repeat search in opposite direction")
        $(color_blue ":s/foo/bar/g |${normal} Replace foo with bar in current line")
        $(color_blue ":%s/foo/bar/g |${normal} Replace foo with bar in entire file")
        $(color_blue ":s/foo/bar/gc |${normal} Replace foo with bar in current line with confirmation")
        $(color_blue ":%s/foo/bar/gc |${normal} Replace foo with bar in entire file with confirmation")
        $(color_blue ":set ic |${normal} Ignore case in search")
        $(color_blue ":set is |${normal} Enable partial search")
        $(color_blue ":set hls |${normal} Enable search highlight")
        $(color_blue ":noh |${normal} Remove search highlight")

      $(color_green "Buffers")
        $(color_blue ":e file |${normal} Edit file")
        $(color_blue ":ls |${normal} List buffers")
        $(color_blue ":bnext |${normal} Next buffer")
        $(color_blue ":bprev |${normal} Previous buffer")
        $(color_blue ":bfirst |${normal} First buffer")
        $(color_blue ":blast |${normal} Last buffer")
        $(color_blue ":bdelete |${normal} Delete buffer")
        $(color_blue ":bdelete 2 |${normal} Delete buffer 2")
        $(color_blue ":bdelete foo |${normal} Delete buffer with foo in name")
        $(color_blue ":bdelete foo bar |${normal} Delete buffer with foo or bar in name")

      $(color_green "Windows")
        $(color_blue ":sp |${normal} Split window horizontally")
        $(color_blue ":vsp |${normal} Split window vertically")
        $(color_blue ":q |${normal} Quit window")
        $(color_blue ":q! |${normal} Quit window without saving")
        $(color_blue ":w |${normal} Save file")
        $(color_blue ":wq |${normal} Save file and quit")
        $(color_blue ":e |${normal} Edit file")
        $(color_blue ":e! |${normal} Edit file without saving")

      $(color_green "Tabs")
        $(color_blue ":tabnew |${normal} Open new tab")
        $(color_blue ":tabnext |${normal} Next tab")
        $(color_blue ":tabprev |${normal} Previous tab")
        $(color_blue ":tabclose |${normal} Close tab")
        $(color_blue ":tabonly |${normal} Close all tabs except current")

      $(color_green "Help")
        $(color_blue ":help |${normal} Open help")
        $(color_blue ":help w |${normal} Open help for w command")
        $(color_blue ":helpgrep foo |${normal} Search help for foo")
        $(color_blue ":helptags |${normal} Generate help tags")
        $(color_blue ":helptags ALL |${normal} Generate help tags for all directories")

		EOF
  )
  if [ -n "$1" ]; then
    command echo "$message" | grep -i "$1" | column -t -s \|
  else
    command echo "$message" | column -t -s \|
  fi
}

#@lstmux
#--> List tmux commands
function lstmux() {
  echo ""
  color_green "$(print_section "TMUX Commands")"
  local message
  message=$(
    cat <<-EOF
			$(color_green "Windows")
			  $(color_blue "New Window: |${normal} pre + c")
			  $(color_blue "Select Window: |${normal} pre + 1-9, starts at 1")
			  $(color_blue "Rename Window: |${normal} pre + ,")
			  $(color_blue "Previous Window: |${normal} pre + p")
			  $(color_blue "Next Window: |${normal} pre + n")
			  $(color_blue "Close Window: |${normal} pre + k")
			  $(color_blue "Last Active Window: |${normal} pre + l")
			$(color_green "Panes")
			  $(color_blue "Split Horizontally: |${normal} pre + {pipe}")
			  $(color_blue "Split Vertically: |${normal} pre + -")
			  $(color_blue "Rename Pane: |${normal} tmux select-pane -T 'New name'")
			  $(color_blue "Navigate panes: |${normal} pre + LRUD")
			  $(color_blue "Resize pane: |${normal} pre + Cmd-Option-LRUD")
			  $(color_blue "Toggle last active pane: |${normal} pre + ;")
			  $(color_blue "Zoom In on pane: |${normal} pre + z")
			  $(color_blue "Close Pane: |${normal} pre + x")
			  $(color_blue "Swap with Next Pane: |${normal} pre + }")
			  $(color_blue "Swap with Previous Pane: |${normal} pre + {")
			  $(color_blue "Breakout Pane to New Window: |${normal} pre + !")
			$(color_green "Sessions")
			  $(color_blue "Rename Current Session: |${normal} pre + $")
			  $(color_blue "Detach Session: |${normal} pre + d")
			  $(color_blue "List Sessions: |${normal} tmux ls")
			  $(color_blue "New Session: |${normal} tmux new -s session_name")
			  $(color_blue "Attach Session: |${normal} tmux attach -t session_name")
			  $(color_blue "Switch Session: |${normal} tmux switch -t session_name")
			  $(color_blue "Detach from Session: |${normal} tmux detach")
			$(color_green "SessionX")
			  $(color_blue "Delete Selected Session: |${normal} alt + backspace")
			  $(color_blue "Scroll Preview Up: |${normal} Ctrl + u")
			  $(color_blue "Scroll Preview Down: |${normal} Ctrl + d")
			  $(color_blue "Select Preview Up: |${normal} Ctrl + n")
			  $(color_blue "Select Preview Down: |${normal} Ctrl + p")
			  $(color_blue "Rename Session: |${normal} Ctrl + r")
			  $(color_blue "Reload Window List: |${normal} Ctrl + w")
			  $(color_blue "Fuzzy Read: |${normal} Ctrl + x")
			  $(color_blue "Expand: |${normal} Ctrl + e")
			  $(color_blue "Back: |${normal} Ctrl + b")
			  $(color_blue "Tree: |${normal} Ctrl + t")
			  $(color_blue "Tmuxinator: |${normal} Ctrl + /")
			  $(color_blue "Fzf Marks: |${normal} Ctrl + g")
			  $(color_blue "Toggle Preview Pane: |${normal} ?")
			$(color_green "General")
			  $(color_green "pre: |${normal} ctrl + <space>")
			  $(color_blue "Command Mode: |${normal} pre + :")
			  $(color_blue "Copy Mode: |${normal} pre + Enter")
			  $(color_blue "Copy current command to clipboard: |${normal} pre + y")
			  $(color_blue "Copy current directory to clipboard: |${normal} pre + Y")
			  $(color_blue "Save Tmux Environment: |${normal} pre + Ctrl-s")
			  $(color_blue "Restore Tmux Environment: |${normal} pre + Ctrl-r")
			  $(color_blue "Reload tmux conf file: |${normal} 'tmux source-file ~/.tmux.conf'")
			$(color_green "Tree Sidebar")
			  $(color_blue "Toggle Tree Sidebar: |${normal} pre + <tab>")
			  $(color_blue "Toggle Tree Sidebar with Focus: |${normal} pre + <backspace>")
			$(color_green "Links")
			  $(color_blue "https://github.com/tmux/tmux/wiki/Getting-Started ${normal}")
			  $(color_blue "https://github.com/omerxx/tmux-sessionx ${normal}")
			  $(color_blue "https://github.com/tmux-plugins/tpm/blob/master/docs/how_to_create_plugin.md ${normal}")
		EOF
  )
  if [ -n "$1" ]; then
    command echo "$message" | grep -i "$1" | column -t -s \|
  else
    command echo "$message" | column -t -s \|
  fi
}

#@lsnano
#--> List nano commands
function lsnano() {
  echo ""
  color_green "$(print_section "Nano Commands")"
  local message
  message=$(
    cat <<-EOF
			$(color_green "File handling")
			  $(color_blue "Ctrl+S |${normal} Save current file")
			  $(color_blue "Ctrl+O |${normal} Offer to write file ("Save as")")
			  $(color_blue "Ctrl+R |${normal} Insert a file into current one")
			  $(color_blue "Ctrl+X |${normal} Close buffer, exit from nano")
			$(color_green "Editing")
			  $(color_blue "Ctrl+K |${normal} Cut current line into cutbuffer")
			  $(color_blue "Alt+6 |${normal} Copy current line into cutbuffer")
			  $(color_blue "Ctrl+U |${normal} Paste contents of cutbuffer")
			  $(color_blue "Alt+T |${normal} Cut until end of buffer")
			  $(color_blue "Ctrl+] |${normal} Complete current word")
			  $(color_blue "Alt+3 |${normal} Comment/uncomment line/region")
			  $(color_blue "Alt+U |${normal} Undo last action")
			  $(color_blue "Alt+E |${normal} Redo last undone action")
			$(color_green "Search and replace")
			  $(color_blue "Ctrl+Q |${normal} Start backward search")
			  $(color_blue "Ctrl+W |${normal} Start forward search")
			  $(color_blue "Alt+Q |${normal} Find next occurrence backward")
			  $(color_blue "Alt+W |${normal} Find next occurrence forward")
			  $(color_blue "Alt+R |${normal} Start a replacing session")
			$(color_green "Deletion")
			  $(color_blue "Ctrl+H |${normal} Delete character before cursor      ")
			  $(color_blue "Ctrl+D |${normal} Delete character under cursor")
			  $(color_blue "Alt+Bsp |${normal} Delete word to the left")
			  $(color_blue "Ctrl+Del |${normal} Delete word to the right")
			  $(color_blue "Alt+Del |${normal} Delete current line")
			$(color_green "Operations")
			  $(color_blue "Ctrl+T |${normal} Execute some command")
			  $(color_blue "Ctrl+J |${normal} Justify paragraph or region")
			  $(color_blue "Alt+J |${normal} Justify entire buffer")
			  $(color_blue "Alt+B |${normal} Run a syntax check")
			  $(color_blue "Alt+F |${normal} Run a formatter/fixer/arranger")
			  $(color_blue "Alt+: |${normal} Start/stop recording of macro")
			  $(color_blue "Alt+; |${normal} Replay macro")
			$(color_green "Moving around")
			  $(color_blue "Ctrl+B |${normal} One character backward")
			  $(color_blue "Ctrl+F |${normal} One character forward")
			  $(color_blue "Ctrl+← |${normal} One word backward")
			  $(color_blue "Ctrl+→ |${normal} One word forward")
			  $(color_blue "Ctrl+A |${normal} To start of line")
			  $(color_blue "Ctrl+E |${normal} To end of line")
			  $(color_blue "Ctrl+P |${normal} One line up")
			  $(color_blue "Ctrl+N |${normal} One line down")
			  $(color_blue "Ctrl+↑ |${normal} To previous block")
			  $(color_blue "Ctrl+↓ |${normal} To next block")
			  $(color_blue "Ctrl+Y |${normal} One page up")
			  $(color_blue "Ctrl+V |${normal} One page down")
			  $(color_blue "Alt+\ |${normal} To top of buffer")
			  $(color_blue "Alt+/ |${normal} To end of buffer")
			$(color_green "Special movement")
			  $(color_blue "Alt+G |${normal} Go to specified line")
			  $(color_blue "Alt+] |${normal} Go to complementary bracket")
			  $(color_blue "Alt+↑ |${normal} Scroll viewport up")
			  $(color_blue "Alt+↓ |${normal} Scroll viewport down")
			  $(color_blue "Alt+< |${normal} Switch to preceding buffer")
			  $(color_blue "Alt+> |${normal} Switch to succeeding buffer")
			$(color_green "Information")
			  $(color_blue "Ctrl+C |${normal} Report cursor position")
			  $(color_blue "Alt+D |${normal} Report line/word/character count")
			  $(color_blue "Ctrl+G |${normal} Display help text")
			$(color_green "Various")
			  $(color_blue "Alt+A |${normal} Turn the mark on/off")
			  $(color_blue "Tab |${normal} Indent region")
			  $(color_blue "Shift+Tab |${normal} marked region")
			  $(color_blue "Alt+V |${normal} Enter next keystroke verbatim")
			  $(color_blue "Alt+N |${normal} Turn line numbers on/off")
			  $(color_blue "Alt+P |${normal} Turn visible whitespace on/off")
			  $(color_blue "Alt+X |${normal} Hide or unhide the help lines")
			  $(color_blue "Ctrl+L |${normal} Refresh the screen")
		EOF
  )
  if [ -n "$1" ]; then
    command echo "$message" | grep -i "$1" | column -t -s \|
  else
    command echo "$message" | column -t -s \|
  fi
}

############################################################
# NEW PROJECTS
############################################################

#@new-scala-project
#--> Create new scala sbt project
function new-scala-project() {
  # Make Folders
  mkdir -p "$1" && cd "$1" || exit
  mkdir -p src/{main,test}/{java,resources,scala}
  mkdir project target

  # Make build.sbt
  touch build.sbt
  cat <<-EOF >build.sbt
		name := "$1"
		version := "1.0"
		scalaVersion := "2.13.8"

		libraryDependencies += "org.scalactic" %% "scalactic" % "3.2.12"
		libraryDependencies += "org.scalatest" %% "scalatest" % "3.2.12" % "test"
	EOF

  # Make scalaformat file
  touch .scalafmt.conf
  cat <<-EOF >.scalafmt.conf
		version = "3.5.3"
		runner.dialect = scala213
	EOF

  # TODO: [2022/10/30] - Get this from github
  # Make scala .gitignore
  touch .gitignore
  cat <<-EOF >.gitignore
		bin/
		target/
		build/
		.bloop
		.bsp
		.metals
		.cache
		.cache-main
		.classpath
		.history
		.project
		.scala_dependencies
		.settings
		.worksheet
		.DS_Store
		*.class
		*.log
		*.iml
		*.ipr
		*.iws
		.idea
	EOF
}

function checkstuff() {
  echo "Pyenv python location: $(pyenv which python)"
  echo "Pyenv python version: $(pyenv version-name)"
  echo "Python location: $(which python)"
  echo "Python version: $(python -V)"
  echo "Poetry location: $(which poetry)"
  echo "Poetry version: $(poetry --version)"
  echo "Poetry python version: $(poetry env info)"
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

######################################################################
# IP
######################################################################

#@external-ip
#--> External IP
function external-ip() {
  curl https://ipinfo.io/ip
  echo
}

#@local-ip
#--> Local IP
function local-ip() {
  ifconfig | grep inet | grep -vE '(inet6|127.0.0.1)' | awk '{print $2}' | awk -F ':' '{print $2}'
}

#@all-local-ips
#--> All local IPs
function all-local-ips() {
  ifconfig -a | grep -o 'inet6\? \(addr:\)\?\s\?\(\(\([0-9]\+\.\)\{3\}[0-9]\+\)\|[a-fA-F0-9:]\+\)' | awk '{ sub(/inet6? (addr:)? ?/, \"\"); print }'
}

#@ifactive
#--> Show active network interfaces
function ifactive() {
  ifconfig | pcregrep -M -o '^[^\t:]+:([^\n]|\n\t)*status: active'
}

############################################################
# SIZE AND COMPRESSION
############################################################

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

############################################################
# DISPLAY AND COLOR
############################################################

# Use Git’s colored diff when available
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

#@digga
#--> Run dig and display the most useful info
function digga() {
  dig +nocmd "$1" any +multiline +noall +answer
}

# # normalize `open` across Linux, macOS, and Windows.
# # This is needed to make the `o` function (see below) cross-platform.
# if [ ! "$(uname -s)" = 'Darwin' ]; then
#   if grep -q Microsoft /proc/version; then
#     # Ubuntu on Windows using the Linux subsystem
#     alias open='explorer.exe'
#   else
#     alias open='xdg-open'
#   fi
# fi

#@opendir
#--> Open current directory or given location
function opendir() {
  if [ $# -eq 0 ]; then
    open .
  else
    open "$@"
  fi
}
