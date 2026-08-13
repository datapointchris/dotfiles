"""A TLS-intercepting proxy, reported as itself rather than as an outage.

The work box sits behind one. On 2026-08-13 an `apply --offline` there reported
`the claude-code install script exited 60` and nothing else — 60 being curl's code
for a certificate it will not verify, which is one CA import away from fixed and
reads as a blocked network. Every layer on that path narrowed its answer to a bool
or a bare number, so the cause existed nowhere: not on screen, not in the run
record, not in the debug stream.

These pin the four places the reason now survives.
"""

from __future__ import annotations

from pathlib import Path

import httpx2
import pytest

from dotfiles import diagnose
from dotfiles import effects
from dotfiles import github_release
from dotfiles import network
from dotfiles.providers import script

INTERCEPTED = 'certificate verify failed: unable to get local issuer certificate'


class TestTheReasonLeavesTheTransport:
    def test_a_refused_certificate_is_carried_out_rather_than_becoming_False(self, tmp_path, monkeypatch) -> None:
        """One `except` clause with no `as` binding is where every download's reason
        died — a 404, a DNS failure, a TLS rejection, ENOSPC and EACCES were one value."""

        def refuse(url, **kwargs):
            raise httpx2.ConnectError(INTERCEPTED)

        monkeypatch.setattr(github_release, 'request', refuse)

        answered = github_release.download_asset('https://example.test/x', tmp_path / 'x')

        assert not answered
        assert INTERCEPTED in answered.reason

    def test_it_is_still_usable_as_a_boolean(self, tmp_path, monkeypatch) -> None:
        """Eleven providers write `if not effects.fetch(...)` and eight test doubles
        return a bare bool. A plain `str` return would have inverted every one of them
        silently, because `False` and `''` are both falsy."""
        monkeypatch.setattr(github_release, 'request', lambda url, **kwargs: b'bytes')

        assert effects.fetch('https://example.test/x', tmp_path / 'x')

    def test_a_reason_that_says_nothing_still_names_its_type(self, tmp_path, monkeypatch) -> None:
        """`httpx2.ConnectError('')` is possible, and the type alone already separates
        a refused connection from a 404."""

        def refuse(url, **kwargs):
            raise httpx2.ConnectError('')

        monkeypatch.setattr(github_release, 'request', refuse)

        assert github_release.download_asset('https://example.test/x', tmp_path / 'x').reason == 'ConnectError'


class TestTheDiagnosisNamesTheFix:
    def test_an_intercepted_certificate_is_told_apart_from_an_outage(self) -> None:
        explained = diagnose.explain('packages/ghrelease/fd', f'could not download fd: ConnectError: {INTERCEPTED}')

        assert 'not signed by a CA this machine trusts' in explained
        assert 'proxy' in explained

    def test_the_fix_names_a_trust_store_that_exists_on_this_machine(self) -> None:
        """A reader told to drop a CA where their distribution does not look will
        conclude the certificate was not the problem."""
        explained = diagnose.explain('packages/ghrelease/fd', f'ConnectError: {INTERCEPTED}')
        named = [store for store in diagnose.TRUST_STORES if store in explained]

        assert all(Path(store).is_dir() for store in named)

    def test_an_ordinary_failure_is_returned_unchanged(self) -> None:
        assert diagnose.explain('packages/ghrelease/fd', 'could not download fd') == 'could not download fd'

    def test_curl_60_has_a_cause_and_an_unknown_code_does_not(self) -> None:
        """An invented cause is what makes a diagnosis untrustworthy."""
        assert 'CA this machine trusts' in diagnose.curl_cause(60)
        assert diagnose.curl_cause(211) == ''


class TestTheProbeSaysWhichKindOfNo:
    """A blocked host wants an offline bundle. An untrusted certificate wants a CA.
    Both were `NO` in the same column, so an intercepted machine read as a blackholed
    one — and the operator was sent to spend hours building a bundle."""

    def test_a_certificate_rejection_is_not_reported_as_a_block(self, monkeypatch) -> None:
        probe = network.Probe('github_release', 'fd', 'https://github.com/x/fd/releases/latest')
        monkeypatch.setattr(
            effects,
            'run',
            lambda *args, **kwargs: effects.Completed(command=('curl',), returncode=60, transcript=f'curl: (60) {INTERCEPTED}'),
        )

        measured = network.measure(probe)

        assert not measured.reachable
        assert 'CA this machine trusts' in measured.refusal

    def test_a_refused_connection_carries_curls_own_meaning(self, monkeypatch) -> None:
        probe = network.Probe('github_release', 'fd', 'https://github.com/x/fd/releases/latest')
        monkeypatch.setattr(effects, 'run', lambda *args, **kwargs: effects.Completed(command=('curl',), returncode=7, transcript=''))

        assert 'refused or filtered' in network.measure(probe).refusal

    def test_a_reachable_host_carries_no_reason(self, monkeypatch) -> None:
        """A reason invented for every row is a reason nobody reads."""
        probe = network.Probe('github_release', 'fd', 'https://github.com/x/fd/releases/latest')
        monkeypatch.setattr(effects, 'run', lambda *args, **kwargs: effects.Completed(command=('curl',), returncode=0, transcript=''))

        assert network.measure(probe).refusal == ''


class TestAFailedScriptSaysWhatItSaid:
    def test_the_transcript_rides_on_the_failure_rather_than_the_exit_code(self) -> None:
        """`the claude-code install script exited 60` was the whole message, with the
        cause a screen above it and already scrolled away on a multi-minute apply."""
        completed = effects.Completed(command=('bash',), returncode=60, transcript=f'downloading\ncurl: (60) {INTERCEPTED}\n')

        said = script.failure('claude-code', completed)

        assert 'exited 60' in said
        assert INTERCEPTED in said

    def test_a_script_that_said_nothing_still_reports_its_status(self) -> None:
        completed = effects.Completed(command=('bash',), returncode=1, transcript='   \n\n')

        assert script.failure('theme', completed) == 'the theme install script exited 1'

    def test_the_tail_is_kept_rather_than_the_head(self) -> None:
        """A vendor installer prints its banner, progress and environment checks before
        it fails, so the head of a transcript is reliably the irrelevant part."""
        completed = effects.Completed(command=('bash',), returncode=1, transcript='banner\n' * 40 + 'the real cause\n')

        assert 'the real cause' in script.failure('uv', completed)
        assert script.failure('uv', completed).count('banner') <= script.TRANSCRIPT_LINES


@pytest.mark.parametrize('code', [6, 7, 28, 35, 60])
def test_every_named_curl_code_reads_as_a_sentence(code: int) -> None:
    assert diagnose.curl_cause(code).startswith('the ')
