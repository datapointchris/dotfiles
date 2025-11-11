# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variable is referenced but not assigned
# *For the word formatting that comes from .color-and-formatting
# DOTFILES="$HOME/dotfiles"
SHELLS="$HOME/shell"
source "$SHELLS/colors.sh"

#@openhands
#--> Run the openhands docker container
function openhands() {
  local code_dir="$HOME/code"
  local default_repo="ichrisbirch"
  if [ -n "$1" ]; then
    repo="$1"
  else
    repo="$default_repo"
  fi
  export WORKSPACE_BASE="$code_dir/$repo"

  echo "Using $(color_blue "$WORKSPACE_BASE") as workspace base"

  docker run -it --rm --pull=always \
    -e SANDBOX_RUNTIME_CONTAINER_IMAGE=docker.all-hands.dev/all-hands-ai/runtime:0.32-nikolaik \
    -e SANDBOX_USER_ID="$(id -u)" \
    -e WORKSPACE_MOUNT_PATH="$WORKSPACE_BASE" \
    -v "$WORKSPACE_BASE:/opt/workspace_base" \
    -e LOG_ALL_EVENTS=true \
    -e LLM_NUM_RETRIES=5 \
    -e LLM_RETRY_MIN_WAIT=30 \
    -e LLM_RETRY_MAX_WAIT=150 \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v ~/.openhands-state:/.openhands-state \
    -p 3000:3000 \
    --add-host host.docker.internal:host-gateway \
    --name openhands-app \
    docker.all-hands.dev/all-hands-ai/openhands:0.32
}

#@toichrisbirch
#--> scp file or directory to ichrisbirch home dir
function toichrisbirch() {
  scp -i ~/.ssh/apps.pem "$@" ubuntu@ichrisbirch:~
}

#@reload-dev-forever
#--> Reload nginx and supervisor in a loop forever
function reload-dev-forever() {
  local char=":"
  local loops=1
  while true; do
    chars=$(printf "$char%.0s" $(seq 1 $loops))
    echo "Restarting $(color_blue "DEV") $(color_green "NGINX") and $(color_green "Supervisor") $(color_blue ": $loops ${chars}")"
    sudo nginx -s reload && sudo supervisorctl reload >>/dev/null
    loops=$((loops + 1))
    sleep 15
  done
}

#@brew-maintenance
#--> Run full brew maintenance - update, upgrade, cleanup, autoremove
function brew-maintenance() {
  color_green "$(print_section "Brew Maintenance")"
  echo

  color_blue "Updating brew..."
  color_green "brew update"
  brew update
  echo

  color_blue "Upgrading packages..."
  color_green "brew upgrade"
  brew upgrade
  echo

  color_blue "Cleaning up old versions..."
  color_green "brew cleanup"
  brew cleanup
  echo

  color_blue "Removing unused dependencies..."
  color_green "brew autoremove"
  brew autoremove
  echo

  color_blue "Running doctor diagnostics..."
  color_green "brew doctoer"
  brew doctor
  echo

  color_green "Maintenance complete!"
}

#@lsaero
#--> AeroSpace keybindings quick reference
function lsaero() {
  echo ""
  color_green "$(print_section "AeroSpace Keybindings")"
  echo ""

  color_yellow "Main Mode:"
  echo "  $(color_blue "alt + h/j/k/l")              Focus window (←/↓/↑/→)"
  echo "  $(color_blue "alt + shift + h/j/k/l")      Move window (←/↓/↑/→)"
  echo "  $(color_blue "alt + f")                    Toggle floating/tiling"
  echo "  $(color_blue "alt + shift + f")            Toggle fullscreen"
  echo "  $(color_blue "alt + tab")                  Switch to previous workspace"
  echo "  $(color_blue "alt + enter")                Open new Ghostty terminal"
  echo "  $(color_blue "alt + shift + m")            Open universal menu (new terminal)"
  echo "  $(color_blue "ctrl + alt + shift + ;")     Enter Cmd Mode"
  echo "  $(color_blue "alt + shift + ;")            Enter Service Mode"
  echo ""

  color_yellow "Cmd Mode:"
  echo "  $(color_blue "[key]")                      Go to workspace (a/b/c/d/e/m/q/s/x/y/z)"
  echo "  $(color_blue "shift + [key]")              Move window to workspace"
  echo "  $(color_blue "shift + h/j/k/l")            Join with window (←/↓/↑/→)"
  echo "  $(color_blue "ctrl + alt + h/j/k/l")       Resize window (smart/smart-opposite)"
  echo "  $(color_blue "' or \\")                    Toggle layout (tiles/accordion)"
  echo "  $(color_blue "esc")                        Return to Main Mode"
  echo ""

  color_yellow "Service Mode:"
  echo "  $(color_blue "esc")                        Reload config & return to main"
  echo "  $(color_blue "r")                          Reset layout"
  echo "  $(color_blue "f")                          Toggle floating/tiling"
  echo "  $(color_blue "backspace")                  Close all windows except current"
  echo ""
}

#@lskeys
#--> Complete keybinding reference for AeroSpace, Tmux, and Neovim
function lskeys() {
  echo ""
  color_green "$(print_section "Complete Keybinding Reference")"
  echo ""

  # AeroSpace
  color_green "═══════════ AeroSpace ═══════════"
  echo ""
  color_yellow "Navigation:"
  echo "  $(color_blue "alt + h/j/k/l")              Focus window (directional)"
  echo "  $(color_blue "alt + shift + h/j/k/l")      Move window (directional)"
  echo "  $(color_blue "alt + tab")                  Switch to previous workspace"
  echo ""
  color_yellow "Creation:"
  echo "  $(color_blue "alt + enter")                New Ghostty terminal"
  echo ""
  color_yellow "Workspace Switching:"
  echo "  $(color_blue "ctrl + alt + shift + ;")     Enter cmd mode (required)"
  echo "  $(color_blue "[letter]")                   Go to workspace (a/b/c/d/e/m/q/s/x/y/z)"
  echo "  $(color_blue "shift + [letter]")           Move window to workspace"
  echo ""
  color_yellow "Layout:"
  echo "  $(color_blue "alt + f")                    Toggle floating/tiling"
  echo "  $(color_blue "alt + shift + f")            Fullscreen"
  echo "  $(color_blue "' or \\")                    Toggle layout (in cmd mode)"
  echo ""
  color_yellow "Resize:"
  echo "  $(color_blue "ctrl + alt + j/k")           Resize smart ±50 (in cmd mode)"
  echo "  $(color_blue "ctrl + alt + h/l")           Resize opposite ±50 (in cmd mode)"
  echo ""

  # Tmux
  color_green "═══════════════ Tmux ═══════════════"
  echo ""
  color_yellow "Prefix: $(color_blue "Ctrl + Space")"
  echo ""
  color_yellow "Sessions:"
  echo "  $(color_blue "prefix + s")                 List sessions with sesh"
  echo "  $(color_blue "prefix + :new -s name")      New session"
  echo "  $(color_blue "prefix + d")                 Detach"
  echo ""
  color_yellow "Windows:"
  echo "  $(color_blue "prefix + c")                 New window"
  echo "  $(color_blue "prefix + k")                 Kill window"
  echo "  $(color_blue "prefix + n/l")               Next window"
  echo "  $(color_blue "prefix + p/h")               Previous window"
  echo "  $(color_blue "prefix + 0-9")               Select window"
  echo "  $(color_blue "prefix + </>")               Swap window left/right"
  echo ""
  color_yellow "Panes:"
  echo "  $(color_blue "prefix + |")                 Split vertical (side-by-side)"
  echo "  $(color_blue "prefix + -")                 Split horizontal (stacked)"
  echo "  $(color_blue "Ctrl + h/j/k/l")             Navigate panes (smart, vim-aware)"
  echo "  $(color_blue "Ctrl + Alt + h/j/k/l")       Resize panes (5 units)"
  echo ""
  color_yellow "Other:"
  echo "  $(color_blue "prefix + R")                 Reload config"
  echo "  $(color_blue "prefix + :")                 Command mode"
  echo "  $(color_blue "prefix + [")                 Copy mode"
  echo "  $(color_blue "prefix + P")                 Paste buffer"
  echo ""

  # Neovim
  color_green "═══════════════ Neovim ═══════════════"
  echo ""
  color_yellow "Buffers (Primary file navigation):"
  echo "  $(color_blue "<leader>fb")                 Find buffer (Telescope)"
  echo "  $(color_blue ":b [name]")                  Switch buffer"
  echo "  $(color_blue ":bnext/:bprev")              Next/previous buffer"
  echo ""
  color_yellow "Tabs (Layouts/contexts):"
  echo "  $(color_blue "<leader>te")                 New tab"
  echo "  $(color_blue "<leader>tw")                 Close tab"
  echo "  $(color_blue "<tab>/<shift-tab>")          Next/previous tab"
  echo ""
  color_yellow "Splits/Windows (Viewing multiple files):"
  echo "  $(color_blue ":vsp/:sp [file]")            Vertical/horizontal split"
  echo "  $(color_blue "Ctrl + h/j/k/l")             Navigate splits (smart, tmux-aware)"
  echo "  $(color_blue "<leader>r + h/j/k/l")        Resize splits (10 units)"
  echo "  $(color_blue "<leader>rm")                 Maximize/minimize split"
  echo "  $(color_blue ":q/<leader>qq")              Close split"
  echo ""
}

#@lsmove
#--> Visual diagram of movement/navigation keybindings
function lsmove() {
  echo ""
  color_green "$(print_section "Movement/Navigation")"
  echo ""

  color_yellow "┌─────────────────────────────────────────────────────────────┐"
  echo "$(color_yellow "│")                        $(color_green "AeroSpace")                            $(color_yellow "│")"
  echo "$(color_yellow "│")  Focus Window:        $(color_blue "alt + h/j/k/l")                         $(color_yellow "│")"
  echo "$(color_yellow "│")  Move Window:         $(color_blue "alt + shift + h/j/k/l")                 $(color_yellow "│")"
  echo "$(color_yellow "│")  Switch Workspace:    $(color_blue "alt + tab")                             $(color_yellow "│")"
  echo "$(color_yellow "│")                       $(color_blue "Ctrl+Alt+Shift+; then [key]")           $(color_yellow "│")"
  color_yellow "└─────────────────────────────────────────────────────────────┘"
  echo "                              $(color_yellow "↓")"
  color_yellow "┌─────────────────────────────────────────────────────────────┐"
  echo "$(color_yellow "│")                          $(color_green "Tmux")                               $(color_yellow "│")"
  echo "$(color_yellow "│")  Navigate Panes:      $(color_blue "Ctrl + h/j/k/l")                        $(color_yellow "│")"
  echo "$(color_yellow "│")  Switch Window:       $(color_blue "prefix + h/l")                          $(color_yellow "│")"
  echo "$(color_yellow "│")                       $(color_blue "prefix + 0-9")                          $(color_yellow "│")"
  echo "$(color_yellow "│")  Switch Session:      $(color_blue "prefix + s")                            $(color_yellow "│")"
  color_yellow "└─────────────────────────────────────────────────────────────┘"
  echo "                              $(color_yellow "↓")"
  color_yellow "┌─────────────────────────────────────────────────────────────┐"
  echo "$(color_yellow "│")                         $(color_green "Neovim")                              $(color_yellow "│")"
  echo "$(color_yellow "│")  Navigate Splits:     $(color_blue "Ctrl + h/j/k/l")                        $(color_yellow "│")"
  echo "$(color_yellow "│")  Switch Buffer:       $(color_blue "<leader>fb")                            $(color_yellow "│")"
  echo "$(color_yellow "│")                       $(color_blue ":b [name]")                             $(color_yellow "│")"
  echo "$(color_yellow "│")  Switch Tab:          $(color_blue "<tab>/<shift-tab>")                     $(color_yellow "│")"
  color_yellow "└─────────────────────────────────────────────────────────────┘"
  echo ""
  color_blue "💡 Ctrl+hjkl works seamlessly across Tmux and Neovim (vim-tmux-navigator)"
  echo ""
}

#@lsresize
#--> Visual diagram of resize keybindings
function lsresize() {
  echo ""
  color_green "$(print_section "Resize")"
  echo ""

  color_yellow "┌─────────────────────────────────────────────────────────────┐"
  echo "$(color_yellow "│")                        $(color_green "AeroSpace")                            $(color_yellow "│")"
  echo "$(color_yellow "│")  Enter Cmd Mode:      $(color_blue "Ctrl + Alt + Shift + ;")                $(color_yellow "│")"
  echo "$(color_yellow "│")  Resize Smart:        $(color_blue "Ctrl + Alt + j/k") (±50)                $(color_yellow "│")"
  echo "$(color_yellow "│")  Resize Opposite:     $(color_blue "Ctrl + Alt + h/l") (±50)                $(color_yellow "│")"
  color_yellow "└─────────────────────────────────────────────────────────────┘"
  echo "                              $(color_yellow "↓")"
  color_yellow "┌─────────────────────────────────────────────────────────────┐"
  echo "$(color_yellow "│")                          $(color_green "Tmux")                               $(color_yellow "│")"
  echo "$(color_yellow "│")  Resize Panes:        $(color_blue "Ctrl + Alt + h/j/k/l") (5 units)        $(color_yellow "│")"
  color_yellow "└─────────────────────────────────────────────────────────────┘"
  echo "                              $(color_yellow "↓")"
  color_yellow "┌─────────────────────────────────────────────────────────────┐"
  echo "$(color_yellow "│")                         $(color_green "Neovim")                              $(color_yellow "│")"
  echo "$(color_yellow "│")  Resize Splits:       $(color_blue "<leader>r + h/j/k/l") (10 units)        $(color_yellow "│")"
  echo "$(color_yellow "│")  Maximize/Minimize:   $(color_blue "<leader>rm")                            $(color_yellow "│")"
  color_yellow "└─────────────────────────────────────────────────────────────┘"
  echo ""
  color_blue "💡 Ctrl+Alt+hjkl resizes Tmux panes even from within Neovim!"
  echo ""
}

#@lssplit
#--> Visual diagram of split/create keybindings
function lssplit() {
  echo ""
  color_green "$(print_section "Split/Create")"
  echo ""

  color_yellow "┌─────────────────────────────────────────────────────────────┐"
  echo "$(color_yellow "│")                        $(color_green "AeroSpace")                            $(color_yellow "│")"
  echo "$(color_yellow "│")  New Terminal:        $(color_blue "alt + enter")                           $(color_yellow "│")"
  echo "$(color_yellow "│")  New Workspace:       $(color_blue "Ctrl+Alt+Shift+; [key]")                $(color_yellow "│")"
  echo "$(color_yellow "│")  Join Window:         $(color_blue "Shift + h/j/k/l")                       $(color_yellow "│")"
  color_yellow "└─────────────────────────────────────────────────────────────┘"
  echo "                              $(color_yellow "↓")"
  color_yellow "┌─────────────────────────────────────────────────────────────┐"
  echo "$(color_yellow "│")                          $(color_green "Tmux")                               $(color_yellow "│")"
  echo "$(color_yellow "│")  New Session:         $(color_blue "prefix + :new -s name")                 $(color_yellow "│")"
  echo "$(color_yellow "│")  New Window:          $(color_blue "prefix + c")                            $(color_yellow "│")"
  echo "$(color_yellow "│")  Split Vertical:      $(color_blue "prefix + |")                            $(color_yellow "│")"
  echo "$(color_yellow "│")  Split Horizontal:    $(color_blue "prefix + -")                            $(color_yellow "│")"
  color_yellow "└─────────────────────────────────────────────────────────────┘"
  echo "                              $(color_yellow "↓")"
  color_yellow "┌─────────────────────────────────────────────────────────────┐"
  echo "$(color_yellow "│")                         $(color_green "Neovim")                              $(color_yellow "│")"
  echo "$(color_yellow "│")  New Tab:             $(color_blue "<leader>te")                            $(color_yellow "│")"
  echo "$(color_yellow "│")  Vertical Split:      $(color_blue ":vsp [file]")                           $(color_yellow "│")"
  echo "$(color_yellow "│")  Horizontal Split:    $(color_blue ":sp [file]")                            $(color_yellow "│")"
  color_yellow "└─────────────────────────────────────────────────────────────┘"
  echo ""
  color_blue "💡 Prefer buffers (<leader>fb) over splits for file navigation!"
  echo ""
}
