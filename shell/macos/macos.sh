# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variables referenced but not assigned (from sourced files)

SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
source "$SHELL_DIR/colors.sh"

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
  color_green "brew update"
  brew update
  echo

  color_blue "Upgrading packages..."
  color_green "brew upgrade"
  brew upgrade
  echo

  color_blue "Cleaning up old versions..."
  color_green "brew cleanup"
  brew cleanup
  echo

  color_blue "Removing unused dependencies..."
  color_green "brew autoremove"
  brew autoremove
  echo

  color_blue "Running doctor diagnostics..."
  color_green "brew doctoer"
  brew doctor
  echo

  color_green "Maintenance complete!"
}

# ------------ Terminal ------------ #

# Copy the last command to the OS clipboard
alias copycommand='fc -ln -1 | pbcopy'

# Terraform force-unlock with ID from plan
alias terraform-force-unlock='terraform force-unlock -force $(terraform plan 2>&1 | grep "ID: " | awk "{print \$NF}")'

# ---------- Directory Navigation ---------- #

alias icloud="z ~/Library/Mobile\ Documents/com~apple~CloudDocs/"

alias docs='z $HOME/code/docs'

# ---------- Logs ---------- #

# Show nginx logs (brew installed)
alias nlog="tail -f /usr/local/var/log/nginx/error.log"

# Show supervisor logs (brew installed)
alias suplog="tail -f -n 20 /usr/local/var/log/supervisor/supervisord.log"

alias locallogs="z /usr/local/var/log; ls -l"

# ---------- Operations ---------- #

# Start Github Issues Flask Server
alias issues='$HOME/code/python-projects/github-issues/.venv/bin/python $HOME/code/python-projects/github-issues/github_issues/main.py'

# Reload audio driver
alias reload-audio='sudo killall coreaudiod'

# Trim new lines and copy to clipboard
alias copytoclip="tr -d '\n' | pbcopy"

# Recursively delete `.DS_Store` files
alias delete-ds-store="find . -type f -name '*.DS_Store' -ls -delete"

# Reload local nginx and supervisor
alias reload-dev='sudo nginx -s reload && sudo supervisorctl reload'

# Symlink /etc/hosts to etc.hosts
alias symlink-hosts='sudo ln -sf $HOME/etc.hosts /etc/hosts'

# ---------- Miscellaneous ---------- #

# Audio control for greenpi
alias pausepi="ssh chris@192.168.10.40 'pacmd suspend 1'"
alias playpi="ssh chris@192.168.10.40 'pacmd suspend 0'"

# Copy shrug to clipboard
alias shrug="echo '¯\_(ツ)_/¯' | pbcopy"

# ---------- AWS ---------- #

# Source aws-profiles script to set profile (must be sourced for environment variables to persist)
alias aws-profiles='source "$HOME/.local/bin/aws-profiles"'

# ---------- Environment ---------- #

# Set ENVIRONMENT variable (formerly functions in macos-functions.sh)
alias development='export ENVIRONMENT=development'
alias testing='export ENVIRONMENT=testing'
alias production='export ENVIRONMENT=production'
