---
icon: material/city
---

# Architecture

How the dotfiles repository is organized and why.

## A machine is a point on six axes, not a platform string

Which coordinate directories a machine deploys is decided by where it sits on the
axes, never by a platform name. So the Wayland tree lives once under
`display/wayland/`, whatever Linux runs beneath it, and the apt helpers reach the
Ubuntu work box as well as the Debian LXC. The trees, their destinations, and
what a coordinate directory means inside each are
[Symlinks Manager](../reference/tools/symlinks.md).

A single fused `PLATFORM` string could express neither of those. Why it was split
into axes, and why a label like `archlinux` survives as a bundle over the tuple,
is the module docstring in `src/dotfiles/coordinates.py`.

A `MACHINE_ROLE` axis — work, personal, server — was tried alongside `PLATFORM`
and dropped before the split. It was rendered from the same manifest, so it
carried no information `MACHINE` did not. It declared three values while shipping
a single file that served a single machine. That file was employer
infrastructure, which the machine-local file handles instead. That is the better
fit, because the code was never shareable in the first place.

Deploy with `dotfiles symlinks apply`, which works from any directory. `task` is
equivalent from inside the repo, and both front doors are
[Management Interface](management-interface.md).

## Nothing detects what a machine is

`MACHINE` is the one value chosen by hand. It selects a manifest, and the
manifest declares where the machine sits on each of the six axes in
`src/dotfiles/coordinates.py`. Detection is what the declaration replaced, after
a guessed platform put the wrong shell tree on a wsl box for a whole install —
the docstring in `src/dotfiles/machine.py` carries that account. A guess also
cannot answer half the axes. Network trust and capacity are intentions, and
nothing on a box knows an intention.

No coordinate reaches `~/.env` at all. `coordinate_exports` in
`src/dotfiles/envfile.py` returns nothing, and its docstring holds why, along
with the disagreement that settled it.

## A manifest declares names, never installers

Installation is driven by machine manifests in `install/manifests/`. Every
installed tool is declared as a name in a list, and that name must resolve to a
catalog entry in `install/packages.yml`. `dotfiles machines check` enforces the
pairing in both directions: every name reaches an entry, and every entry is
reached by a name or warned about.

Runtime installation is derived from list presence rather than from an explicit
boolean. A non-empty `go_tools:` triggers the Go runtime, and `uv_tools:` or
`git_uv_tools:` triggers uv. A manifest setting one of the retired runtime-gate
booleans is refused by name rather than as merely unknown — `RETIRED_KEYS` in
`src/dotfiles/machine.py` says why the name has to be spoken.

`dotfiles machines show <name>` resolves any manifest by name, not only the one
this machine runs. `bash install.sh --machine <name>` bootstraps the CLI and
stops, printing the `dotfiles apply` that converges the machine.

## The Windows side is a machine, not a bridge

Group policy on that box forbids symlink creation, so its manifest declares
`deploy_by_copy` and every declared file arrives as a regular file. The module
docstring in `src/dotfiles/resources/symlinks.py` holds what a copy gives up.
`DEPLOY_BY_COPY` beside it holds why the manifest states the fact rather than the
OS implying it.

The reasoning is inherited rather than new. Windows Git Bash cannot follow a
symlink across the WSL boundary either. So for as long as the Windows side was
reached from WSL, a script copied the files across and wrote the `.bashrc` that
loaded them. It sourced each file separately rather than concatenating them into
one `combined.sh`. Concatenating bought about 0.1ms of saved file opens against a
~60ms startup, and it turned one syntax error into a shell with no aliases or
functions at all. The script also refused to delete, for the reason the copy mode
still refuses to prune.

What that arrangement could not do is anything else a machine needs. It carried
shell files and `~/.env` and nothing more, because the Windows side was not a
machine this repo could address. It had no manifest, no coordinates and no way to
run the CLI. Declaring it as one makes its whole deploy an ordinary
`dotfiles apply`, and nothing reaches across the boundary beside that. Two owners
of one act is how a machine comes to disagree with itself about what has run.

## Nothing tells `.zshrc` which shell code to load

Shell functions and aliases live in `shell/` and deploy as symlinks, with no
build step. A machine sources every layer its coordinates select. `configs/` and
`apps/` do the opposite with their coordinate directories, and
[Symlinks Manager](../reference/tools/symlinks.md) owns that distinction.

`.zshrc` sources `common/` and then globs `~/.local/shell/*/*/*.sh`, sourcing
every one it finds and `local.sh` last. It reads no list to decide which. The
deployed tree is the resolved answer, so nothing has to be told what to load.
Most of the six axes have no directory at all, because an axis earns one only
where something actually differs along it.

### The machine-local file is declared, never shipped

`~/.local/shell/local.sh` is shell code this repo declares and deliberately never
contains: the work box's employer infrastructure, meaning internal hostnames,
share paths and Okta profiles. It is a real file among the symlinks, sourced last
so it can build on what the coordinate layers exported.

The repo knows it exists without knowing its contents. `install/flags.yml`
declares it as a `required_files` entry narrowed on `network_trust: nonfleet`
rather than on a machine name, and the comment there carries why: naming a single
machine had the Windows half of one laptop declare no need for a file it reads.
`~/.env` names the path, which is what tells a rebuild where the file goes, and
`dotfiles check` reports it missing.

safekeep restores it rather than an installer writing it, so a machine part way
through a rebuild is legitimately without one. Both consumers guard on the file
existing. `dotfiles symlinks apply` removes only links that resolve into the
repo, so a real file there survives every run untouched.

The split to hold to is mechanism versus values. Mounting a Windows share is a
WSL capability, so `mount-cifs` lives in `shell/host/wsl/wsl.sh` and takes the
share as an argument. Only the wrappers naming actual hosts go in `local.sh`.

A second test sits beside it, and it is the one that is easy to miss. A
workaround only an employer's network forces is theirs too, however generic it
looks. `update-tldr` installs tldr pages from a zip downloaded by hand, and it
reaches the Windows Downloads folder through `$winchris`. Read as a mechanism it
is plainly a WSL function. No personal WSL box would ever run it, because every
one of them can just fetch the pages. It sat in the coordinate layer for months
on the strength of the mechanism test alone.

### The register is what `apply` will never supply

`required:` and `required_files:` in `install/flags.yml` are the whole set of
things a machine needs that no apply can produce, and
`dotfiles machines requirements` is the listing. Each entry names its own
`restore:`, because where a file comes back from is a property of the file. A
credential comes from Vaultwarden rather than from a backup of the machine that
lost it.

`--safekeep` emits the files as the `[[back_up_paths]]` blocks safekeep's config
wants. Blocks to paste rather than a generated config, and `_safekeep_block` in
`src/dotfiles/commands/machines.py` holds why that boundary is load-bearing.

## Git builds its own layering on top of what arrived

One file arrives at each destination under `configs/`, and nothing merges it with
the variants a machine did not select. Git is the exception. It chains the
deployed files itself through `include.path`, last-wins.

`~/.config/git/config` is the entry point. It is a real file holding a single
include of `common.gitconfig`, written by the deploy epilogue. Both of its jobs
rule out a link, and `src/dotfiles/deploy.py` holds them beside what one there
would cost.

Everything shared ships from `configs/common/.config/git/common.gitconfig`. Below
it sits one include per variant, each named for the coordinate **value** rather
than for the axis. `wsl.gitconfig` carries `core.autocrlf`, because a checkout on
the Linux side is edited from Windows tools too, and `fleet.gitconfig` or
`nonfleet.gitconfig` carries identity. All are ignored while absent, so a machine
needing none ships nothing. Trust comes last, because its nonfleet form overrides
a default with an `includeIf` and git resolves last-wins.

Two rules hold that scheme together. Git enforces neither, so
`dotfiles machines check` does. `_git_variants` in `src/dotfiles/validate.py` is
the pair, and its docstring carries why a broken one is invisible on the machine
it breaks.

The `gh` credential helper is common rather than a variant, which is what
collapsed three near-identical files into one. It was per-platform only because
it named an absolute path — `/usr/bin/gh` on Linux, `/usr/local/bin/gh` on an
Intel Mac, and `/opt/homebrew/bin/gh` on an Apple Silicon one, a distinction no
platform string draws. `gh` unqualified resolves everywhere git runs here.

Identity rides the trust axis, because that is the thing it actually varies with.
A machine hosting employer work alongside personal needs a different default from
one hosting only personal work. A fleet machine's `fleet.gitconfig` includes
`personal.gitconfig` unconditionally, so the personal machines take their
identity from the repo and nobody sets one by hand. The personal address is in
the repo because it is already in every commit object here. Shipping it discloses
nothing, and a value the repo owns cannot drift on one machine or vanish when a
symlink is pruned.

A machine off the fleet inverts the pair. `local.gitconfig` is the default, and
`personal.gitconfig` is included behind
`includeIf "hasconfig:remote.*.url:..."`. That direction is deliberate. A repo
slipping through the match commits under the employer address, which is wrong but
internal; the reverse puts a personal address into employer history. `hasconfig`
keys on the remote rather than the checkout path, so it holds wherever a repo is
cloned. It takes two blocks, because the condition matches the URL literally and
HTTPS and SSH spell the same remote differently.

Four levels of include is more than prose can keep anyone oriented in, so
`dotfiles identity show` draws the chain this machine actually resolved — which
file contributed what, which variant is legitimately absent, and which
conditional include did not fire here. `dotfiles check` reports the two ways the
arrangement fails silently: a `~/.gitconfig`, which git prefers over the entry
point for reads and writes both, and two files setting one key to different
values.

`local.gitconfig` is the one identity this repo never ships, so
`install/flags.yml` declares it and `dotfiles check` fails while it is missing.
That declaration is load-bearing. Git ignores an absent include silently, and
`user.useConfigOnly = true` would then refuse every commit while naming nothing.
The module docstring in `src/dotfiles/resources/identity.py` holds the read that
check has to make to see an identity at all, and why a plainer one calls every
machine unset.

## The cost of the split

The common-plus-coordinate scheme buys one shared edit reaching every platform.
It charges one recurring question: does this belong in `configs/common/` or in a
coordinate directory? Getting it wrong is quiet. A setting lands in `common/`
that only one OS can honour, and the others carry it harmlessly until the day one
does not.

The test is whether the *other* platforms would want it if they could run it. A
`.gitconfig` alias belongs in common even though only one machine uses that
remote. A Homebrew path does not, because it is meaningless elsewhere rather than
merely unused. See [Tool Availability](../reference/platforms/tools.md).
