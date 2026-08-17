# Tool Availability

What is installed on a machine is `doit kit list`, or
`packages list --section=<section>` for one install method. This page covers
only the tools where the *choice* of method needed a decision, and the
per-platform quirks that decision produced.

## Binary names are uniform on every platform

`~/.local/bin` is the user binary directory everywhere, and a tool answers to
the same name on every machine. The Ubuntu `batcat`/`fdfind` rename never
arises, because `bat` and `fd` install through `cargo binstall` rather than apt.
That uniformity is a consequence of the
[package strategy](../../architecture/package-management.md), not an accident.

## atuin is the one split-method tool

atuin installs from GitHub releases on Linux, like fzf and neovim. macOS falls
back to Homebrew. Upstream publishes no Intel-macOS release binary, only Apple
Silicon, and `cargo binstall` would fall through to compiling from source.
brew's bottle covers both Mac architectures. So every Mac takes brew while every
other platform takes the uniform GitHub-releases path.

## fnm reaches non-interactive shells, and nvm cannot

Node.js versions come from **fnm**, installed as a cargo package. Repos across
the portfolio pin different versions in `.nvmrc` — several want 24, meso wants
26. Running the wrong one is not a subtle failure: ichrisbirch's frontend suite
dies outright on 26 with `localStorage is undefined`.

`src/dotfiles/providers/toolchain.py` installs the fleet default and links it
as fnm's `default` alias. `.zshenv` puts `~/.local/share/fnm/aliases/default/bin`
on PATH ahead of everything else. Scripts, editors, agents and pre-commit hooks
therefore resolve `node` to that version with no shell integration at all.
`.zshrc` layers `fnm env --use-on-cd` over it, so entering a directory with an
`.nvmrc` switches.

nvm is a shell function defined in `.zshrc`, so it does not exist in a
non-interactive shell. fnm is a binary, so the default alias and `fnm exec` work
anywhere. Dropping nvm on the grounds that per-project switching was unused was
the wrong diagnosis of a real problem.

The brew/pacman `node` package stays declared, but only as the bootstrap npm the
installer needs before fnm has fetched anything.

## npm's prefix is set twice, because the two stages run in the wrong order

npm's global prefix points at `~/.local/share/npm` through an XDG-located user
config at `~/.config/npm/npmrc`, deployed from
`configs/common/.config/npm/npmrc`. `.zshrc` points npm at that file by
exporting `NPM_CONFIG_USERCONFIG`. This keeps globally-installed tools — LSPs,
formatters — in a user-writable location, independent of the Node.js package
itself. On Arch, where system npm's default prefix is `/usr`, it is what makes
`npm install -g` work without sudo.

The installing side cannot rely on that file. The npmrc is a symlink, and the
symlink stage runs *after* the npm one. On a first install the file does not
exist yet, npm falls back to its built-in prefix, and every global install dies
with EACCES. So `src/dotfiles/providers/npm.py` passes `NPM_CONFIG_PREFIX` on
every call. The environment variable outranks every config file, so it holds in
both orders.

## Platform-Specific Quirks

=== "macOS"

    GNU coreutils install from Homebrew under unprefixed names, prepended to
    PATH. GNU therefore wins over BSD in scripts as well as in interactive
    shells, so write GNU syntax — `sed -i`, never `sed -i ''`.

    Homebrew's prefix differs by architecture: `/usr/local` on Intel,
    `/opt/homebrew` on Apple Silicon. `BREW_PREFIXES` in
    `src/dotfiles/providers/bootstrap.py` is the pair every caller resolves
    through, so nothing hardcodes one.

=== "Ubuntu/WSL"

    Fonts install to Windows with no manual step and no admin rights, because
    the per-user font directory under `%LOCALAPPDATA%` needs neither. The
    `windows-fonts` step in `install/system.yml` installs them and points
    fontconfig at that directory, so `fc-list` and the `font` CLI both see what
    Windows has.

    `/etc/wsl.conf` belongs to the distro and this repo does not deploy it.
    `apps/host/wsl/wsl-tools` reports what it holds and what each setting buys —
    most usefully that `appendWindowsPath=false` is what takes the Windows
    directories back off PATH.
