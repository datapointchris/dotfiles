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
from dotfiles.session import Session


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


@pytest.mark.parametrize(
    'banner',
    ['3.52.0', 'Version:\t development\n', 'docker-language-server version 0.0.0'],
    ids=['a-real-version', 'an-unparseable-placeholder', 'a-placeholder-that-parses'],
)
def test_a_go_installed_binary_answers_from_the_toolchain_whatever_its_banner_says(monkeypatch, gobin, banner) -> None:
    """The banner is not read, and which of the three it is does not matter.

    Letting the banner win wherever it parses, and asking `go version -m` only
    where it does not, interrogates a version string about whether it is a real
    version — the move `standards/release.md` § "Never detect a dev build from a
    version string" forbids, for the reason it gives there: a valid-looking string
    carries no evidence about what produced it.

    The three ids are the whole argument. `go install` never passes the
    `-ldflags -X` a release build stamps a version with, so `gdu` prints
    `development` and `docker-language-server` prints `0.0.0`. Only the second
    failed to parse, so only the second reached the toolchain — and
    docker-language-server measured as permanently behind and reinstalled on
    three consecutive applies before anyone noticed. Telling the first from the
    third means reading the string, which is the thing that cannot be done.

    A well-behaved tool loses nothing. `task`'s banner and its module version are
    the same fact, and the one from the toolchain is the one that cannot be a
    placeholder — as long as the toolchain resolved a tag, which
    `test_a_pseudo_versioned_module_is_not_an_answer` is the other half of.
    """
    binary = gobin / 'tool'
    monkeypatch.setattr(evidence.shutil, 'which', lambda name: str(binary) if name == 'tool' else None)
    probes = probed(monkeypatch, (0, banner))
    asked = module_version(monkeypatch, 'v5.36.1')

    assert evidence.reported_version('tool') == 'v5.36.1'
    assert asked == [binary]
    assert probes == [], 'the banner was run, and not running it is the point'


def test_a_pseudo_versioned_module_is_not_an_answer(monkeypatch, gobin) -> None:
    """`go install` resolved a commit, so the binary's own banner is what is left.

    Where no tag matches the module path, `go version -m` answers a pseudo-version
    like `v0.0.0-20260216134545-b8098dc1b9de`, which `versions.parse` reads as
    `(0, 0, 0)` — below every release anyone publishes — while the binary's own
    banner is correct. Preferring the module unconditionally makes such a tool
    permanently STALE, which is the placeholder failure moved onto a different tool
    rather than fixed.

    Neither record is authoritative and each fails its own way. The asymmetry that
    makes this decidable is that only the module's failure announces itself: a
    pseudo-version is a format the toolchain defines, where telling a placeholder
    `0.0.0` from a real one means guessing.
    """
    binary = gobin / 'cheat'
    monkeypatch.setattr(evidence.shutil, 'which', lambda name: str(binary) if name == 'cheat' else None)
    probed(monkeypatch, (0, '5.1.0'))
    asked = module_version(monkeypatch, 'v0.0.0-20260216134545-b8098dc1b9de')

    assert evidence.reported_version('cheat') == '5.1.0'
    assert asked == [binary], 'the toolchain is still asked first; its answer is what is rejected'


def test_a_go_binary_go_cannot_name_is_unknown_rather_than_its_banner(monkeypatch, gobin) -> None:
    """`go` missing, or a binary it does not recognise, is "cannot say" — not a
    reason to hand back the placeholder this whole path exists to avoid."""
    binary = gobin / 'gdu'
    monkeypatch.setattr(evidence.shutil, 'which', lambda name: str(binary) if name == 'gdu' else None)
    probed(monkeypatch, (0, 'Version:\t development\n'))
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


def test_the_preconditions_are_measured_once_however_many_resources_ask(monkeypatch, tmp_path) -> None:
    """`gh auth token` is 30ms and more than one resource wants the answer. Asked
    per resource it was a subprocess each deciding one fact about the machine, and
    a walk that reached a different verdict half way through would report two
    states of one login inside a single report."""
    asked: list[list[str]] = []

    def record(command, **_kwargs) -> Completed:
        argv = tuple(str(part) for part in command)
        asked.append(list(argv))
        return Completed(argv, 1, '')

    monkeypatch.delenv('GITHUB_TOKEN', raising=False)
    monkeypatch.setattr(evidence, 'run', record)
    live = Session(machine_name='box', repo=tmp_path, home=tmp_path)

    first = live.preconditions

    assert live.preconditions is first
    assert len(asked) == 1
