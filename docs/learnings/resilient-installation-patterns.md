# Resilient Installation Patterns

**Context**: A failure during a machine build should cost one tool, not the rest of the
run.

## One bad name in a batch installs nothing at all

`brew install pkg1 pkg2 ... pkgN` validates every formula up front. It aborts the whole
command if even one name is unresolvable — a formula in a tap that was never added, for
instance. A missing `borders` tap once silently took out tmux, neovim and every other
system package in the same invocation. It surfaced phases later as `tmux: command not
found`, when tpm ran.

The fix is a batch fast-path with a per-package fallback. Attempt the batch, and on
failure retry each package on its own, so the culprits are named — `Failed to install:
borders` — instead of reported as "some packages may have failed". The slow per-package
cost is paid only once the batch has already failed.

Nothing about this is a brew problem. `apt-get install a b c` exiting 1 says just as
little about which of the three broke, which is why the isolation belongs to every
manager rather than to the one script that first needed it. `_transact` in
`src/dotfiles/registry.py` is where it lives, and registering taps runs before the batch
for the same reason an unresolvable formula aborts one.

## An is-it-installed check freezes everything it guards

An install can also succeed and then never change again. Yazi's install step was guarded
on `command -v yazi`, and yazi was more than its binary — the same step installed flavors
and plugins. Once the binary was on disk the step never ran again, so a plugin added
afterwards reached no machine that already had yazi. Nothing reported a problem, because
the step was up to date.

Any "is it installed" check that guards more than the thing it names has this bug, and
the shape outlives whatever runs it. `fzf-tmux` is a separate file beside `fzf`, and the
binary being current says nothing about whether it is still there. So a binary at the
resolved tag is not enough to call a release converged. The release provider's `evidence`
in `src/dotfiles/registry.py` asks `ghrelease.missing_companions` as well, and reports a
present binary with an absent companion as missing.

Splitting the kinds apart is the stronger version of the lesson. Yazi's plugins are
declared in `packages.yml` under `yazi_plugins` and cloned by the plugins resource, so a
step that installs one kind of thing cannot freeze another.

Never paper over the difference with `|| echo "Failed (continuing)"`. That turns a real
error into a line of output nobody reads.

## Keep structured failure data off both streams

Which stream an error lands on is the failing tool's choice, not the installer's.
Capturing one stream for the record and letting the other through therefore loses causes
at random. A failure is a returned value here rather than parsed text, so stdout and
stderr stay free to be merged and teed, live and whole. The isolation that makes this
work sits in `_act` and `_measure` in `src/dotfiles/engine.py` — one place, rather than
one call site per installer — and `dotfiles report latest` is where a failed install is
read.

## Related

- [A packages.yml Entry Is Not an Install](packages-yml-entry-is-not-an-install.md)
- [Shell Libraries](../architecture/shell-libraries.md)
