
# ============================================================ #
# -------------------- OH-MY-ZSH SETTINGS -------------------- #
# ============================================================ #

export ZSH=$HOME/.oh-my-zsh

# My theme
ZSH_THEME="datapointchris"
DEFAULT_USER=chris

# Allow oh-my-zsh to auto-update without prompt
DISABLE_UPDATE_PROMPT="true"

# oh-my-zsh plugins
plugins=()

# Run oh-my-zsh 
source $ZSH/oh-my-zsh.sh

# Enable completions -> AFTER sourcing oh-my-zsh.sh
# autoload -Uz compinit && compinit


# ======================================================== #
# -------------------- SHELL SETTINGS -------------------- #
# ======================================================== #

# Settings
[ -f ~/.dotfiles/settings.sh ] && source ~/.dotfiles/settings.sh

# Exports
[ -f ~/.dotfiles/exports.sh ] && source ~/.dotfiles/exports.sh

# Aliases
[ -f ~/.dotfiles/aliases.sh ] && source ~/.dotfiles/aliases.sh

# Functions
[ -f ~/.dotfiles/functions.sh ] && source ~/.dotfiles/functions.sh

# Local customizations
[ -f ~/.zsh.local ] && source ~/.zsh.local


# ============================================== #
# -------------------- MISC -------------------- #
# ============================================== #

# Load pyenv
eval "$(pyenv init --path)"

# iTerm2 Shell Integration
test -e "${HOME}/.iterm2_shell_integration.zsh" && source "${HOME}/.iterm2_shell_integration.zsh"

# zsh-completions from Brew
# run `compaudit | xargs chmod g-w` to fix insecure directories problem
if type brew &>/dev/null; then
    FPATH=$(brew --prefix)/share/zsh-completions:$FPATH

    autoload -Uz compinit
    compinit
fi

# Syntax Highlighting -> Must be last
source /usr/local/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh