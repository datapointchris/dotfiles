# Installer Utility Libraries

Shared bash sourced by the installer scripts that are left. Everything here exists
because two or more of them needed the same thing and a copy in each was drifting.

One library is left, and that is the shape the conversion was aiming at rather
than an accident: what remains in bash is what a human runs by hand, and a
sequence of `wsl.exe` calls has no Python worth writing around it.

`rg '^[a-z_]+\(\)' <file>` lists what a library defines; each file's header
comment says what the function is for. This page is the *why each library exists*,
which is the part a reader cannot recover from the code.

## wsl-rootfs.sh

Building a WSL distribution image, which is a sequence of `wsl.exe` calls with
nothing in common with an installer.

## What is not here any more

`version-helpers.sh` compared two versions and looked up the newest GitHub
release, and `python.sh` defined `dotfiles_python` so a bash installer could read
`packages.yml` at all. Both went when the last caller did: `src/dotfiles/versions.py`
and `github_release.py` answer those questions now, and nothing sources bash to ask
them. The properties their tests asserted were moved onto the Python first — the
bundle-category read, the offline-versus-online upstream, and the release-tag
comparison shapes are in `tests/resources/test_packages.py` and
`tests/resolver/test_versions.py`.

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
