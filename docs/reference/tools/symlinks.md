# Symlinks Manager

Deploys this repo into `$HOME`: a common base, plus one `<axis>/<value>`
directory per coordinate axis the machine sits on. `dotfiles symlinks --help`
lists the verbs, and `dotfiles machines show` prints the point a machine sits at.

## Two of the three trees do not mirror into `$HOME`

`configs/` mirrors into `$HOME` directly. `apps/` lands in `~/.local/bin/`.
`shell/` lands in `~/.local/shell/` — shell *code*, functions and aliases,
rather than config, which is why it does not sit under `~/.config`. `TREES` in
`src/dotfiles/resources/symlinks.py` is the declaration, and its docstring says
why two of them flatten and one keeps its axis path.

An app whose job is to change the calling shell cannot live in `apps/` at all.
A symlinked command runs in its own process. It cannot export into the shell
that ran it, so it becomes a function in `shell/common/functions.sh` instead.

Go apps, and personal CLI tools like `theme` and `font`, are not symlinked. They
have their own installers — see
[App Installation Patterns](../../learnings/app-installation-patterns.md).

## The trees mean two opposite things by their coordinate directories

`configs/` and `apps/` hold **variants**. They flatten onto the destination, so
exactly one file arrives. The rest are versions this machine did not select.

`shell/` holds **layers**. Every directory this machine's coordinates select is
sourced together, and each keeps its `<axis>/<value>` path so a sourced file
says which coordinate asked for it.

## Two variants may never claim one target

Deployment is ordered, so a collision does not fail. It deploys whichever
directory comes later and reports success, which reads as an override rather
than as the bug it is. Nothing at run time can catch that, which is why
`tests/symlinks/test_coordinate_directories.py` asserts it against every machine
the axes can express rather than only the ones a manifest names today.

## Nothing is unlinked before being rewritten

A link already deployed produces no change at all, so `apply` leaves it
untouched. That closes the window a daemon watching its own config regenerates a
default inside. Hyprland found its file gone mid-pass, wrote itself a default,
and the create pass then refused the target as foreign. Never reinstate a pass
that unlinks everything first — the window is closed by deciding per link, not
by ordering two passes.
`tests/resources/test_symlinks.py::test_a_deployed_config_is_never_touched_by_a_later_run`
pins it.

## A copy machine gives up provenance, and everything built on it

A machine whose manifest sets `deploy_by_copy: true` gets the same three trees
at the same destinations, written as regular files. A copy is a regular file, so
ownership can only ever answer *foreign* for one. Provenance is what both target
refusals and the orphan prune are built out of, so all three go together:
`--force` is refused at the door, and nothing is ever pruned. A file at a path
the repo no longer declares stays where it is.

That last one is deliberate rather than a gap. Nothing on disk distinguishes a
copy this manager wrote from a file somebody put there, and the Windows box is
where the only copy of a file this repo cannot regenerate is most likely to be
sitting.

`dotfiles symlinks unlink` survives the loss by asking a different question.
Pruning has to ask about a path nothing declares, which is the question a copy
cannot answer. Unlinking asks only about paths the repo names, and every path
this mechanism has ever written is one of them.

The module docstring in `src/dotfiles/resources/symlinks.py` carries the rest of
what copy retires and why each was given up in the open.
`install/manifests/windows-work-workstation.yml` says why the boolean is
declared rather than derived from `os_family`.

## A template carries a per-machine value into a file that cannot read one

A file ending in `.tmpl` deploys without the suffix, as a regular file with its
`${NAME}` placeholders filled from `~/.env`. It is for a program that reads one
file and nothing beside it in every process that starts it. A value the program
takes from its environment reaches only processes that sourced `~/.env`, and a
timer or an `ssh host cmd` never did. atuin is the case that brought it in: it
reads `ATUIN_SYNC_ADDRESS` only while its config names no address, so without
the address in the file a timer's sync goes to api.atuin.sh.
`src/dotfiles/symlinks/template.py` holds the syntax and the write.

Every placeholder is a `required:` entry in `install/flags.yml`.
`dotfiles machines check` fails a template that fills a value some machine
selecting it is never asked for, because that machine's env check would report
nothing to set while the file stayed unrendered. An unset value is named twice by
`dotfiles check`, on the env row and on the template's, and `apply` leaves the
target as it found it.

A rendered file has the copy mode's missing provenance. `apply` overwrites
whatever is at the target, and `dotfiles symlinks unlink` removes only a file
still holding exactly this machine's rendering.

*Rejected:* a `templates/` tree with a resource of its own. It is a second walk
with a second collision domain and a new CLI noun, and one file's variants would
sit in two trees — the atuin config's nonfleet variant is a plain file under
`configs/`. *Rejected:* `managed_files` in `install/system.yml`, which writes
root-owned files with escalation and fills only `{user}`. *Rejected:* keeping the
file hand-written and checking only that it names an address, which lets every
other setting in it drift between machines.

## Prune broken links with `apply`, never with `find -delete`

`plan` finds them and `apply` repairs them by pruning, and both touch only links
resolving into this repo. A `find -delete` sweep across `$HOME` deletes every
broken link on the machine, including ones this manager never created and is not
responsible for.

`~/.local/shell/local.sh` is the file that proves the boundary matters. It is a
real file that no repo declares, holding machine-local shell code that exists
nowhere else. It survives every deploy because only a link resolving into the
source tree is ever unlinked.

## The exclusion rules carry their constraints beside the constants

`EXCLUDE_PATTERNS` decides what never gets linked, and path handling around it
has failed in two ways that are easy to reintroduce. Substring matching on
`.git/` excluded `.gitconfig`. Hand-rolled relative paths broke 122 symlinks in
one pass. Both are worked through with the failing code and the regression
assertions in
[Learnings: Symlinks Path Gotchas](../../learnings/symlinks-path-gotchas.md).

`EXCLUDE_SEARCH_DIRS` is a separate list governing where the orphan walk
descends rather than what gets linked, and `SEARCH_DEPTH` bounds how far down it
goes. Both carry their reasoning and their rejected alternatives in comments
beside them in `src/dotfiles/symlinks/core.py`, where anyone about to change a
value is already reading.

## Deciding and acting live in separate modules

`src/dotfiles/resources/symlinks.py` decides: what the repo declares, what is at
each target, and what to do about the difference. `src/dotfiles/symlinks/core.py`
holds the primitives it decides with. `src/dotfiles/deploy.py` is the epilogue
that runs after a deploy.

Decisions are tested in `tests/resources/test_symlinks.py`, which builds a whole
synthetic repo and home per test. The primitives are covered in
`tests/symlinks/`.
