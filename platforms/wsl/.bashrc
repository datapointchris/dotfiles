# shellcheck shell=bash
# shellcheck disable=SC1091

if [[ -o login ]]; then echo "Login shell"; else echo "Not Login shell"; fi

SHELLS="$HOME/.shell"

source "$SHELLS/exports.sh"
source "$SHELLS/colors.sh"
source "$SHELLS/formatting.sh"
source "$SHELLS/functions.sh"

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
    source "$SHELLS/aliases-ec2.sh"

    # Load neofetch on Linux if installed (last so everything else has loaded first)
    if command -v neofetch &>/dev/null; then
        neofetch
    fi
else
    source "$SHELLS/aliases.sh"
fi
. "/Users/chris/.local/share/cargo/env"
