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
`--force` is refused at the door, and no copy is ever pruned. A copy at a path
the repo no longer declares stays where it is.

Leaving that copy is deliberate rather than a gap. Nothing on disk distinguishes
a copy this manager wrote from a file somebody put there, and the Windows box is
where the only copy of a file this repo cannot regenerate is most likely to be
sitting. A rendering of a deleted template is still pruned there, because the
template's history tells it apart from somebody's file.

`dotfiles symlinks unlink` survives the loss by asking a different question.
Pruning has to ask about a path nothing declares, which is the question a copy
cannot answer. Unlinking asks about a copy only at a path the repo declares,
where comparing bytes answers it.

The module docstring in `src/dotfiles/resources/symlinks.py` carries the rest of
what copy retires and why each was given up in the open.
`install/manifests/windows-work-workstation.yml` says why the boolean is
declared rather than derived from `os_family`.

## A template carries a per-machine value into a file that cannot read one

A file ending in `.tmpl` deploys without the suffix, as a regular file with its
`${NAME}` placeholders filled from `~/.env`. It is for a program that reads its
one config file in every process, such as atuin. A value the program takes from
its environment reaches only processes that sourced `~/.env`, and an
`ssh host cmd` never does. `src/dotfiles/symlinks/template.py` holds the syntax
and the write.

Every placeholder is a `required:` entry in `install/flags.yml`.
`dotfiles machines check` fails a template whose placeholder some machine
selecting it is never asked for. On that machine only the template's own row
would name the value. The env check and the generated block in `~/.env` list
only the machine's `required:` entries. An unset value is named twice by
`dotfiles check`: on the env row and on the template's. `apply` leaves the
target as it found it.

A rendered file is a regular file, so the template stands in for the provenance
a link carries. A target matching the template is this manager's earlier
rendering, whatever stands where a placeholder sits. `apply` renders over it and
`dotfiles symlinks unlink` removes it. Anything else is somebody's file, and
`apply` refuses it like a foreign link unless given `--force`. A copy machine
refuses it too, because the template can tell the two apart where a copy
cannot.

A template deleted from the repo takes its renderings with it. A rendering points
nowhere, so the broken-link scan never finds one. Git holds the provenance
instead: every template the repo deleted, and every text each one held. `observe`
places each deleted template through the source directories this machine selects.
Where nothing declares that target now, a regular file there is fitted against
every text the template held. A fit is this manager's rendering, and `apply`
removes it. Anything else may hold an edit that exists nowhere else, so it is
reported `undeclared` and left in place. `dotfiles symlinks unlink` takes back
the same renderings.

This is the previous-generation diff home-manager runs at activation, removing
what the old generation listed and the new one does not. home-manager stores each
generation. Here git already holds them, so nothing new is stored. *Rejected:* a
state file recording what each apply rendered. It is a second record of what git
already holds, and a machine that lost it would keep its renderings for good.
*Rejected:* an explicit removal list, as chezmoi's `.chezmoiremove` is. Every
template deletion would need a second edit, and the forgotten edit is the failure
this prevents.

A program writing exactly the text a deleted template rendered loses that file at
the next apply. That matters for a template written to equal what a CLI's own
login writes. A machine whose coordinates changed after it rendered a template
keeps that rendering, because only the directories it selects now are searched.
A target the repo still declares is never pruned. So a template replaced by a
plain file, or moved and edited in one commit, leaves its old rendering to that
target's own row, which refuses it as somebody's file.

*Rejected:* a `templates/` tree with a resource of its own. It is a second walk
with a second collision domain and a new CLI noun, and one file's variants would
sit in two trees: the atuin config's nonfleet variant is a plain file under
`configs/`. *Rejected:* `managed_files` in `install/system.yml`, which writes
root-owned files with escalation and fills only `{user}`. *Rejected:* keeping the
file hand-written and checking only that it names an address, which lets every
other setting in it drift between machines. *Rejected:* a linked config naming no
address, leaving atuin to read `ATUIN_SYNC_ADDRESS` itself. An interactive shell
then syncs to the right server, while `ssh host atuin doctor` on the same machine
reports atuin's hosted service.

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
