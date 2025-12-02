# shellcheck shell=bash
# shellcheck disable=SC1091

if [[ -o login ]]; then echo "Login shell"; else echo "Not Login shell"; fi

SHELL_DIR="$HOME/.local/shell"

source "$SHELL_DIR/exports.sh"
source "$SHELL_DIR/colors.sh"
source "$SHELL_DIR/formatting.sh"
source "$SHELL_DIR/functions.sh"

# Aliases
# Load pyenv if installed
if command -v pyenv &>/dev/null; then
    eval "$(pyenv init --path)"
fi

# Load jenv if installed (before exports so JAVA_HOME export can use jenv location)
if command -v jenv &>/dev/null; then
    eval "$(jenv init -)"
fi

if [[ $(uname) == "Linux" && $(whoami) == "ubuntu" ]]; then
    source "$SHELL_DIR/aliases-ec2.sh"

    # Load neofetch on Linux if installed (last so everything else has loaded first)
    if command -v neofetch &>/dev/null; then
        neofetch
    fi
else
    source "$SHELL_DIR/aliases.sh"
fi
. "/Users/chris/.local/share/cargo/env"
