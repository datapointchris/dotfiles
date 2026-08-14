"""Getting a package manager onto the machine, which is not a package install.

Three procedures with nothing in common with `pacman -S` and not much in common
with each other. Homebrew arrives as a shell script from its own project; yay is
an AUR package, so it has to be built before there is anything that builds AUR
packages; flatpak needs a remote before `flatpak install` can name anything.

Each is a **precondition of a provider**, in the shape `cargo.binstall` took: it
runs only when something needing it is planned, it is idempotent, and it answers
with a `Result` its provider turns into a refusal rather than raising.

**A bootstrap cannot be gated by a payload switch, because the payload is what
asks for it.** Gate it on a manifest tier and a manifest declaring no tier drops
the bootstrap while still running the payload — `brew install` without the step
that provides `brew`. That stays unreachable only for as long as every manifest
happens to declare a tier.

None of the three is a declared package, and that is the point rather than an
omission: a manager declared as one of its own packages would need itself to
install itself.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path

from dotfiles import effects
from dotfiles.effects import Output
from dotfiles.privilege import Privilege
from dotfiles.providers import Kind
from dotfiles.providers import Result
from dotfiles.providers import syspkg
from dotfiles.providers import toolchain

BREW_INSTALLER = 'https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh'

BREW_PREFIXES = (Path('/opt/homebrew/bin'), Path('/usr/local/bin'))
"""Where the installer puts `brew`: Apple silicon first, then Intel.

Probed rather than derived from the architecture, because the second is also
where an Intel-era prefix survives a machine migration.
"""

YAY_REPO = 'https://aur.archlinux.org/yay.git'

FLATHUB = 'https://flathub.org/repo/flathub.flatpakrepo'

SYSTEM_BUS = Path('/run/dbus/system_bus_socket')
"""What flatpak talks to, and what a container has none of.

The bash skipped flatpak when `DOTFILES_DOCKER_TEST` was set, which is a test
harness telling production code it is being tested. The reason the container
cannot run flatpak is that it has no bus — so this asks about the bus, and is
equally right on a machine that is not a container and has no bus either.
"""


def homebrew() -> Result:
    """Homebrew itself, from its own installer.

    Not run through `Privilege`. The installer creates `/opt/homebrew` as root and
    then refuses to continue if it *is* root, so it calls sudo for the parts that
    need it and prompts on its own; handing it an already-escalated shell is the
    one way to make it fail.

    Downloaded to a file and run from there rather than piped into bash — the
    same bytes, but a failure names a script that still exists to be read.
    `NONINTERACTIVE` suppresses the "press RETURN" it would otherwise block a
    scripted install on; it does not suppress the password prompt, which is a
    person's to answer.
    """
    if shutil.which('brew'):
        return Result(True, '', kind=Kind.UNCHANGED)

    with tempfile.TemporaryDirectory(prefix='dotfiles-homebrew-') as scratch:
        script = Path(scratch) / 'install.sh'
        arrived = effects.fetch(BREW_INSTALLER, script)
        if not arrived:
            # The first thing that runs on a fresh Mac, so the failure with the least
            # context around it — and the one most likely to be read as "the network
            # is down" when it is a proxy certificate.
            return Result(
                False, f'could not download the Homebrew installer from {BREW_INSTALLER}: {arrived.reason}', kind=Kind.DOWNLOAD_FAILED
            )
        installed = effects.run(['bash', str(script)], env={'NONINTERACTIVE': '1'})

    if not installed.ok:
        return Result(False, f'the Homebrew installer exited {installed.returncode}', kind=Kind.COMMAND_FAILED)

    placed = next((prefix for prefix in BREW_PREFIXES if (prefix / 'brew').is_file()), None)
    if placed is None:
        looked = ' or '.join(str(prefix) for prefix in BREW_PREFIXES)
        return Result(False, f'the Homebrew installer reported success but left no brew in {looked}', kind=Kind.VERIFY_FAILED)
    toolchain.put_on_path(placed)
    return Result(True, f'Homebrew installed at {placed}', kind=Kind.APPLIED)


def taps(wanted: Sequence[str]) -> Result:
    """Register the third-party formula sources before anything resolves against them.

    A formula in a tap — JankyBorders, AeroSpace — is unresolvable until its tap
    is registered, and an unresolvable formula aborts a batched `brew install`
    before it touches anything. So this runs before the batch rather than
    alongside it, and a tap that fails is fatal to the batch rather than a
    warning: installing anyway means every package in the group fails for a
    reason naming the wrong formula.

    `brew tap` on an already-registered tap is a no-op, so this is idempotent
    without asking what is registered.
    """
    for tap in wanted:
        added = effects.run(['brew', 'tap', tap], output=Output.QUIET)
        if not added.ok:
            return Result(False, f'brew tap {tap} exited {added.returncode}', kind=Kind.COMMAND_FAILED)
    return Result(True, '', kind=Kind.APPLIED)


def aur() -> Result:
    """What `yay -S` needs before it can install anything: a GnuPG home, and yay.

    Two halves because they gate the same batch, not because they are one thing.
    Building yay does not need GnuPG; *installing an AUR package* does, because
    makepkg verifies upstream source signatures and a missing `GNUPGHOME` fails
    the verification rather than skipping it.
    """
    home = _gnupg_home()
    try:
        home.mkdir(parents=True, exist_ok=True)
        home.chmod(0o700)
    except OSError as refused:
        return Result(False, f'could not prepare {home} for AUR signature verification: {refused}', kind=Kind.WRITE_FAILED)

    return _yay()


def _gnupg_home() -> Path:
    """Where `.zshrc` puts GnuPG, which is where makepkg has to be told to look.

    Duplicated from the shell rather than shared with it because the shell is not
    running: an install invoked from a plain `bash` inherits no `GNUPGHOME`, and
    makepkg then writes a second keyring under `~/.gnupg` that the next
    interactive run cannot see.
    """
    data = os.environ.get('XDG_DATA_HOME') or str(Path.home() / '.local' / 'share')
    return Path(data) / 'gnupg'


def _yay() -> Result:
    """Build yay from the AUR, which is the only way to get an AUR helper.

    `makepkg` refuses to run as root and escalates for the install step itself, so
    this is deliberately not routed through `Privilege` — the same reasoning as
    the Homebrew installer above, for the same kind of tool.

    `base-devel` is checked by looking for makepkg rather than asked of pacman:
    the answer is the same, and a machine that cannot build cannot bootstrap an
    AUR helper whatever the package database says about why.
    """
    if shutil.which('yay'):
        return Result(True, '', kind=Kind.UNCHANGED)
    if shutil.which('makepkg') is None:
        return Result(False, 'building yay needs base-devel, which this machine has not installed', kind=Kind.PREREQUISITE_MISSING)

    environment = {'GNUPGHOME': str(_gnupg_home())}
    with tempfile.TemporaryDirectory(prefix='dotfiles-yay-') as scratch:
        checkout = Path(scratch) / 'yay'
        cloned = effects.run(['git', 'clone', '--depth', '1', YAY_REPO, str(checkout)])
        if not cloned.ok:
            return Result(False, f'could not clone {YAY_REPO}: exited {cloned.returncode}', kind=Kind.DOWNLOAD_FAILED)

        built = effects.run(['makepkg', '-si', '--noconfirm'], cwd=checkout, env=environment)

    if not built.ok:
        return Result(False, f'makepkg -si exited {built.returncode} building yay', kind=Kind.COMMAND_FAILED)
    return Result(True, 'yay built from the AUR', kind=Kind.APPLIED)


def flathub(installer: str, privilege: Privilege) -> Result:
    """flatpak, and the remote every declared app is named against.

    The remote is the half that matters. `flatpak install <id>` with no remote
    fails naming the app, which reads as a missing app rather than a machine that
    was never pointed at Flathub.

    flatpak itself is installed through the machine's own package manager rather
    than declared under `system_packages`, for the reason at the top of this
    module — and because a machine subscribing to no `flatpak_apps` should not
    carry the runtime for them.
    """
    if shutil.which('flatpak') is None:
        installed = syspkg.install(installer, ['flatpak'], privilege)
        if not installed.ok:
            return Result(
                False, f'flatpak is not installed and {installer} could not install it: {installed.detail}', kind=Kind.PREREQUISITE_MISSING
            )

    if not SYSTEM_BUS.exists():
        return Result(False, f'flatpak needs the D-Bus system bus at {SYSTEM_BUS}, and this machine has none', kind=Kind.UNSUPPORTED_HERE)

    added = effects.run(['flatpak', 'remote-add', '--if-not-exists', 'flathub', FLATHUB], output=Output.QUIET)
    if not added.ok:
        return Result(False, f'could not add the flathub remote: flatpak remote-add exited {added.returncode}', kind=Kind.COMMAND_FAILED)
    return Result(True, '', kind=Kind.APPLIED)
