# System Configuration

A machine is not converged when its packages are installed. It also has to be in
the docker group, have `docker.socket` enabled, log itself in on TTY1, point
`/etc/zshenv` at the XDG config, and run zsh as its login shell. None of that is
a package, all of it needs root, and until this conversion none of it could be
checked at all.

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

## Every read is unprivileged, every write is not

This is the property the whole subsystem is built around, and it is a constraint
the providers satisfy rather than a happy accident:

| the privileged write | the unprivileged read |
| --- | --- |
| `groupadd` / `usermod -aG` | the group database |
| `systemctl enable` | `systemctl is-enabled` |
| `tee` a file under `/etc` | read it — these are all mode 0644 |
| `chsh` | the passwd entry's shell field |

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
