"""A TLS-intercepting proxy, reported as itself rather than as an outage.

The work box sits behind one. Unreported, an `apply --offline` there says
`the install script exited 60` and nothing else — 60 being curl's code for a
certificate it will not verify, which is one CA import away from fixed and reads
as a blocked network. Every layer on that path can narrow its answer to a bool or
a bare number, and then the cause exists nowhere: not on screen, not in the run
record, not in the debug stream.

These pin the four places the reason survives.
"""

from __future__ import annotations

import httpx2
import pytest

from dotfiles import diagnose
from dotfiles import effects
from dotfiles import github_release
from dotfiles import network
from dotfiles.providers import script

INTERCEPTED = 'certificate verify failed: unable to get local issuer certificate'

CURL_REJECTED_A_CERTIFICATE = """curl: (60) SSL certificate OpenSSL verify result: unable to get local issuer certificate (20)
More details here: https://curl.se/docs/sslcerts.html

curl failed to verify the legitimacy of the server and therefore could not
establish a secure connection to it. To learn more about this situation and
how to fix it, please visit the webpage mentioned above.
"""
"""Verbatim, from `20260817T211750Z-pf5xmxfy-apply.jsonl` on the work box.

Written out rather than shortened because the shape is the subject: five non-blank
lines, the cause on the first and three lines of closing advice at the end. A
paraphrase with the marker anywhere else is the test that passed while the machine
it was written for got nothing.
"""


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

    def test_the_fix_names_a_store_that_exists_and_the_command_that_refreshes_it(self, tmp_path) -> None:
        """A reader told to drop a CA where their distribution does not look will
        conclude the certificate was not the problem.

        The stores are passed rather than read off this machine, so the assertion is
        about the branch rather than about whichever distribution runs the suite."""
        store = tmp_path / 'anchors'
        store.mkdir()
        found = diagnose._intercepted({str(tmp_path / 'absent'): 'never', str(store): 'sudo refresh-trust'})

        assert found.fix == f'install the proxy CA into {store}, then: sudo refresh-trust'
        assert not found.unavailable

    def test_a_machine_with_no_known_store_says_so_rather_than_naming_a_wrong_one(self, tmp_path) -> None:
        """The branch both Macs take, since none of the three Linux trust-store
        directories exists there — macOS keeps its in the Keychain. Read off the real
        machine, this was asserted by `all([])` and passed without reaching it."""
        found = diagnose._intercepted({str(tmp_path / 'absent'): 'never'})

        assert found.fix == ''
        assert found.unavailable
        assert 'no known trust-store directory' in found.unavailable[0]

    def test_every_store_carries_the_command_that_rebuilds_it(self) -> None:
        """Two structures that must stay in lockstep drift, and the drift lands inside
        the error path — the lookup ran while composing a diagnosis."""
        assert all(command.startswith('sudo ') for command in diagnose.TRUST_STORES.values())

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
        assert measured.refusal is network.Refusal.INTERCEPTED

    def test_a_refused_connection_carries_curls_own_meaning(self, monkeypatch) -> None:
        probe = network.Probe('github_release', 'fd', 'https://github.com/x/fd/releases/latest')
        monkeypatch.setattr(effects, 'run', lambda *args, **kwargs: effects.Completed(command=('curl',), returncode=7, transcript=''))

        measured = network.measure(probe)

        assert measured.refusal is network.Refusal.BLOCKED
        assert 'refused or filtered' in measured.detail

    def test_a_reachable_host_carries_no_reason(self, monkeypatch) -> None:
        """A reason invented for every row is a reason nobody reads."""
        probe = network.Probe('github_release', 'fd', 'https://github.com/x/fd/releases/latest')
        monkeypatch.setattr(effects, 'run', lambda *args, **kwargs: effects.Completed(command=('curl',), returncode=0, transcript=''))

        assert network.measure(probe).refusal is network.Refusal.NONE


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

    def test_curls_own_layout_keeps_the_cause_the_tail_would_drop(self) -> None:
        """curl prints its diagnosis first and five lines of advice after it, so the
        tail is boilerplate and the marker falls outside the budget. Recorded on the
        work box eight times on 2026-08-17, every line of it curl's closing advice."""
        completed = effects.Completed(command=('bash',), returncode=60, transcript=CURL_REJECTED_A_CERTIFICATE)

        said = script.failure('claude-code', completed)

        assert 'unable to get local issuer certificate' in said
        assert 'please visit the webpage mentioned above' in said

    def test_a_carried_cause_reaches_the_advice_the_machine_is_owed(self) -> None:
        """The whole point of keeping it: `explain` matches on that line, so trimming it
        left the one machine this diagnosis was written for reading raw curl text."""
        completed = effects.Completed(command=('bash',), returncode=60, transcript=CURL_REJECTED_A_CERTIFICATE)

        explained = diagnose.explain('packages/custom/claude-code', script.failure('claude-code', completed))

        assert diagnose.INTERCEPTED_CAUSE in explained

    def test_a_cause_already_in_the_tail_is_not_repeated(self) -> None:
        completed = effects.Completed(command=('bash',), returncode=60, transcript=f'downloading\ncurl: (60) {INTERCEPTED}\n')

        assert script.failure('claude-code', completed).count(INTERCEPTED) == 1


@pytest.mark.parametrize('code', [6, 7, 28, 35, 60])
def test_every_named_curl_code_reads_as_a_sentence(code: int) -> None:
    assert diagnose.curl_cause(code).startswith('the ')
