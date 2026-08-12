# System Configuration

A machine is not converged when its packages are installed. It also has to be in
the docker group, have `docker.socket` enabled, log itself in on TTY1, point
`/etc/zshenv` at the XDG config, run zsh as its login shell, and — on a Mac — hold
seventy-odd `defaults` keys at the values this repo picked. None of that is a
package, and until this conversion none of it could be checked at all.

The declaration is `install/system.yml`; the reads and writes are
`src/dotfiles/providers/sysconfig.py`; the door to root is
`src/dotfiles/privilege.py`. `dotfiles system plan` prints what would change,
`dotfiles system check` prints what is wrong, and `dotfiles apply` repairs it.

## Why it is a second file

`install/packages.yml` says what a machine installs. `packages --source
<section>` narrows to one of those sections, and every one of them names a
payload: something fetched, versioned, and upgraded. A group membership is none
of those things, so putting it there would put system configuration behind the
`packages` noun — which is exactly what a `system` resource exists to stop.

What the two files share is the *shape* of the question — declared, observed,
repaired — which is why these are catalog rows read by the same loader and not a
second mechanism bolted on beside it. A section's schema is still its dataclass,
and an unknown key is still an error at load time.

## macOS preferences are the same idea, one layer over

Seventy-three `defaults write` calls that could never be asked anything. A
setting changed by hand in System Settings, or reset by an OS upgrade, was
invisible until someone noticed the behaviour — and `defaults` has had a native,
unprivileged, exact read side the whole time.

The rows are data because the variation between them genuinely is data: a domain,
a key, a type and a value. The five `-dict-add` entries and the one
`-currentHost` entry get explicit schema fields rather than a general mechanism,
because six exceptions out of seventy-four do not justify one. A row's `name` is
*derived* from its address rather than written beside it — seventy-three
hand-written slugs would be a second spelling of a fact the row already carries,
and the derived form is the string to paste after `defaults read`.

**One export per domain, not one read per key.** `defaults export <domain> -`
emits the whole domain as XML and `plistlib` turns it into real Python values, so
a bool comes back a bool and the `-dict-add` entries are a dictionary lookup
instead of a parse of human-readable output. Seventy-four keys across fifteen
domains cost fifteen subprocesses, and the three spellings `defaults read` uses
for one boolean stop being able to disagree.

Two things there are not preference keys — `~/Library` being visible is a file
flag plus an extended attribute, and the screenshot directory existing is a
directory existing. Both are `steps` rows, described below.

**No preference escalates**, which is why `needs_root` is a field with a
per-section default rather than a resource-wide assumption. A Mac whose only
drift is its Dock size converges without a password. It is also why the provider
registry asks `needs_root(item)` rather than carrying a flat `privileged` field:
for `system.yml` the answer is per row and already declared, and a field on the
provider beside a field on the entry would be two sources for one fact.

Two decisions worth not reversing by accident. `System Settings` is quit once
before the first write of a process, because it holds its own copy of a domain
and writes it back on quit — a preference set underneath it is reverted with
nothing to say it happened. And **no app is restarted**: `killall Finder` and
friends were deliberately removed from `preferences.sh` before this conversion,
with a note reading "changes take effect on next login/reboot", so the `restart:`
field the design sketched is not here.

## `steps` is the name for no shared mechanism

Six rows with nothing in common: the scheduled check, `~/Library`'s hidden flag
and extended attribute, the screenshot directory, the Xcode licence, OrbStack's
plugin directory in `~/.config/docker/config.json`, and fontconfig pointing at
the Windows user font directory. Each is one pair of functions under
`providers/`, the shape `custom_installers` settled on — the declaration
names *which*, the code says *how*, and a test asserts the two sets match in both
directions so neither a row nothing implements nor a function nothing declares
can sit there reading as maintained.

A `check:`/`apply:` argv pair in the YAML was the alternative, and four of the
six would not fit it: a JSON merge, a path discovered by asking Windows, a unit
file compared against a serialised plist, and an observation that has to
*decline* to escalate.

Four of them are worth knowing about individually.

**The scheduled check is a row rather than something set up by hand**, because a
schedule nobody can check is a schedule that silently stops. It is a systemd
*user* timer on Linux and a LaunchAgent on macOS — user-level on both, because
the check reads `$HOME`, `~/.env` and the user's release cache, so running it as
root would measure a machine nobody uses. Every `check` writes
`$XDG_STATE_HOME/dotfiles/status.json` (the versioned document, which is also
what a differential bundle will diff against) and, only when something is an
Issue, a one-line `nudge` file. `dotfiles shell-init zsh` emits a *reader* for
that file, cached by `.zshrc` and gated on `DOTFILES_NUDGE`.

Three things there are deliberate. It **fires on Issues, not on drift** — drift
is the normal state of a machine between applies and nudging about it would train
the nudge away inside a week. The nudge is **a second file rather than a field in
the JSON**, because the reader is zsh and parsing JSON there means `jq`, which
means a subprocess at every prompt; a one-line file is `$(<file)` with no fork.
And the shell **ignores a nudge older than a day**, because a timer that stopped
running would otherwise leave a stale warning on screen with nothing to say it
had stopped being true.

Two bugs it took installing on a real machine to find, both now pinned by tests.
The unit must name the **installed** binary: `shutil.which` picked up the dev
venv's console script when the install ran through `uv run`, pinning the schedule
to a virtualenv that is rebuilt on every dependency change. And the service
declared `SuccessExitStatus=1`, because `check` exited 1 on drift and without it
the unit sat in `systemctl --user --failed` forever — which is how a real failure
comes to be ignored.

That workaround is gone, and it is worth saying why rather than just deleting it:
it existed because one verb answered two questions. Drift is `plan`'s answer now
and `check` exits 0 or 3, so a red unit means something is actually wrong and the
unit needs no exception to say so.

The same run exposed a third: `Session.resolve` read `MACHINE` only from the
environment, so a scheduled check on a machine whose `~/.env` named it exactly
failed with "MACHINE is unset". It reads the file as well now, which fixes every
non-login context — a timer, `docker exec`, cron.

**The Xcode licence is the one observation in the repo that genuinely needs
root.** `observe` is never handed a `Privilege`, so it reports `UNKNOWN` with the
reason rather than prompting from the half of the run that must never prompt. Two
cheaper questions come first and settle it without root on every machine that has
no full Xcode: no `xcodebuild` at all, or an active developer directory that is
the Command Line Tools.

**The docker config is docker's file, not this repo's.** It carries credential
helpers and proxies, so the plugin directory is merged into whatever is there and
a file that will not parse as JSON is refused rather than replaced — rewriting it
would discard what it holds.

**The Windows username is asked of Windows.** `WINDOWS_USER` is declared in
`flags.yml`, but it lives below the OVERRIDES marker in `~/.env` and is set by
hand, so it is absent during the very first install — the run that needs the font
path most. `cmd.exe /C echo %USERNAME%` is self-describing and works then.

`install/wsl/docker-repo.sh` deliberately did **not** convert. Nothing in the
install path calls it: WSL borrows the engine from Docker Desktop, and
`docs/configuration/docker.md` documents the script as the manual escape hatch
for a machine that cannot have Docker Desktop. Making it a resource would make it
something the installer runs, which is the opposite of what that page says.

## Every read is unprivileged, every write is not

This is the property the whole subsystem is built around, and it is a constraint
the providers satisfy rather than a happy accident:

| the privileged write | the unprivileged read |
| --- | --- |
| `groupadd` / `usermod -aG` | the group database |
| `systemctl enable` | `systemctl is-enabled` |
| `tee` a file under `/etc` | read it — these are all mode 0644 |
| `chsh` | the passwd entry's shell field |
| `defaults write` | `defaults export` — and it needs no privilege either way |

So `check` never escalates, which is what lets it run at a prompt, unattended on
a timer, and inside a container with no passwordless sudo. A row that
*cannot* be observed unprivileged reports `UNKNOWN` with the reason instead of
guessing — a machine with no `systemctl` is not a machine whose units drifted.

Arch's `system-config.sh` had already worked this out and could not benefit from
it. It was written as check-then-act throughout — `getent group docker`,
`systemctl is-enabled`, `grep -q autologin` — but each read was followed
immediately by the `sudo` acting on it, so running the script at all meant a
password, and nothing could ever ask it what it *would* do.

The group membership is the one read that changed on the way across. The bash
asked `id -nG`, which reports the groups of the running *session* and does not
change until the next login — so it re-ran `usermod` on every install after the
first. The provider reads the group database, which is the state `usermod`
actually wrote.

## Narrowing is per entry

The rows do not divide the way a package section does. Auto-login on TTY1
belongs to a machine whose compositor replaced its display manager; the docker
group belongs to a machine that installed docker; the system zshenv belongs to
every machine that asked for zsh. Three unrelated questions, and no single
coordinate answers them.

So an entry names the key that decides it — a coordinate, a system package it
configures, or a manifest feature — and they compose by conjunction. An entry
needing two conditions states both rather than having a combined axis invented
for it, and an axis nothing uses yet is not a field yet: adding one is two lines
in `catalog.py`, and until then declaring it is a load-time error rather than a
silently ignored key.

`requires_package` is the interesting one, because it is the only narrowing that
depends on the rest of the plan. It is why system configuration resolves in a
second pass: what a machine installs has to be known before what a machine
configures can be. The ordering is the provider registry's — each provider is
handed what the providers before it resolved, so the two passes are one loop and
`registry.PROVIDERS` puts every `system.yml` provider after every `packages.yml`
one.

## Root is acquired at the write

`privilege.py` is the only module in the package that contains the string
`sudo`, and a test asserts it over the parsed source so the prose explaining why
a module does not escalate is not itself a violation.

A privileged `perform` calls for root when it reaches the write, which is what
brew and every other installer does. Two properties matter, and the second is
what the front-loaded design existed for:

**A refusal is not fatal.** With no sudo, or with the password declined,
privilege is marked unavailable for the rest of the run: the privileged rows are
reported and everything else still converges. That is what makes the container
harnesses work without a passwordless-sudo carve-out.

**The plan says in advance how many changes will ask.** Privilege is declared on
the change and known at plan time, so `dotfiles plan` prints the count and
`--json` carries it. Nobody is surprised mid-run — they are told up front and
asked at the moment.

`observe` is never handed a `Privilege`, so "the read-only verbs do not escalate"
is structural rather than promised, and it covers `plan` and `check` alike.

**Probe with `sudo -n true`, never `sudo -v`.** `-v` authenticates, so it wants a
terminal and fails on a `NOPASSWD` box where sudo works perfectly — and the answer
is cached for the run, so one failed probe declined root for every write after it,
on every headless caller there is. Passwordless is checked before prompting is
offered, because `offer` governs whether to *ask*, not whether to escalate.

**This reverses the design that stood here.** One authorization at the front,
held open by a keepalive timer, was the rule until it was measured: keeping a
sudo timestamp alive **does not work on macOS**, repeatedly. So the front prompt
bought a property the platform will not give, and paid for it with a password
prompt on machines that turn out to need nothing. `authorize()`, `Escalation`,
`stop()` and the self-re-arming `threading.Timer` are gone, and with them the
generator-finalization hazard of a background thread outliving a run.

## A browser's extensions are configuration where the browser has a policy

Safari's extensions are App Store apps and Zen's are installed by hand from
addons.mozilla.org, so both are `packages.yml` rows — payload, fetched and
versioned. Vivaldi's are neither. Chromium reads an enterprise policy file and
installs what it names, which makes the *file* the declared state and the
extensions a consequence of it. So the whole set is a `managed_files` row rather
than a `vivaldi_extensions` section with a provider behind it: there is nothing
per-extension for a provider to do that writing one file does not already do,
and the row converges through machinery that exists.

It is two rows, because the two platforms disagree about what a policy *is*
rather than about where it lives. Linux is a JSON file in a directory Chromium
scans. macOS is a preference domain read through CFPreferences, binding only
when the domain is **forced** — which is what `/Library/Managed Preferences`
means, and why this cannot be a `macos_defaults` row: a `defaults write` into
the user domain arrives as merely *recommended*, `ExtensionInstallForcelist` has
no recommended level, and the value is discarded with nothing said. The Mac row
is device-scope rather than `/Library/Managed Preferences/<user>/`, which is
rebuilt from installed configuration profiles and so is another process's to
delete. cfprefsd caches the domain, so the extensions arrive at the next login.

The Linux row narrows on `requires_package: vivaldi`; the Mac row narrows on
`os_family`, because `requires_package` is resolved against the first pass's
`system_packages` alone and on a Mac Vivaldi is a cask, which that set cannot
see.

The trade is that `packages list` cannot see the three extensions, because they
are inside a policy document rather than rows, and that the two documents restate
one list in two syntaxes. That is the point at which a section and a provider
would earn themselves; a list of three does not.

## Three things worth not rediscovering

**Vivaldi reads `/etc/vivaldi/policies`, not `/etc/opt/vivaldi/policies`.** The
`/etc/opt/<vendor>` form is where Google-*branded* Chrome reads, and it is what
every guide and forum answer repeats. Vivaldi ships an unbranded Chromium build,
which compiles in the shorter path, so a policy file at the documented location
is read by nothing and reports no error — the extensions simply never appear.
`strings -a /opt/vivaldi/vivaldi-bin | rg '^/etc/'` settles it in one command,
and is worth preferring to any amount of documentation.

**The system zshenv is `/etc/zsh/zshenv` on Debian.** Debian builds zsh with
`--enable-etcdir=/etc/zsh`; everyone else's is `/etc/zshenv`. Writing to the
wrong one fails silently — zsh reads the other, and `~/.config/zsh/.zshrc` never
loads at all. The entry declares both and the provider picks the one whose
directory exists.

**The TTY auto-login line needs two backslashes.** `\\u` in the unit file, not
`\u`: systemd unescapes `\\` to `\` when it parses `ExecStart`, and agetty's
`-o` reads `\u` as the username. The bash wrote one, because its heredoc was
unquoted and bash ate the other before `tee` ever saw it. Nobody noticed,
because the working machine's file was correct and there was no way to compare
the two. The first `check` after this conversion found it.
