"""How the package finds the checkout it manages.

The failure this guards is silent rather than loud, which is why it needs a test:
a non-editable install puts the package under `site-packages`, where walking up
three parents reaches a real directory that simply is not a checkout. Nothing
raises — every path below just points somewhere empty, and the first symptom is
an unrelated "no such file" from whichever command ran first.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from dotfiles import paths


def make_checkout(root: Path) -> Path:
    (root / 'install').mkdir(parents=True, exist_ok=True)
    (root / paths.REPO_MARKER).write_text('system_packages: []\n')
    return root


def test_the_real_repo_is_recognised() -> None:
    """Guards every other test here: if the marker were wrong, all of them pass
    while the recogniser recognises nothing."""
    assert paths._looks_like_repo(paths.REPO_ROOT)


def test_a_directory_without_the_marker_is_not_a_checkout(tmp_path: Path) -> None:
    assert not paths._looks_like_repo(tmp_path)


def test_the_environment_wins_even_over_a_tree_that_is_incomplete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """DOTFILES_DIR is the injection point tests use, and a fixture is often only
    the few files one check needs — so validating it would break the seam."""
    monkeypatch.setenv('DOTFILES_DIR', str(tmp_path))
    importlib.reload(paths)
    try:
        assert tmp_path.resolve() == paths.REPO_ROOT
    finally:
        monkeypatch.undo()
        importlib.reload(paths)


def test_an_editable_install_resolves_by_walking_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """src/dotfiles/paths.py in a checkout: three parents up is the repo."""
    checkout = make_checkout(tmp_path / 'checkout')
    module = checkout / 'src' / 'dotfiles' / 'paths.py'
    module.parent.mkdir(parents=True)
    module.touch()

    monkeypatch.delenv('DOTFILES_DIR', raising=False)
    monkeypatch.setattr(paths, '__file__', str(module))

    assert paths._repo_root() == checkout.resolve()


def test_a_non_editable_install_falls_through_to_the_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The bug: walking up from site-packages reaches .../lib/python3.13, which
    exists and is not a checkout, so the old code returned it and every path
    below was wrong without anything saying so."""
    installed = tmp_path / 'tools' / 'dotfiles' / 'lib' / 'python3.13' / 'site-packages' / 'dotfiles'
    installed.mkdir(parents=True)
    module = installed / 'paths.py'
    module.touch()

    home = make_checkout(tmp_path / 'home' / 'dotfiles')

    monkeypatch.delenv('DOTFILES_DIR', raising=False)
    monkeypatch.setattr(paths, '__file__', str(module))
    monkeypatch.setattr(Path, 'home', classmethod(lambda _cls: home.parent))

    walked = Path(module).resolve().parents[2]
    assert walked.is_dir(), 'the wrong answer has to be a real directory, or this proves nothing'
    assert paths._repo_root() == home.resolve()
