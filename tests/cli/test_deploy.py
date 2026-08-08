"""The one write deployment makes into `$HOME` that this repo does not own.

Every other path the deploy touches is a symlink the manager can recreate from
the checkout. `~/.gitconfig` is the exception — a real file, deliberately not in
the repo — which is why the rule that it must never be written *through* a link
is worth pinning rather than leaving to the next reader to rediscover.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles import deploy


@pytest.fixture
def identity_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`IDENTITY_FILE` resolves `Path.home()` at import, so redirect the constant."""
    path = tmp_path / '.gitconfig'
    monkeypatch.setattr(deploy, 'IDENTITY_FILE', path)
    return path


def test_absent_identity_file_is_created(identity_file: Path) -> None:
    deploy._ensure_identity_file()
    assert identity_file.read_text() == deploy.IDENTITY_PLACEHOLDER


def test_an_existing_identity_file_is_left_alone(identity_file: Path) -> None:
    """The placeholder carries no [user], so overwriting one would drop an identity."""
    identity_file.write_text('[user]\n\temail = someone@example.com\n')
    deploy._ensure_identity_file()
    assert 'someone@example.com' in identity_file.read_text()


def test_a_dangling_link_is_replaced_rather_than_written_through(identity_file: Path, tmp_path: Path) -> None:
    """The regression: this wrote the placeholder into the checkout.

    A machine predating the identity file had `~/.gitconfig` linked into
    `configs/<platform>/`, and removing that source left the link behind. To
    `exists()` a dangling link reads as absent, so the guard fell through; to
    `write_text()` it reads as its target, so the write created the repo file.
    """
    vanished_source = tmp_path / 'configs' / 'archlinux' / '.gitconfig'
    identity_file.symlink_to(vanished_source)

    deploy._ensure_identity_file()

    assert not vanished_source.exists()
    assert not identity_file.is_symlink()
    assert identity_file.read_text() == deploy.IDENTITY_PLACEHOLDER


def test_a_live_link_is_honoured(identity_file: Path, tmp_path: Path) -> None:
    """Pointing the identity at a private synced file is not this function's business
    to undo — it only needs `git config --global` to miss the repo-owned config."""
    elsewhere = tmp_path / 'private' / 'gitconfig'
    elsewhere.parent.mkdir()
    elsewhere.write_text('[user]\n\temail = someone@example.com\n')
    identity_file.symlink_to(elsewhere)

    deploy._ensure_identity_file()

    assert identity_file.is_symlink()
    assert 'someone@example.com' in elsewhere.read_text()
