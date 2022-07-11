#!/usr/bin/env bash

# ================================== #
# ---------- System Setup ---------- #

# Remove all previous aliases, some from oh-my-zsh and unnecessary git shit
unalias -m '*' 

# Enable aliases to be sudo’ed
alias sudo='sudo '

# Repeat the last command with sudo prefixed
alias please='sudo $(fc -ln -1)'

# Copy the last command to the OS clipboard
alias copycommand="fc -ln -1 | pbcopy"

# ========================================== #
# ---------- Directory Navigation ---------- #

alias ..="cd .."
alias ...="cd ../.."
alias ....="cd ../../.."

# Directory shortcuts
alias dl="cd $HOME/Downloads"
alias dt="cd $HOME/Desktop"
alias pj="cd $HOME/github/projects"
alias apps="cd $HOME/github/apps"
alias icloud="cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/"


# ==================================== #
# ---------- List / Display ---------- #

# Long format, human-readable, with directory trailing `/`
alias ll="ls -lhF"

# Long format, human-readable, include hidden, with directory trailing `/`
alias la="ls -lhAF"

# List only directories
alias lsd="ls -ldh */"

# chmod octal permissions
alias lsperm="ls -lhAF --color | awk '{k=0;for(i=0;i<=8;i++)k+=((substr(\$1,i+2,1)~/[rwx]/)*2^(8-i));if(k)printf(\"%0o \",k);print}'"

# Print each PATH entry on a separate line
alias path='echo -e ${PATH//:/\\n}'

# Show all logs in /var/log
alias logs="sudo find /var/log -type f -exec file {} \; | grep 'text' | cut -d'$()' -f1 | sed -e's/:$//g' | grep -v '[0-9]$' | xargs tail -f"

# External IP
alias extip="dig +short myip.opendns.com @resolver1.opendns.com"

# Local IP
alias localip="ifconfig | grep inet | grep -vE '(inet6|127.0.0.1)' | awk '{print $2}' | awk -F ':' '{print $2}'"

# All local IPs
alias ips="ifconfig -a | grep -o 'inet6\? \(addr:\)\?\s\?\(\(\([0-9]\+\.\)\{3\}[0-9]\+\)\|[a-fA-F0-9:]\+\)' | awk '{ sub(/inet6? (addr:)? ?/, \"\"); print }'"

# Show active network interfaces
alias ifactive="ifconfig | pcregrep -M -o '^[^\t:]+:([^\n]|\n\t)*status: active'"

# Always enable colored `grep` output
alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'


# ================================ #
# ---------- Operations ---------- #

# Make new Python virtual environment
alias makevenv='python -m venv .venv'

# Activate Python virtual environment
alias venv='source .venv/bin/activate'

# Reset JAVA_HOME after changing with jenv
alias jenv_set_java_home='export JAVA_HOME="$HOME/.jenv/versions/`jenv version-name`"'

# Reload audio driver
alias reload-audio='sudo killall coreaudiod'

# Trim new lines and copy to clipboard
alias c="tr -d '\n' | pbcopy"

# Recursively delete `.DS_Store` files
alias cleanup="find . -type f -name '*.DS_Store' -ls -delete"

# Empty the Trash on all mounted volumes and the main HDD.
# Also, clear Apple’s System Logs to improve shell startup speed.
# Finally, clear download history from quarantine. https://mths.be/bum
alias emptytrash="sudo rm -rfv /Volumes/*/.Trashes; sudo rm -rfv ~/.Trash; sudo rm -rfv /private/var/log/asl/*.asl; sqlite3 ~/Library/Preferences/com.apple.LaunchServices.QuarantineEventsV* 'delete from LSQuarantineEvent'"

# Hide/show all desktop icons (useful when presenting)
alias hidedesktop="defaults write com.apple.finder CreateDesktop -bool false && killall Finder"
alias showdesktop="defaults write com.apple.finder CreateDesktop -bool true && killall Finder"

# URL-encode strings
alias urlencode='python -c "import sys, urllib as ul; print ul.quote_plus(sys.argv[1]);"'

# Merge PDF files, preserving hyperlinks
# Usage: `mergepdf input{1,2,3}.pdf`
alias mergepdf='gs -q -dNOPAUSE -dBATCH -sDEVICE=pdfwrite -sOutputFile=_merged.pdf'

# PlistBuddy alias, because sometimes `defaults` just doesn’t cut it
alias plistbuddy="/usr/libexec/PlistBuddy"

# Kill all the tabs in Chrome to free up memory
# [C] explained: http://www.commandlinefu.com/commands/view/402/exclude-grep-from-your-grepped-output-of-ps-alias-included-in-description
alias chromekill="ps ux | grep '[C]hrome Helper --type=renderer' | grep -v extension-process | tr -s ' ' | cut -d ' ' -f2 | xargs kill"

# Lock the screen (when going AFK)
alias afk="/System/Library/CoreServices/Menu\ Extras/User.menu/Contents/Resources/CGSession -suspend"

# Reload the shell (i.e. invoke as a login shell)
alias reload="exec ${SHELL} -l"

# Reload DNS
alias reloaddns="dscacheutil -flushcache && sudo killall -HUP mDNSResponder"


# ============================= #
# ---------- Network ---------- #

# Easy SSH
alias sshmbp="ssh chris@$MBP_IP"
alias sshmacmini="ssh chris@$MACMINI_IP"
alias sshgreenpi="ssh chris@$GREENPI_IP"
alias sshpython="ssh chris@$PYTHON_IP"
alias ssheuphoria="ssh -ti ~/.ssh/apps.pem ubuntu@$EUPHORIA_IP 'cd /var/www/euphoria; bash'"
# alias euphoria="ssh -i ~/.ssh/apps.pem ubuntu@18.205.159.66 'cd /var/www/euphoria && git pull'"

# Audio control for greenpi
alias pausepi="ssh chris@192.168.10.40 'pacmd suspend 1'"
alias playpi="ssh chris@192.168.10.40 'pacmd suspend 0'"

# Copy markdown files
alias copymarkdown="rsync -ave ssh -i ~/.ssh/apps.pem --exclude=apps.pem --exclude=_gsdata_ ~/Documents/brain/Unstructured\ Structure/ ubuntu@$EUPHORIA_IP:/var/www/euphoria/euphoria/tracks/static/markdown"


# =================================== #
# ---------- Miscellaneous ---------- #

# Copy shrug to clipboard
alias shrug="echo '¯\_(ツ)_/¯' | pbcopy"


# ========================= #
# ---------- Git ---------- #

# Git - different from alias in gitconfig where these don't have to use `git` first
alias gst="git status"
alias gb="git branch"
alias gc="git checkout"
alias gitadmit="git add . && git commit -m"


# ========================================== #
# ---------- Program associations ---------- #

alias -s md=code

# Visual Studio Code
alias -s {css,ts,html,py,r,json}=code