"""What a binary says its version is, and when to stop trusting it.

`reported_version` is mechanism-agnostic — it knows how to run a probe and
nothing about who installed what — except for the one seam `gotool.gobin()`
gives it: a binary living there is one `go install` produced, and its own banner
is never the thing `go install` puts a real version behind. Everywhere else this
is unchanged, which is the property most worth pinning down: a probe's raw
output, or nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles import evidence
from dotfiles.effects import Completed
from dotfiles.providers import gotool


@pytest.fixture
def gobin(tmp_path, monkeypatch) -> Path:
    home = tmp_path / 'home'
    directory = home / 'go' / 'bin'
    directory.mkdir(parents=True)
    monkeypatch.setenv('HOME', str(home))
    return directory


def probed(monkeypatch, *answers: tuple[int, str]) -> list[list[str]]:
    """Stub what each `VERSION_PROBES` attempt answers, in order."""
    calls: list[list[str]] = []
    remaining = list(answers)

    def fake_run(command, **_kwargs) -> Completed:
        argv = [str(part) for part in command]
        calls.append(argv)
        returncode, stdout = remaining.pop(0) if remaining else (1, '')
        return Completed(tuple(argv), returncode, stdout, stdout=stdout)

    monkeypatch.setattr(evidence, 'run', fake_run)
    return calls


def module_version(monkeypatch, answer: str | None) -> list[Path]:
    calls: list[Path] = []

    def fake(binary: Path) -> str | None:
        calls.append(binary)
        return answer

    monkeypatch.setattr(evidence.gotool, 'module_version', fake)
    return calls


def test_a_non_go_binary_keeps_whatever_the_first_probe_printed(monkeypatch) -> None:
    """Unchanged from before this existed: a probe's raw output, read or not —
    `rg --version` prints a real one, and this is not that test, but the tool
    living outside `gotool.gobin()` is what must not change."""
    monkeypatch.setattr(evidence.shutil, 'which', lambda name: '/usr/bin/rg' if name == 'rg' else None)
    probed(monkeypatch, (0, 'ripgrep 14.1.1 (rev...)'))
    asked = module_version(monkeypatch, 'unused')

    assert evidence.reported_version('rg') == 'ripgrep 14.1.1 (rev...)'
    assert asked == []


def test_a_non_go_binary_with_unparseable_output_is_returned_verbatim(monkeypatch) -> None:
    """The garbage-text case this repo already accepts for everything that is not
    a `go install`-ed binary: unchanged, and never routed at `go`."""
    monkeypatch.setattr(evidence.shutil, 'which', lambda name: '/usr/bin/webviewrs' if name == 'webviewrs' else None)
    probed(monkeypatch, (0, 'usage: webviewrs <url>'))
    asked = module_version(monkeypatch, 'unused')

    assert evidence.reported_version('webviewrs') == 'usage: webviewrs <url>'
    assert asked == []


def test_a_go_installed_binary_with_a_parseable_banner_is_trusted_without_asking_go(monkeypatch, gobin) -> None:
    """`task --version` already prints `3.52.0` — the module version `go version
    -m` would say is no more correct, and asking anyway would be a wasted
    subprocess on every current, well-behaved Go tool."""
    binary = gobin / 'task'
    monkeypatch.setattr(evidence.shutil, 'which', lambda name: str(binary) if name == 'task' else None)
    probed(monkeypatch, (0, '3.52.0'))
    asked = module_version(monkeypatch, 'unused')

    assert evidence.reported_version('task') == '3.52.0'
    assert asked == []


def test_a_go_installed_binary_with_no_parseable_banner_falls_back_to_the_module_version(monkeypatch, gobin) -> None:
    """`gdu --version` prints `Version:\tdevelopment` for every copy `go install`
    has ever produced, because the flag a release build stamps a real one with is
    exactly what `go install` never passes."""
    binary = gobin / 'gdu'
    monkeypatch.setattr(evidence.shutil, 'which', lambda name: str(binary) if name == 'gdu' else None)
    probed(monkeypatch, (0, 'Version:\t development\n'), (1, ''))
    asked = module_version(monkeypatch, 'v5.36.1')

    assert evidence.reported_version('gdu') == 'v5.36.1'
    assert asked == [binary]


def test_falling_back_never_fabricates_a_version(monkeypatch, gobin) -> None:
    """`go` missing, or a binary it does not recognise, is "cannot say" — not a
    reason to hand back the unparseable banner this whole path exists to avoid."""
    binary = gobin / 'gdu'
    monkeypatch.setattr(evidence.shutil, 'which', lambda name: str(binary) if name == 'gdu' else None)
    probed(monkeypatch, (0, 'Version:\t development\n'), (1, ''))
    module_version(monkeypatch, None)

    assert evidence.reported_version('gdu') is None


def test_a_missing_binary_is_none_before_anything_is_asked(monkeypatch) -> None:
    monkeypatch.setattr(evidence.shutil, 'which', lambda name: None)
    calls = probed(monkeypatch)
    asked = module_version(monkeypatch, 'unused')

    assert evidence.reported_version('gdu') is None
    assert calls == []
    assert asked == []


def test_gobin_itself_is_measured_by_gotool_directly(gobin) -> None:
    """`gotool.gobin()` is the fact this whole seam is keyed on — proven live
    rather than assumed, since a mismatch here would silently turn every Go tool
    back into the general, unrouted case."""
    assert gotool.gobin() == gobin
