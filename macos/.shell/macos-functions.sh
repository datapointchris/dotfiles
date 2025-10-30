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
#--> AeroSpace keybindings quick reference
function lsaero() {
  echo ""
  color_green "$(print_section "AeroSpace Keybindings")"
  echo ""

  color_green "Main Mode:"
  echo "  $(color_blue "alt + h/j/k/l")              Focus window (←/↓/↑/→)"
  echo "  $(color_blue "alt + shift + h/j/k/l")      Move window (←/↓/↑/→)"
  echo "  $(color_blue "alt + , / .")                Focus monitor (←/→)"
  echo "  $(color_blue "alt + shift + , / .")        Move window to monitor (←/→)"
  echo "  $(color_blue "alt + tab")                  Switch to previous workspace"
  echo "  $(color_blue "alt + enter")                Open new Ghostty terminal"
  echo "  $(color_blue "ctrl + alt + shift + ;")     Enter Cmd Mode"
  echo "  $(color_blue "alt + shift + ;")            Enter Service Mode"
  echo ""

  color_green "Cmd Mode:"
  echo "  $(color_blue "[key]")                      Go to workspace (a/b/c/d/e/m/q/s/x/y/z)"
  echo "  $(color_blue "shift + [key]")              Move window to workspace"
  echo "  $(color_blue "shift + h/j/k/l")            Join with window (←/↓/↑/→)"
  echo "  $(color_blue "- / =")                      Resize window (-50/+50)"
  echo "  $(color_blue "/ or ,")                     Toggle layout (tiles/accordion)"
  echo "  $(color_blue "alt + h/l")                  Focus monitor (←/→)"
  echo "  $(color_blue "alt + shift + h/l")          Move workspace to monitor (←/→)"
  echo "  $(color_blue "esc")                        Return to Main Mode"
  echo ""

  color_green "Service Mode:"
  echo "  $(color_blue "esc")                        Reload config & return to main"
  echo "  $(color_blue "r")                          Reset layout"
  echo "  $(color_blue "f")                          Toggle floating/tiling"
  echo "  $(color_blue "backspace")                  Close all windows except current"
  echo ""
}
