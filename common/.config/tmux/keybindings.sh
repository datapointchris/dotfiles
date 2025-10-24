#!/bin/bash

normal=$(tput sgr0)
underline=$(tput smul)
color_green() { echo "$(tput setaf 2)$1$(tput sgr0)"; }
color_blue() { echo "$(tput setaf 4)$1$(tput sgr0)"; }
print_section() { echo "${underline}        $1          ${normal}"; }

function lstmux() {
  echo ""
  color_green "$(print_section "TMUX Commands")"
  local message
  message=$(
    cat <<-EOF

			$(color_green "Menu")
			  $(color_blue "Open Menu: |${normal} pre + space")
			  $(color_blue "Show Keybindings Popup: |${normal} pre + C-p")
			$(color_green "Windows")
			  $(color_blue "New Window: |${normal} pre + c")
			  $(color_blue "Select Window: |${normal} pre + 1-9, starts at 1")
			  $(color_blue "Rename Window: |${normal} pre + ,")
			  $(color_blue "Previous Window: |${normal} pre + p")
			  $(color_blue "Next Window: |${normal} pre + n")
			  $(color_blue "Close Window: |${normal} pre + k")
			  $(color_blue "Last Active Window: |${normal} pre + l")
			$(color_green "Panes")
			  $(color_blue "Split Horizontally: |${normal} pre + {pipe}")
			  $(color_blue "Split Vertically: |${normal} pre + -")
			  $(color_blue "Rename Pane: |${normal} tmux select-pane -T 'New name'")
			  $(color_blue "Navigate panes: |${normal} pre + LRUD")
			  $(color_blue "Navigate panes: |${normal} Ctrl + hjkl")
			  $(color_blue "Resize pane: |${normal} pre + Cmd-Option-LRUD")
			  $(color_blue "Resize pane: |${normal} pre + Option-hjkl")
			  $(color_blue "Toggle last active pane: |${normal} pre + ;")
			  $(color_blue "Zoom In on pane: |${normal} pre + z")
			  $(color_blue "Close Pane: |${normal} pre + x")
			  $(color_blue "Swap with Next Pane: |${normal} pre + }")
			  $(color_blue "Swap with Previous Pane: |${normal} pre + {")
			  $(color_blue "Breakout Pane to New Window: |${normal} pre + !")
			$(color_green "Sessions")
			  $(color_blue "Rename Current Session: |${normal} pre + $")
			  $(color_blue "Detach Session: |${normal} pre + d")
			  $(color_blue "List Sessions: |${normal} tmux ls")
			  $(color_blue "New Session: |${normal} tmux new -s session_name")
			  $(color_blue "Attach Session: |${normal} tmux attach -t session_name")
			  $(color_blue "Switch Session: |${normal} tmux switch -t session_name")
			  $(color_blue "Detach from Session: |${normal} tmux detach")
			$(color_green "Copy Mode")
			  $(color_blue "Enter Copy Mode: |${normal} pre + Enter")
			  $(color_blue "Scroll Up: |${normal} pre + PageUp")
			  $(color_blue "Scroll Down: |${normal} pre + PageDown")
			  $(color_blue "Copy Selection: |${normal} pre + w")
			  $(color_blue "Exit Copy Mode: |${normal} leq")
			$(color_green "General")
			  $(color_blue "SessionX: |${normal} pre + s")
			  $(color_blue "Command Mode: |${normal} pre + :")
			  $(color_blue "Copy Mode: |${normal} pre + Enter")
			  $(color_blue "Copy current command to clipboard: |${normal} pre + y")
			  $(color_blue "Copy current directory to clipboard: |${normal} pre + Y")
			  $(color_blue "Save Tmux Environment: |${normal} pre + Ctrl-s")
			  $(color_blue "Restore Tmux Environment: |${normal} pre + Ctrl-r")
			  $(color_blue "Reload tmux conf file: |${normal} pre + Ctrl-R 'tmux source-file ~/.config/tmux/tmux.conf'")
			$(color_green "Tree Sidebar")
			  $(color_blue "Toggle Tree Sidebar: |${normal} pre + <tab>")
			  $(color_blue "Toggle Tree Sidebar with Focus: |${normal} pre + <backspace>")
			$(color_green "Links")
			  $(color_blue "https://github.com/tmux/tmux/wiki/Getting-Started ${normal}")
			  $(color_blue "https://github.com/omerxx/tmux-sessionx ${normal}")
			  $(color_blue "https://github.com/tmux-plugins/tpm/blob/master/docs/how_to_create_plugin.md ${normal}")
		EOF
  )
  if [ -n "$1" ]; then
    command echo "$message" | grep -i "$1" | column -t -s \|
  else
    command echo "$message" | column -t -s \|
  fi
}
