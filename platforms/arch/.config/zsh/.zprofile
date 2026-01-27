#shellcheck disable=all
# Arch Linux zprofile
# Sourced on login shells

# Auto-start Hyprland on TTY1
if [[ -z "$DISPLAY" ]] && [[ $(tty) == /dev/tty1 ]]; then
    exec start-hyprland
fi
