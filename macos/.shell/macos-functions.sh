# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variable is referenced but not assigned
# *For the word formatting that comes from .color-and-formatting
# DOTFILES="$HOME/dotfiles"
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

#@toichrisbirch
#--> scp file or directory to ichrisbirch home dir
function toichrisbirch() {
  scp -i ~/.ssh/apps.pem "$@" ubuntu@ichrisbirch:~
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

#@brew-maintenance
#--> Run full brew maintenance - update, upgrade, cleanup, autoremove
function brew-maintenance() {
  color_green "$(print_section "Brew Maintenance")"
  echo

  color_blue "Updating brew..."
  brew update
  echo

  color_blue "Upgrading packages..."
  brew upgrade
  echo

  color_blue "Cleaning up old versions..."
  brew cleanup
  echo

  color_blue "Removing unused dependencies..."
  brew autoremove
  echo

  color_blue "Running diagnostics..."
  brew doctor
  echo

  color_green "Maintenance complete!"
}

#@lsaero
#--> List AeroSpace window manager keybindings
function lsaero() {
  echo ""
  color_green "$(print_section "AeroSpace Keybindings")"
  local message
  message=$(
    cat <<-EOF
			$(color_green "Main Mode - Navigation")
			  $(color_blue "alt + h/j/k/l |${normal} Focus left/down/up/right")
			  $(color_blue "alt + shift + h/j/k/l |${normal} Move window left/down/up/right")
			  $(color_blue "alt + tab |${normal} Switch to previous workspace")
			  $(color_blue "alt + enter |${normal} Open new terminal (Wezterm)")
			$(color_green "Main Mode - Mode Switching")
			  $(color_blue "ctrl + alt + shift + ; |${normal} Enter alt mode")
			  $(color_blue "alt + shift + ; |${normal} Enter service mode")
			$(color_green "Alt Mode - Workspace Navigation")
			  $(color_blue "i |${normal} iChrisBirch - Terminal workspace")
			  $(color_blue "c |${normal} iChrisBirch - Editor workspace")
			  $(color_blue "b |${normal} iChrisBirch - Panel workspace")
			  $(color_blue "t |${normal} Project - Terminal workspace")
			  $(color_blue "w |${normal} Project - Editor workspace")
			  $(color_blue "a |${normal} Project - Panel workspace")
			  $(color_blue "x/y/z |${normal} Misc workspaces")
			  $(color_blue "d |${normal} Dotfiles workspace")
			  $(color_blue "u |${normal} University workspace")
			  $(color_blue "q |${normal} Quick temporary workspace")
			  $(color_blue "e |${normal} Email workspace")
			  $(color_blue "m |${normal} Music workspace")
			  $(color_blue "s |${normal} Social workspace")
			$(color_green "Alt Mode - Move Window to Workspace")
			  $(color_blue "shift + [key] |${normal} Move current window to workspace [key]")
			$(color_green "Alt Mode - Window Joining")
			  $(color_blue "shift + h/j/k/l |${normal} Join with left/down/up/right")
			$(color_green "Alt Mode - Monitor Management")
			  $(color_blue "alt + h/l |${normal} Focus monitor left/right")
			  $(color_blue "alt + shift + h/l |${normal} Move workspace to monitor left/right")
			$(color_green "Alt Mode - Layout")
			  $(color_blue "/ |${normal} Toggle tiles layout (horizontal/vertical)")
			  $(color_blue ", |${normal} Toggle accordion layout (horizontal/vertical)")
			$(color_green "Alt Mode - Resizing")
			  $(color_blue "' |${normal} Resize smart -50")
			  $(color_blue "\\ |${normal} Resize smart +50")
			$(color_green "Service Mode")
			  $(color_blue "esc |${normal} Reload config and return to main")
			  $(color_blue "r |${normal} Reset layout (flatten workspace tree)")
			  $(color_blue "f |${normal} Toggle floating/tiling layout")
			  $(color_blue "backspace |${normal} Close all windows except current")
			$(color_green "General")
			  $(color_blue "Modes exit to main |${normal} Most commands auto-exit to main mode")
			  $(color_blue "esc in any mode |${normal} Return to main mode")
		EOF
  )
  if [ -n "$1" ]; then
    command echo "$message" | grep -i "$1" | column -t -s \|
  else
    command echo "$message" | column -t -s \|
  fi
}
