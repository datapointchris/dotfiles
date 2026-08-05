# shellcheck shell=bash

# Puts the fleet's tool directories on PATH for install.sh and update.sh.
#
# Neither entry point reads .zshenv, so nothing a phase installs is visible to
# the phase that consumes it unless it is named here: go-tools needs the Go
# toolchain, node.sh needs fnm from the cargo phase, and npm-globals needs the
# Node that node.sh links as fnm's default alias. Order mirrors .zshenv so a
# phase resolves the same binary the shell would.
#
# The fnm alias directory does not exist until the node phase creates it, which
# is harmless: PATH entries are resolved per lookup, not when PATH is set.
export PATH="$HOME/.local/share/fnm/aliases/default/bin:$HOME/.local/bin:$HOME/.cargo/bin:$HOME/go/bin:/usr/local/go/bin:/usr/local/bin:$PATH"
