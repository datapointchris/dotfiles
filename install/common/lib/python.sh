# shellcheck shell=bash

# The interpreter that can import `dotfiles`, for the installer scripts that
# still read packages.yml through it.
#
# `DOTFILES_PYTHON` is the CLI's own `sys.executable`, exported into every script
# `bridge.py` launches — so the interpreter with the dependencies is the one
# already running. No PYTHONPATH: the distribution is installed, not found on a
# path. Never the system interpreter, which is the one guaranteed to lack PyYAML.
#
# The fallback is for a phase script run by hand out of the repo. uv is safe to
# assume there for the same reason the variable is safe to assume elsewhere —
# the bootstrap installs uv before anything that could call this.
#
# Both branches disappear with the scripts that call them: once a resource owns
# its own plan/observe/diff/act, nothing shells out to ask Python a question.

dotfiles_python() {
  if [[ -n "${DOTFILES_PYTHON:-}" ]]; then
    "$DOTFILES_PYTHON" "$@"
  else
    uv run --project "${DOTFILES_DIR:?DOTFILES_DIR must be set to run python from the repo}" --quiet python "$@"
  fi
}
