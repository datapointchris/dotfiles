# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variable is referenced but not assigned

# ------------ Terminal ------------ #

# Remove all previous aliases, some from oh-my-zsh and unnecessary git shit
unalias -a

# Enable aliases to be sudo’ed
alias sudo='sudo '

# Repeat the last command with sudo prefixed
alias please='sudo $(fc -ln -1)'

# Copy the last command to the OS clipboard
alias copycommand='fc -ln -1 | pbcopy'

# Move all files and folders including hidden to parent directory
alias move_all_to_parent='find . -maxdepth 1 -exec mv {} .. \;'

# SnowSQL command
alias snowsql='/Applications/SnowSQL.app/Contents/MacOS/snowsql'

# Terraform force-unlock with ID from plan
alias terraform-force-unlock='terraform force-unlock -force $(terraform plan 2>&1 | grep "ID: " | awk "{print \$NF}")'

# ---------- Directory Navigation ---------- #

alias ..='z ..'
alias ...='z ../..'
alias ....='z ../../..'

# Directory shortcuts
alias dl='z $HOME/Downloads'
alias dt='z $HOME/Desktop'

alias icloud="z ~/Library/Mobile\ Documents/com~apple~CloudDocs/"

alias docs='z $HOME/code/docs'
alias dots='z $HOME/dotfiles'
alias icb='ichrisbirch'
alias nconf='z $HOME/.config/nvim'

# ---------- List / Display ---------- #

# Color LS command
# Long format, human-readable, include hidden, with directory trailing `/` (same as la)
# alias ls="ls -lhAFgo --color"
alias ls="eza -l --all --git --git-repos --icons=always --group-directories-first --no-permissions --no-user --no-time"

# Long format, human-readable, with directory trailing '/'
alias ll="ls -lhF --color"

# Long format, human-readable, include hidden, with directory trailing '/'
alias la="ls -lhAF --color"

# List only directories
# alias lsdir="ls -ldh *"
alias lsd="eza -l --all --git --git-repos --icons=always --no-permissions --no-user --no-time --only-dirs"

# Print each PATH entry on a separate line
alias paths='echo -e ${PATH//:/\\n}'

# Always enable colored `grep` output
alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'

# ---------- Logs ---------- #

# open log files in less and scrolled to the bottom
alias log='less +G'

# Show all logs in /var/log
# Command: find all of type file, show file type, search for text, split on ':', take first column (file absolute path), invert match of files ending in numbers, tail the remaining files
alias varlogs="find /var/log -type f -exec file {} \; | grep 'text' | gcut -d ':' -f1 | grep -v '[0-9]$' | xargs tail -f"

# Show nginx logs (brew installed)
alias nlog="tail -f /usr/local/var/log/nginx/error.log"

# Show supervisor logs (brew installed)
alias suplog="tail -f -n 20 /usr/local/var/log/supervisor/supervisord.log"

alias locallogs="cd /usr/local/var/log; ls -l"

# ---------- Operations ---------- #

# Start Github Issues Flask Server
alias issues='$HOME/code/python-projects/github-issues/.venv/bin/python $HOME/code/python-projects/github-issues/github_issues/main.py'

# Check the python version and location
alias checkpython='python -V && which python'

# Make new Python virtual environment
alias makevenv='python -m venv .venv'

# Reset JAVA_HOME after changing with jenv
alias jenv-set-java-home='export JAVA_HOME="$HOME/.jenv/versions/`jenv version-name`"'

# Run pre-commit on all files in project
alias pca='pre-commit run --all-files'

# Reload audio driver
alias reload-audio='sudo killall coreaudiod'

# Trim new lines and copy to clipboard
alias copytoclip="tr -d '\n' | pbcopy"

# Recursively delete `.DS_Store` files
alias delete-ds-store="find . -type f -name '*.DS_Store' -ls -delete"

# Recursively delete __pycache__ files
alias remove-pycache="find . -name '__pycache__' -type d -exec rm -rf {} +"

# URL-encode string
alias urlencode='python -c "import sys, urllib as ul; print ul.quote_plus(sys.argv[1]);"'

# Kill all the tabs in Chrome to free up memory
# [C] explained: http://www.commandlinefu.com/commands/view/402/exclude-grep-from-your-grepped-output-of-ps-alias-included-in-description
alias chromekill="ps ux | grep '[C]hrome Helper --type=renderer' | grep -v extension-process | tr -s ' ' | cut -d ' ' -f2 | xargs kill"

# Reload the shell
alias reload='exec $SHELL'

# Reload local nginx and supervisor
alias reload-dev='sudo nginx -s reload && sudo supervisorctl reload'

# Reload DNS
alias reload-dns="dscacheutil -flushcache && sudo killall -HUP mDNSResponder"

# Watch listening ports for changes
alias watchports='watch -n 1 -d lsof -iTCP -sTCP:LISTEN -n -P'

# Symlink /etc/hosts to etc.hosts
alias symlink-hosts='sudo ln -sf $HOME/etc.hosts /etc/hosts'

# ---------- Network ---------- #

alias sshmbp='ssh chris@$mbp'
alias sshmacmini='ssh chris@$macmini'
alias sshgreenpi='ssh chris@$greenpi'
alias sshpython='ssh chris@$python'
alias sshichrisbirch='ssh -t -o StrictHostKeyChecking=no -i ~/.ssh/ichrisbirch-webserver.pem ubuntu@18.117.41.228'

# ---------- Miscellaneous ---------- #

# Audio control for greenpi
alias pausepi="ssh chris@192.168.10.40 'pacmd suspend 1'"
alias playpi="ssh chris@192.168.10.40 'pacmd suspend 0'"

# Copy shrug to clipboard
alias shrug="echo '¯\_(ツ)_/¯' | pbcopy"

# ---------- Git ---------- #

# Git - different from alias in gitconfig where these don't have to use `git` first
alias gst='git status'

alias commitall='git add -A; git commit -m'

alias git-alias='cat ~/.gitconfig | grep --after-context=50 "\[alias\]"'
