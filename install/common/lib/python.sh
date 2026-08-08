# shellcheck shell=bash

# The interpreter that can import `dotfiles`, for the installer scripts that
# still read packages.yml through it.
#
# There used to be one answer — /usr/bin/python3 with PYTHONPATH pointed at src/
# — and making it true cost a bootstrap on every platform: python3-yaml on apt,
# python-yaml on pacman, and `pip install --user PyYAML` into Apple's system
# interpreter. That last one had to run before the platform was known, because
# reading the manifest is what determines the platform, which is the ordering
# knot `docs/learnings/testing-bootstrap-dependencies.md` records.
#
# install.sh now installs this package with uv before any phase runs, so the
# interpreter that has the dependencies is the one already executing the CLI.
# DOTFILES_PYTHON carries it: src/dotfiles/bridge.py exports sys.executable into
# every script it launches. No PYTHONPATH, because the distribution is installed
# rather than found on a path.
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
