# shellcheck shell=bash

# Puts the fleet's tool directories on PATH for install.sh and update.sh.
#
# Neither entry point reads .zshenv, so nothing a phase installs is visible to
# the phase that consumes it unless it is named here: the cargo provider needs
# cargo from rustup, the node toolchain needs the fnm that arrives as a cargo
# package, and npm-globals needs the Node that fnm links as its default alias.
# Order mirrors .zshenv so a phase resolves the same binary the shell would.
#
# The fnm alias directory does not exist until the node phase creates it, which
# is harmless: PATH entries are resolved per lookup, not when PATH is set.
export PATH="$HOME/.local/share/fnm/aliases/default/bin:$HOME/.local/share/npm/bin:$HOME/.local/bin:$HOME/.cargo/bin:$HOME/go/bin:/usr/local/go/bin:/usr/local/bin:$PATH"
