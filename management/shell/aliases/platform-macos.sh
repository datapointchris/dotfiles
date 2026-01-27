# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variable is referenced but not assigned

# ------------ Terminal ------------ #

# Copy the last command to the OS clipboard
alias copycommand='fc -ln -1 | pbcopy'

# Terraform force-unlock with ID from plan
alias terraform-force-unlock='terraform force-unlock -force $(terraform plan 2>&1 | grep "ID: " | awk "{print \$NF}")'

# ---------- Directory Navigation ---------- #

alias icloud="z ~/Library/Mobile\ Documents/com~apple~CloudDocs/"

alias docs='z $HOME/code/docs'
alias icb='~/webapps/ichrisbirch/cli/ichrisbirch'

# ---------- Logs ---------- #

# Show nginx logs (brew installed)
alias nlog="tail -f /usr/local/var/log/nginx/error.log"

# Show supervisor logs (brew installed)
alias suplog="tail -f -n 20 /usr/local/var/log/supervisor/supervisord.log"

alias locallogs="z /usr/local/var/log; ls -l"

# ---------- Operations ---------- #

# Fix docker socket with colima
alias fixcolima='sudo ln -sf /Users/chris/.config/colima/default/docker.sock /var/run/docker.sock'

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

# ---------- Network ---------- #

# Homelab
alias sshicb='ssh chris@10.0.20.11'
alias sshlearn='ssh chris@10.0.20.12'
alias sshops='ssh chris@10.0.20.15'
alias sshrss='ssh chris@10.0.20.17'

# Local Computers
alias sshmbp='ssh chris@$mbp'
alias sshmacmini='ssh chris@$macmini'
alias sshgreenpi='ssh chris@$greenpi'
alias sshpython='ssh chris@$python'

# ---------- Miscellaneous ---------- #

# Audio control for greenpi
alias pausepi="ssh chris@192.168.10.40 'pacmd suspend 1'"
alias playpi="ssh chris@192.168.10.40 'pacmd suspend 0'"

# Copy shrug to clipboard
alias shrug="echo '¯\_(ツ)_/¯' | pbcopy"

# ---------- AWS ---------- #

# Source aws-profiles script to set profile (must be sourced for environment variables to persist)
alias aws-profiles='source "$HOME/.local/bin/aws-profiles"'

# ---------- Backup ---------- #

# Backup important directories to iCloud Documents
alias backup-important='backup-dirs --fast .claude learning notes obsession code'

# ---------- Environment ---------- #

# Set ENVIRONMENT variable (formerly functions in macos-functions.sh)
alias development='export ENVIRONMENT=development'
alias testing='export ENVIRONMENT=testing'
alias production='export ENVIRONMENT=production'
