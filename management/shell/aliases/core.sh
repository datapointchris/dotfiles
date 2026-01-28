# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variable is referenced but not assigned

# ------------ Terminal ------------ #

# Enable aliases to be sudo'ed
alias sudo='sudo '

# Run claude with open permissions
alias risky="claude --dangerously-skip-permissions"

# Repeat the last command with sudo prefixed
alias please='sudo $(fc -ln -1)'

# Move all files and folders including hidden to parent directory
alias move_all_to_parent='find . -maxdepth 1 -exec mv {} .. \;'

# Go to base of current git directory
alias base='z $(git rev-parse --show-toplevel)'

alias y='yazi'

# Open shared network todo with neovim
alias pp='ssh chris@10.0.20.15 -t "nvim ~/todo.md"'

# ---------- Directory Navigation ---------- #

# Use zoxide for smart directory navigation
alias ..='z ..'
alias ...='z ../..'
alias ....='z ../../..'

# Directory shortcuts using zoxide
alias dl='z $HOME/Downloads'
alias dt='z $HOME/Desktop'

alias dots='z $HOME/dotfiles'
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

# Show all logs in /var/log
# Command: find all of type file, show file type, search for text, split on ':', take first column (file absolute path), invert match of files ending in numbers, tail the remaining files
alias varlogs="find /var/log -type f -exec file {} \; | grep 'text' | gcut -d ':' -f1 | grep -v '[0-9]$' | xargs tail -f"

# ---------- Operations ---------- #

# Check the python version and location
alias checkpython='python -V && which python'

# Make new Python virtual environment
alias makevenv='python -m venv .venv'

# Run pre-commit on all files in project
alias pca='pre-commit run --all-files'

# Recursively delete __pycache__ files
alias remove-pycache="find . -name '__pycache__' -type d -exec rm -rf {} +"

# URL-encode string
alias urlencode='python -c "import sys, urllib as ul; print ul.quote_plus(sys.argv[1]);"'

# Kill all the tabs in Chrome to free up memory
# [C] explained: http://www.commandlinefu.com/commands/view/402/exclude-grep-from-your-grepped-output-of-ps-alias-included-in-description
alias chromekill="ps ux | grep '[C]hrome Helper --type=renderer' | grep -v extension-process | tr -s ' ' | cut -d ' ' -f2 | xargs kill"

# Reload the shell
alias reload='exec $SHELL'

# Reload DNS
alias reload-dns="dscacheutil -flushcache && sudo killall -HUP mDNSResponder"

# Watch listening ports for changes
alias watchports='watch -n 1 -d lsof -iTCP -sTCP:LISTEN -n -P'

# ---------- Miscellaneous ---------- #

# ---------- Git ---------- #

# Git - different from alias in gitconfig where these don't have to use `git` first
alias gst='git status'

alias commitall='git add .; git commit -m'

alias git-alias='cat ~/.gitconfig | grep --after-context=50 "\[alias\]"'
