# shellcheck shell=bash

# Use VSCode as default editor (git, etc.)
export EDITOR="nvim"

# Disable brew auto update
export HOMEBREW_NO_AUTO_UPDATE=1

# Set bat theme
export BAT_THEME="gruvbox-dark"

# Cargo if installed
if command -v cargo &>/dev/null; then
  CARGO_HOME="$XDG_DATA_HOME/cargo"
  export CARGO_HOME
fi

# Java if installed
if command -v jenv &>/dev/null; then
  JAVA_HOME="$HOME/.jenv/versions/$(jenv version-name)"
  export JAVA_HOME
fi

# Spark is installed into /usr/local/bin
# Already in PATH

# Scala if installed
if command -v scala &>/dev/null; then
  SCALA_HOME="/usr/local/opt/scala@2.12"
  export SCALA_HOME
fi

# Pyenv
if command -v pyenv &>/dev/null; then
    PYENV_ROOT="$XDG_DATA_HOME/pyenv"
    export PYENV_ROOT
fi

# Adds path to PATH if path exists.
function add_path {
  if [ -d "$1" ]; then
    export PATH="$1:$PATH"
  fi
}

# !! First !!
# gpg 2.2.41 to match ubuntu versions
# add_path "/usr/local/opt/gnupg@2.2/bin"

# Node 18 instead of regular node which is 19
add_path "/usr/local/opt/node@18/bin"

# Postgres 16, `postgres` points to Postgres 14
add_path "/usr/local/opt/postgresql@16/bin"

# SnowSQL since it is an Application
add_path "/Applications/SnowSQL.app/Contents/MacOS"

# Local bin
add_path "$HOME/.local/bin"

# Brew
add_path "/usr/local/sbin"
add_path "/usr/local/bin"

# Jenv
add_path "$HOME/.jenv/bin/"

# Java
add_path "$JAVA_HOME/bin"

# Scala 2.12
add_path "$SCALA_HOME/bin"

# Pyenv
add_path "$PYENV_ROOT/bin"

# Cargo
add_path "$CARGO_HOME/env"
