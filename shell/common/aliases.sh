# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variable is referenced but not assigned

# ------------ Terminal ------------ #

# Enable aliases to be sudo'ed
alias sudo='sudo '

# Move all files and folders including hidden to parent directory
alias move_all_to_parent='find . -maxdepth 1 -exec mv {} .. \;'

# tree should not display any gitignored files or directories
alias tree='tree --gitignore'

# Open shared network todo with neovim
alias pp='ssh ops -t "nvim ~/todo.md"'

# ---------- Directory Navigation ---------- #

# Use zoxide for smart directory navigation
alias ..='z ..'
alias ...='z ../..'
alias ....='z ../../..'

# ---------- List / Display ---------- #

# ls, ll, la and lsd are defined in functions.sh.

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

# Short git aliases in the same spirit as gst.
# ga/gd deliberately omitted: forgit claims them for interactive add/diff.
alias gp='git push'
alias gl='git pull'
