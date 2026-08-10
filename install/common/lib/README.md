# Installer Utility Libraries

Shared bash sourced by the installer scripts that are left. Everything here exists
because two or more of them needed the same thing and a copy in each was drifting.

`rg '^[a-z_]+\(\)' <file>` lists what a library defines; each file's header
comment says what the function is for. This page is the *why each library exists*,
which is the part a reader cannot recover from the code.

## version-helpers.sh

Version comparison and the GitHub releases lookup, for the two scripts that still
ask those questions in bash — the offline connectivity probe and the installed
package verification. `src/dotfiles/versions.py` is the same logic for everything
that has converted, and `tests/shell/test_version_helpers_sh.py` pins the two to
the same answers.

## python.sh

Defines `dotfiles_python` as the CLI's own `sys.executable`, never the system
interpreter. The one thing a bash installer needs in order to read `packages.yml`
at all.

## wsl-rootfs.sh

Building a WSL distribution image, which is a sequence of `wsl.exe` calls with
nothing in common with an installer.

## What is not here any more

`failure-logging.sh` appended a JSON record per failure to `$FAILURE_RECORDS` for
the wrapper to render when an installer exited. It went with the last two
installers — TPM's and lazy.nvim's — because a provider returns an `Outcome` and a
run record already holds every one of them, so a second channel out of a
subprocess had nothing left to carry.

`installed-versions.sh`, `package-query.sh`, `missing-tools.sh` and
`uv-git-tools.sh` served `update.sh`, which is gone: reconcile has one verb, and
`dotfiles apply` installs what is missing and upgrades what is behind. Each of
them answered "what changed" by snapshotting state either side of a command that
exits 0 whether or not anything moved; a `Change` says what moved and why, so
there is nothing left to diff. The pin reasoning that lived in `uv-git-tools.sh`
is in `src/dotfiles/providers/uvtool.py`, which is what installs those tools now.
