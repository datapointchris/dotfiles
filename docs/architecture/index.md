---
icon: material/city
---

# Architecture

How the dotfiles repository is organized and why.

## A machine is a point on six axes, not a platform string

Three trees deploy out of this repo: `configs/` into `$HOME`, `apps/` into
`~/.local/bin/`, and `shell/` into `~/.local/shell/`. Each is a common base plus
one `<axis>/<value>` directory per coordinate axis. Which of those directories a
machine takes is decided by its coordinates rather than by a platform name. So
the Wayland tree lives once under `display/wayland/`, whatever Linux runs beneath
it, and the apt helpers reach the Ubuntu work box as well as the Debian LXC.

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
[Management Interface](management-interface.md). Why two variants may never claim
one target is [Symlinks Manager](../reference/tools/symlinks.md).

## Nothing detects what a machine is

`MACHINE` is the one value chosen by hand. It selects a manifest, and the
manifest declares where the machine sits on each of the six axes in
`src/dotfiles/coordinates.py`. Detection is what the declaration replaced: a wsl
manifest whose `~/.env` was missing fell back to a guess and deployed the linux
shell layer for a whole install. A guess also cannot answer half the axes.
Network trust and capacity are intentions, and nothing on a box knows an
intention.

No coordinate reaches `~/.env` at all. `coordinate_exports` in
`src/dotfiles/envfile.py` returns nothing, and its docstring holds why: a list
shipped there is a second copy of a fact the deployed tree already carries, free
to disagree with it, and it did.

## A manifest declares names, never installers

Installation is driven by machine manifests in `install/manifests/`. Every
installed tool is declared as a name in a list, and that name must resolve to a
catalog entry in `install/packages.yml`. `dotfiles machines check` enforces the
pairing in both directions: every name reaches an entry, and every entry is
reached by a name or warned about.

Runtime installation is derived from list presence rather than from an explicit
boolean. A non-empty `go_tools:` triggers the Go runtime, and `uv_tools:` or
`git_uv_tools:` triggers uv. A manifest setting one of the retired runtime-gate
booleans is refused by name rather than reported as merely unknown, because the
replacement is not guessable from the error — `RETIRED_KEYS` in
`src/dotfiles/machine.py`.

`dotfiles machines show <name>` prints what a manifest resolves to, for any
machine including one you are not standing on. `bash install.sh --machine <name>`
bootstraps the CLI and stops, printing the `dotfiles apply` that converges the
machine.

## The Windows side is a machine, not a bridge

Admin policy on the Windows box refuses to create a symlink, so that machine
declares `deploy_by_copy` and every declared file is copied to its target
instead. What copy gives up, and why nothing is ever pruned under it, is the
module docstring in `src/dotfiles/resources/symlinks.py`.

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

## Shell layers are additive; configs and apps arrive as one file

Shell functions and aliases live in `shell/` and deploy as symlinks, with no
build step. `shell/common/` lands flat in `~/.local/shell/`. A coordinate
directory keeps its `<axis>/<value>/` path at the destination, so a sourced file
says which coordinate asked for it. `shell/` is the only tree that keeps it,
because nothing but `.zshrc` reads there.

`.zshrc` sources `common/` and then globs `~/.local/shell/*/*/*.sh`, sourcing
every one it finds and `local.sh` last. It reads no list to decide which.
`dotfiles symlinks apply` deploys only the directories this machine's coordinates
select and prunes the rest, so the tree is the resolved answer.
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

safekeep restores it rather than an installer creating it, so it is legitimately
absent between `dotfiles apply` and the restore step of a rebuild. Both consumers
guard on the file existing. `dotfiles symlinks apply` removes only links that
resolve into the repo, so a real file there survives every run untouched.

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
wants. Blocks to paste rather than a generated config, and that boundary is
load-bearing: required-to-operate is a strict subset of worth-backing-up, so
generating the whole file from the register would silently drop `~/.ssh` and
everything else the repo has no opinion about.

## Git builds its own layering on top of what arrived

`configs/` deploys variants, never a merge. Exactly one file arrives at each
destination, and the rest are versions this machine did not select. Git is the
exception, and it chains the deployed files itself through `include.path`,
last-wins.

`~/.config/git/config` is the entry point, and the only file in that directory
the repo does not own. It is a real file holding a single include of
`common.gitconfig`, written by the deploy epilogue. It has to be real rather than
a symlink for two reasons. Git writes there when `~/.gitconfig` is absent, and it
follows a symlink when writing. An entry point linked into the checkout would
commit an identity into the repo the first time anyone followed git's own "Please
tell me who you are" hint.

Everything shared ships from `configs/common/.config/git/common.gitconfig`. Below
it sits one include per variant, each named for the coordinate **value** that
supplies it rather than the axis. `wsl.gitconfig` carries `core.autocrlf`,
because a checkout on the Linux side is edited from Windows tools too, and
`fleet.gitconfig` or `nonfleet.gitconfig` carries identity. All are ignored while
absent, so a machine needing none ships nothing. Trust comes last, because its
nonfleet form overrides a default with an `includeIf` and git resolves last-wins.

Naming the value is what makes `eza ~/.config/git/` answer what the machine is.
`trust.gitconfig` would say only that the trust axis had been resolved;
`nonfleet.gitconfig` says which way. The cost is that `common.gitconfig` has to
spell every value out, because git expands nothing but `~` in an `include.path`.
`.zshrc` reaches its own layers by globbing the deployed tree and needs no list.
That asymmetry is what lets `shell/` keep `<axis>/<value>/` in its deployed path
while `configs/` flattens. `dotfiles machines check` fails on a variant gitconfig
no include names, since git would otherwise ignore the missing line without a
word.

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
point for reads and writes both, and one key given different values by two files,
where nothing on screen says which one won.

`local.gitconfig` is the one identity the repo does not ship, so
`install/flags.yml` declares it and `dotfiles check` fails while it is missing.
That declaration is load-bearing. Git ignores an absent include silently, and
`user.useConfigOnly = true` would then refuse every commit while naming nothing.
For the same reason the check runs `git config --global --includes --get`.
`--global` alone implies `--no-includes` and would report every machine unset.
The pair deliberately ignores the `includeIf`, so it reports the machine's
default rather than whatever the current directory resolves to.

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
