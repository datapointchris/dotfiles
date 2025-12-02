# shellcheck shell=bash
# shellcheck disable=SC1091

if [[ -o login ]]; then echo "Login shell"; else echo "Not Login shell"; fi

SHELL_DIR="$HOME/.local/shell"

source "$SHELL_DIR/colors.sh"
source "$SHELL_DIR/formatting.sh"
source "$SHELL_DIR/functions.sh"
source "$SHELL_DIR/aliases.sh"

# Load pyenv if installed
if command -v pyenv &>/dev/null; then
    eval "$(pyenv init --path)"
fi

# Load jenv if installed (before exports so JAVA_HOME export can use jenv location)
if command -v jenv &>/dev/null; then
    eval "$(jenv init -)"
fi

# Load neofetch on Linux if installed (last so everything else has loaded first)
if command -v neofetch &>/dev/null; then
    neofetch
fi

# Load cargo environment if it exists
if [[ -f "$HOME/.cargo/env" ]]; then
    source "$HOME/.cargo/env"
fi
