"""The bootstrap installs the CLI and hands over; it never drives it.

`install.sh` ended in `exec dotfiles apply` for as long as it existed, so a bare
`./install.sh` on a machine whose `~/.env` already named it went straight into a
half-hour networked run nobody had asked to start — and behind the work firewall
that run hung mid-download with no plan ever having been shown.

Nothing else catches a return to that. The e2e machine tier runs the bootstrap
and an `apply` as one chain, and `apply` is idempotent, so a bootstrap that had
quietly converged the machine first would leave every assertion there green.
Reading the script is the only cheap place the property is visible at all, which
is why this asserts on its text.
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
import tarfile
from fnmatch import fnmatch
from pathlib import Path

import pytest
from shells import REPO

from dotfiles import coordinates
from dotfiles.create_bundle import ARCHIVE_MEMBER

BOOTSTRAP = REPO / 'install.sh'

INVOCATION = re.compile(r'^\s*(?:exec\s+)?dotfiles\b.*$', re.MULTILINE)
"""A line that *runs* the CLI, as against one that prints its name."""


def test_the_bootstrap_never_runs_the_cli_it_installs() -> None:
    running = [line.strip() for line in INVOCATION.findall(BOOTSTRAP.read_text())]
    assert not running, f'install.sh invokes the CLI it installs: {running}'


def test_the_bootstrap_says_what_to_run_next() -> None:
    """The other half of the same property: converging has to be one command
    away, and a tail deleted rather than replaced satisfies the test above on
    its own."""
    text = BOOTSTRAP.read_text()
    assert 'dotfiles plan' in text
    assert 'dotfiles apply' in text


SHELL_CASE = re.compile(r'^\s*([A-Z*|\s]+)\)\s*UV=uv\.exe', re.MULTILINE)
"""The `case` arm that decides the uv filename, as its glob patterns."""

GIT_BASH_UNAMES = ('MINGW64_NT-10.0-26100', 'MSYS_NT-10.0-26100', 'CYGWIN_NT-10.0-26100')
"""What `uname -s` answers under each POSIX emulation layer on Windows."""


@pytest.mark.parametrize('reported', GIT_BASH_UNAMES)
def test_the_bootstrap_and_the_cli_agree_on_what_windows_looks_like(reported: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """One fact written at two sites, so a test holds them together.

    `install.sh` imports nothing — that is the whole reason it is POSIX sh and
    readable before running it — so it cannot ask `coordinates` which unames mean
    Windows and has to carry the list itself. Two sites deriving one fact is how
    four of this repo's pinned faults happened, and the only site that would find
    out here is a Windows box nobody else in the fleet can reach.

    Asserted through both implementations rather than by comparing the two lists
    as text: `case` takes globs and `_os_family` takes prefixes, so equal strings
    were never the property. Whether each answers *Windows* is.
    """
    patterns = SHELL_CASE.search(BOOTSTRAP.read_text())
    assert patterns, 'install.sh no longer decides the uv filename from `uname -s`'
    globs = [glob.strip() for glob in patterns.group(1).split('|')]

    monkeypatch.setattr(coordinates.platform, 'system', lambda: reported)

    assert any(fnmatch(reported, glob) for glob in globs), f'install.sh calls {reported} unix'
    assert coordinates.detect().os_family is coordinates.OSFamily.WINDOWS, f'the CLI calls {reported} linux'


def test_the_bootstrap_stages_the_uv_its_platform_carries() -> None:
    """A Windows bundle stages `bin/uv.exe`, so a hardcoded `bin/uv` fails there.

    It failed loudly rather than silently, which is the better of the two — the
    copy would otherwise have put a Linux ELF on PATH under a name Git Bash
    resolves. Pinned because the literal reads perfectly well and nothing else
    would notice its return.
    """
    text = BOOTSTRAP.read_text()

    assert 'bin/uv"' not in text, 'install.sh hardcodes bin/uv, which no Windows bundle carries'
    assert '$BUNDLE/bin/$UV' in text


# ─────────────────────────────────────────────────────────────────────────────
# Staging: the one thing the bootstrap does that the CLI also does
# ─────────────────────────────────────────────────────────────────────────────
#
# Run rather than read. The two unpackers are duplicated on purpose — the CLI
# that would run `bundle stage` is what the bundle exists to install — so the
# only thing keeping them in agreement is that both are exercised. A text
# assertion here would pass on a script that unpacks to the wrong directory.

FAKE_UV = """#!/bin/sh
printf '%s\\n' "$*" >> "$UV_ARGV"
exit 0
"""


def bootstrap_bundle(at: Path, name: str) -> Path:
    """A tarball shaped the way `create_bundle` shapes one: one member holding the
    manifest, the uv the bootstrap copies, and the wheelhouse it installs the CLI
    from.

    The member name comes from the producer rather than being spelled again here.
    `install.sh` moves that name by hand, so a fixture carrying its own copy keeps
    building the old shape after the producer changes — leaving these green while
    every real bundle fails to stage, and only the container tier says so.
    """
    staging = at / f'{name}-contents' / ARCHIVE_MEMBER
    (staging / 'bin').mkdir(parents=True)
    (staging / 'wheels').mkdir()
    (staging / 'manifest.txt').write_text('binary|fd|10.2.0|fd\n')
    (staging / 'bin' / 'uv').write_text('#!/bin/sh\nexit 0\n')
    (staging / 'wheels' / 'dotfiles.whl').write_text('a wheel')

    tarball = at / f'{name}.tar.gz'
    with tarfile.open(tarball, 'w:gz') as packed:
        packed.add(staging, arcname=ARCHIVE_MEMBER)
    return tarball


def run_bootstrap(tmp_path: Path, *archives: str) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    """`install.sh --offline` with uv shadowed, so nothing is really installed."""
    home = tmp_path / 'home'
    staging = tmp_path / 'staged'
    fake_bin = tmp_path / 'bin'
    (home / '.local' / 'bin').mkdir(parents=True)
    fake_bin.mkdir()
    argv_log = tmp_path / 'uv-argv'

    shadow = fake_bin / 'uv'
    shadow.write_text(FAKE_UV)
    shadow.chmod(shadow.stat().st_mode | stat.S_IEXEC)

    # What a real `uv tool install` would have left behind. The script's closing
    # check is that the CLI it installed answers on PATH, and a fake uv that
    # installs nothing fails it — for a reason that has nothing to do with
    # staging, which is what these tests are about.
    installed = home / '.local' / 'bin' / 'dotfiles'
    installed.write_text('#!/bin/sh\nexit 0\n')
    installed.chmod(installed.stat().st_mode | stat.S_IEXEC)

    for name in archives:
        bootstrap_bundle(tmp_path, name)

    environment = {
        **os.environ,
        'HOME': str(home),
        'DOTFILES_BUNDLE': str(staging),
        'UV_ARGV': str(argv_log),
        'PATH': f'{fake_bin}{os.pathsep}/usr/bin{os.pathsep}/bin',
    }
    ran = subprocess.run(
        ['sh', str(BOOTSTRAP), '--machine', 'wsl-work-workstation', '--offline'],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    return ran, staging, argv_log


def test_the_bootstrap_stages_into_a_directory_named_after_the_archive(tmp_path: Path) -> None:
    """The same layout `offline_bundle.stage` writes, reached by the one caller
    that cannot call it."""
    ran, staging, _ = run_bootstrap(tmp_path, 'dotfiles-offline-v20260810T010000Z-box-linux-x86_64')

    assert ran.returncode == 0, ran.stderr
    assert (staging / 'dotfiles-offline-v20260810T010000Z-box-linux-x86_64' / 'manifest.txt').is_file()
    assert not (staging / ARCHIVE_MEMBER).exists(), "the archive's member name must not decide the directory"


def test_the_bootstrap_installs_the_cli_from_the_bundle_it_staged(tmp_path: Path) -> None:
    """The property the duplication exists for: the wheels it hands uv are the
    ones inside the directory it just wrote, not a path assembled separately."""
    ran, staging, argv_log = run_bootstrap(tmp_path, 'dotfiles-offline-v20260810T010000Z-box-linux-x86_64')
    staged = staging / 'dotfiles-offline-v20260810T010000Z-box-linux-x86_64'

    assert ran.returncode == 0, ran.stderr
    assert f'--find-links {staged / "wheels"}' in argv_log.read_text()


def test_the_bootstrap_takes_the_newest_archive_across_the_directories_it_searches(tmp_path: Path) -> None:
    """Ranked by the stamp rather than by which directory was looked at first,
    which is what the CLI's own `newest` does now that a name carries seconds."""
    ran, staging, _ = run_bootstrap(
        tmp_path,
        'dotfiles-offline-v20260101T010000Z-box-linux-x86_64',
        'dotfiles-offline-v20260909T010000Z-box-linux-x86_64',
    )

    assert ran.returncode == 0, ran.stderr
    assert (staging / 'dotfiles-offline-v20260909T010000Z-box-linux-x86_64').is_dir()
    assert not (staging / 'dotfiles-offline-v20260101T010000Z-box-linux-x86_64').exists()


def test_the_bootstrap_reads_a_bundle_somebody_else_staged(tmp_path: Path) -> None:
    """A machine part way through a rebuild has one unpacked already, and the
    archive it came from may be long gone."""
    staging = tmp_path / 'staged' / 'dotfiles-offline-v20260810T010000Z-box-linux-x86_64'
    (staging / 'bin').mkdir(parents=True)
    (staging / 'wheels').mkdir()
    (staging / 'manifest.txt').write_text('binary|fd|10.2.0|fd\n')

    ran, _, argv_log = run_bootstrap(tmp_path)

    assert ran.returncode == 0, ran.stderr
    assert f'--find-links {staging / "wheels"}' in argv_log.read_text()


def test_the_bootstrap_refuses_when_nothing_is_staged_and_nothing_can_be(tmp_path: Path) -> None:
    """Paired with the exit code and a positive fact, because a refusal and a
    crash both leave the staging directory empty."""
    ran, staging, argv_log = run_bootstrap(tmp_path)

    assert ran.returncode == 1
    assert 'no bundle' in ran.stderr
    assert not argv_log.exists(), 'uv was never reached'


def test_a_second_top_level_member_does_not_kill_a_correct_stage(tmp_path: Path) -> None:
    """An AppleDouble sidecar from a tarball repacked on macOS is the real case.
    Under `set -eu` a leftover in the scratch directory used to abort the run
    after the bundle had already been staged, with `rmdir: failed to remove` as
    the whole diagnosis."""
    name = 'dotfiles-offline-v20260810T010000Z-box-linux-x86_64'
    bootstrap_bundle(tmp_path, name)
    stray = tmp_path / '._sidecar'
    stray.write_text('resource fork')
    with tarfile.open(tmp_path / f'{name}.tar.gz', 'w:gz') as packed:
        packed.add(tmp_path / f'{name}-contents' / ARCHIVE_MEMBER, arcname=ARCHIVE_MEMBER)
        packed.add(stray, arcname='._sidecar')

    ran, staging, _ = run_bootstrap(tmp_path)

    assert ran.returncode == 0, ran.stderr
    assert (staging / name / 'manifest.txt').is_file()


def test_an_archive_carrying_no_manifest_is_refused_by_name_not_by_member(tmp_path: Path) -> None:
    """The member is found by its manifest, the way `offline_bundle.stage` finds
    it. Naming it made this the only reader in the fleet that cared what the
    producer called the directory."""
    contents = tmp_path / 'contents' / 'something-else'
    contents.mkdir(parents=True)
    (contents / 'notes.txt').write_text('not a bundle')
    with tarfile.open(tmp_path / 'dotfiles-offline-v20260810T010000Z-box-linux-x86_64.tar.gz', 'w:gz') as packed:
        packed.add(contents, arcname='something-else')

    ran, _, argv_log = run_bootstrap(tmp_path)

    assert ran.returncode == 1
    assert 'no manifest.txt' in ran.stderr
    assert not argv_log.exists(), 'uv was never reached'


def test_a_bundle_built_for_another_machine_is_refused_before_the_move(tmp_path: Path) -> None:
    """After the bootstrap something is always staged, so `reconcile._stage_bundle`
    never validates again on this machine. This is the path where the guard has to
    be, and `bundle download --machine X` writes a peer's archive into the same
    cache the bootstrap searches."""
    name = 'dotfiles-offline-v20260810T010000Z-box-linux-x86_64'
    bootstrap_bundle(tmp_path, name)
    described = tmp_path / f'{name}-contents' / ARCHIVE_MEMBER / 'bundle.json'
    described.write_text('{"machine": "macos-personal-workstation", "completeness": "full"}\n')
    with tarfile.open(tmp_path / f'{name}.tar.gz', 'w:gz') as packed:
        packed.add(tmp_path / f'{name}-contents' / ARCHIVE_MEMBER, arcname=ARCHIVE_MEMBER)

    ran, staging, _ = run_bootstrap(tmp_path)

    assert ran.returncode == 1
    assert 'was built for macos-personal-workstation' in ran.stderr
    assert not (staging / name).exists(), 'a refused bundle leaves nothing behind'


def test_a_bundle_naming_no_machine_still_stages(tmp_path: Path) -> None:
    """Silence is not evidence of a mismatch, and refusing on it would make every
    archive built before `bundle.json` unusable — on the machine that most needs
    to unpack one."""
    name = 'dotfiles-offline-v20260810T010000Z-box-linux-x86_64'
    ran, staging, _ = run_bootstrap(tmp_path, name)

    assert ran.returncode == 0, ran.stderr
    assert (staging / name / 'manifest.txt').is_file()


def test_a_truncated_archive_leaves_the_copy_already_staged_under_that_name(tmp_path: Path) -> None:
    """The ordering, and the reason it is an ordering rather than a preference.

    Removing the destination before the extract means an archive that fails part
    way through destroys the bundle already staged under its name, on the one
    machine that cannot download another. Nothing distinguished the two orders —
    the suite ran thirteen cases and handed the script no archive that fails.

    `offline_bundle.stage` unpacks into a scratch directory and moves for the same
    reason, which is what `code-quality.md` § "A duplicated implementation copies
    the original's failure order, not only its result" is about.
    """
    name = 'dotfiles-offline-v20260810T010000Z-box-linux-x86_64'
    bootstrap_bundle(tmp_path, name)
    truncated = (tmp_path / f'{name}.tar.gz').read_bytes()[:64]
    (tmp_path / f'{name}.tar.gz').write_bytes(truncated)

    already = tmp_path / 'staged' / name
    already.mkdir(parents=True)
    (already / 'manifest.txt').write_text('binary|fd|10.2.0|fd\n')

    ran, staging, _ = run_bootstrap(tmp_path)

    # Non-zero rather than 1: the extract dies under `set -e` and tar's own status
    # is what travels, where the script's checks exit 1 through `die`.
    assert ran.returncode != 0
    assert (staging / name / 'manifest.txt').read_text() == 'binary|fd|10.2.0|fd\n'
