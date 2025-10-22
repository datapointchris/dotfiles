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
