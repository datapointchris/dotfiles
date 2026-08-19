# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variables referenced but not assigned (from sourced files)

# ------------ Terminal ------------ #

# Copy the last command to the OS clipboard
alias copycommand='fc -ln -1 | pbcopy'

# Terraform force-unlock with ID from plan
alias terraform-force-unlock='terraform force-unlock -force $(terraform plan 2>&1 | grep "ID: " | awk "{print \$NF}")'

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

# ---------- Miscellaneous ---------- #

# Audio control for greenpi
alias pausepi="ssh chris@192.168.10.40 'pacmd suspend 1'"
alias playpi="ssh chris@192.168.10.40 'pacmd suspend 0'"

# Copy shrug to clipboard
alias shrug="echo '¯\_(ツ)_/¯' | pbcopy"

# ---------- Environment ---------- #

# Set ENVIRONMENT variable
alias development='export ENVIRONMENT=development'
alias testing='export ENVIRONMENT=testing'
alias production='export ENVIRONMENT=production'
