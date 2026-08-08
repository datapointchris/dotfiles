# System Configuration

A machine is not converged when its packages are installed. It also has to be in
the docker group, have `docker.socket` enabled, log itself in on TTY1, point
`/etc/zshenv` at the XDG config, run zsh as its login shell, and — on a Mac — hold
seventy-odd `defaults` keys at the values this repo picked. None of that is a
package, and until this conversion none of it could be checked at all.

The declaration is `install/system.yml`; the reads and writes are
`src/dotfiles/providers/sysconfig.py`; the one authorization is
`src/dotfiles/privilege.py`. `dotfiles system check` prints where the machine
stands and `dotfiles apply` repairs it.

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
drift is its Dock size converges without a password.

Two decisions worth not reversing by accident. `System Settings` is quit once
before the first write of a process, because it holds its own copy of a domain
and writes it back on quit — a preference set underneath it is reverted with
nothing to say it happened. And **no app is restarted**: `killall Finder` and
friends were deliberately removed from `preferences.sh` before this conversion,
with a note reading "changes take effect on next login/reboot", so the `restart:`
field the design sketched is not here.

## `steps` is the name for no shared mechanism

Five rows with nothing in common: `~/Library`'s hidden flag and extended
attribute, the screenshot directory, the Xcode licence, OrbStack's plugin
directory in `~/.config/docker/config.json`, and fontconfig pointing at the
Windows user font directory. Each is one pair of functions in
`providers/steps.py`, the shape `custom_installers` settled on — the declaration
names *which*, the code says *how*, and a test asserts the two sets match in both
directions so neither a row nothing implements nor a function nothing declares
can sit there reading as maintained.

A `check:`/`apply:` argv pair in the YAML was the alternative, and three of the
five would not fit it: a JSON merge, a path discovered by asking Windows, and an
observation that has to *decline* to escalate.

Three of them are worth knowing about individually.

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

So `check` never escalates, which is what lets it run at a prompt, in a
pre-commit hook, and inside a container with no passwordless sudo. A row that
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
configures can be.

## One prompt

`privilege.py` is the only module in the package that contains the string
`sudo`, and a test asserts it over the parsed source so the prose explaining why
a module does not escalate is not itself a violation.

Three rules follow from that. Privilege is **declared on the change**, so the
whole list is known before any of it runs. Authorization happens **once**, with
that list, and every command after it passes `sudo -n` — so a provider cannot
open a second password prompt in the middle of a twenty-minute install. And a
refusal is **not fatal**: with no sudo, or with the password declined, the
privileged rows are reported and everything else still converges. That is what
makes the container harnesses work without a passwordless-sudo carve-out.

A keepalive refreshes the timestamp while the run continues, because `pacman
-Syu` outlives sudo's default five minutes.

**The prompt is at the end of `apply` rather than the front, and that is
temporary.** What decides whether root is needed at all is the observation, and
the observation is not right until the packages are installed: on a fresh
machine zsh does not exist yet, so an up-front look would find the login shell
unrepairable, ask for nothing, and then refuse the one write it turns out to
need. Asking for a password that may not be needed is the other wrong answer. It
moves to the front when the package backends convert and the whole privileged
list is knowable before anything runs.

## Two things worth not rediscovering

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
