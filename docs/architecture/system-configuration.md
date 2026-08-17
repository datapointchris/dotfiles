# System Configuration

A machine is not converged when its packages are installed. It still has to hold
the group memberships those packages assume, enable the units they ship, log
itself in on TTY1, point `/etc/zshenv` at the XDG config, run zsh as its login
shell, and — on a Mac — hold its `defaults` keys where this repo put them.

`install/system.yml` declares all of it. Four kinds share one mechanism and live
in `src/dotfiles/providers/sysconfig.py`. Preference keys are their own kind, in
`providers/macdefaults.py`. What is left shares no mechanism at all and is
`providers/steps.py`. Root is `src/dotfiles/privilege.py` and nowhere else. Each
of those docstrings is the account of how its own rows converge. This page holds
what no one of them can state.

## Configuration is a second file because payload is a different question

Every section of `install/packages.yml` names bytes: something that arrives from
somewhere, carries a version, and can fall behind. A group membership has none of
those properties. One file for both would make `packages` the noun a reader
reaches for to ask whether this account is in the docker group, and the `system`
resource exists so that it is not. The header of `install/system.yml` makes the
argument at the point where a row gets added.

## An entry narrows itself, and one narrowing forces a second pass

A package section is one question asked of every machine. These rows are not:
three of them can turn on three unrelated conditions, so the condition sits on
the entry instead. `SystemConfig` in `src/dotfiles/catalog.py` carries the fields
and refuses a key that is not one of them.

`requires_package` is the only narrowing that depends on the rest of the plan:
what a machine installs is settled before what a machine configures can be.
`src/dotfiles/registry.py` orders the providers so that dependency is satisfied
by position, which is what keeps it from being a special case in the resolver.

## Every read is unprivileged, and a new row has to keep it that way

`check` never escalates. That is what lets it run from a plain shell, on a timer
with nobody at the keyboard, and inside a container that has no passwordless
sudo. It holds only because every observation was chosen for a read that needs no
root, so a new row is not free to observe itself however it likes. A row that
cannot be seen unprivileged reports `UNKNOWN` with its reason instead of
guessing.

`src/dotfiles/privilege.py` holds the acquisition model and the design it
reversed.

## `steps` is the name for no shared mechanism

Rows with nothing in common except needing to be reconciled. Each is a pair of
functions in `providers/steps.py`, and `tests/resources/test_steps.py` asserts
that the declared set and the implemented set match in both directions. Two of
them are worth knowing about from here.

**The scheduled check is a `steps` row.** `providers/steps.py` hands it to
`providers/schedule.py`, which installs the timer and argues why a machine opts
in rather than getting one by default. What each run writes, when the shell
nudges about it, and when the shell stops believing a nudge are
`src/dotfiles/status.py` and `architecture/observability.md`.

**`install/wsl/docker-repo.sh` is deliberately not a row.** Nothing in the
install path runs it. WSL borrows its engine from Docker Desktop, and
`docs/configuration/docker.md` presents that script as the manual escape hatch
for a machine that cannot have Docker Desktop. Declaring it would make the
installer run it, and that page promises the reverse.

## A browser's extensions are configuration where the browser has a policy

Safari's extensions are App Store apps and Zen's come from addons.mozilla.org, so
both are declared in `packages.yml`. Vivaldi's are neither. Chromium installs
whatever an enterprise policy file names, which makes the file the declared state
and the extensions a consequence of it. So the set is a `managed_files` row and
not a `vivaldi_extensions` section with a provider behind it: writing one file is
the whole of the work, and a section would be a mechanism built for three
strings.

It takes two rows, because Linux and macOS disagree about what a policy *is*
rather than about where one lives. `install/system.yml` carries both, with the
path that took reading the binary to find and the reason a Mac cannot say this
with a preference key.

The trade is that `packages list` cannot see the three extensions, and that one
list is spelled twice in two syntaxes. That is what a section and a provider
would earn themselves against. Three strings do not.
