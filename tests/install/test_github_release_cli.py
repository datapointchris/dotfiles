"""The by-hand door, and the two lookups a version pin depends on.

`python -m dotfiles.github_release` is how the checksum rules are exercised
without running an install, and its exit codes are the interface — `Verification`
says so at the enum. Nothing in the package calls it, by design, so the only thing
that can execute the dispatch is a test that comes in the same way a person does:
the four verbs, the two options `verify` takes, and the order its six arguments
are handed on in.

`tag_for_version` decides what a `version:` in `packages.yml` actually installs,
and it is the reason a pin is written bare rather than as a tag. Both tests that
reach it replace the whole function, so what a pin resolved to was asserted
against a lambda. The three spellings in the table below are the three a real
entry uses.

`release_assets` answers `{}` for a release it could not read, which is the same
answer it gives for a release that published nothing. The last test in
`TestReleaseAssets` holds that shape rather than describing it.

Only the transport is faked. `request` is this module's one call to the network,
and everything above it — the URLs, the tag encoding, the asset selection, the
digest comparison — runs for real.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

import httpx2
import pytest

from dotfiles import github_release

PAYLOAD = b'#!/bin/sh\necho installed\n'

DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
"""Computed here rather than through `sha256_of`, which is what these assert."""

ASSET = 'demo-linux-x86_64.tar.gz'

RELEASE_LIST = 'https://api.github.com/repos/owner/repo/releases?per_page=100'


def refuse(url: str, status: int = 404) -> NoReturn:
    """The refusal a real host answers with, built the way `request` receives it."""
    asked = httpx2.Request('GET', url)
    raise httpx2.HTTPStatusError(f'{status}', request=asked, response=httpx2.Response(status, request=asked))


class FakeGitHub:
    """The transport, and nothing above it.

    An unserved URL is refused with a 404 rather than answered with an empty body,
    because a caller that builds the wrong URL has to fail here — where the URL it
    built is visible — instead of reading a plausible blank two frames later. That
    is the whole reason these tests can assert on `asked` at all.
    """

    def __init__(self) -> None:
        self.pages: dict[str, bytes] = {}
        self.asked: list[str] = []

    def serve(self, url: str, body: object) -> None:
        self.pages[url] = body if isinstance(body, bytes) else json.dumps(body).encode()

    def __call__(self, url: str, accept: str | None = None) -> bytes:
        self.asked.append(url)
        if url not in self.pages:
            refuse(url)
        return self.pages[url]


def connect_error(url: str, accept: str | None = None) -> bytes:
    raise httpx2.ConnectError('no route to host')


def not_found(url: str, accept: str | None = None) -> bytes:
    refuse(url)


def not_json(url: str, accept: str | None = None) -> bytes:
    """A captive portal or a proxy interstitial, which answers 200 with HTML."""
    return b'<html><title>502 Bad Gateway</title></html>'


unreadable = pytest.mark.parametrize('transport', [connect_error, not_found, not_json], ids=['no-route', '404', 'not-json'])


@pytest.fixture
def github(monkeypatch: pytest.MonkeyPatch) -> FakeGitHub:
    fake = FakeGitHub()
    monkeypatch.setattr(github_release, 'request', fake)
    return fake


@pytest.fixture
def no_github_credential(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A machine with no token, so `download_asset` takes one known branch.

    `github_token` reads `$GITHUB_TOKEN` and then asks a real `gh` on PATH, so on a
    logged-in desk the credentialed asset-API path runs and on a runner it does
    not — the same test asking the transport for different URLs depending on whose
    machine it is. Both variables are the product's own knobs.
    """
    empty = tmp_path / 'no-tools'
    empty.mkdir()
    monkeypatch.delenv('GITHUB_TOKEN', raising=False)
    monkeypatch.setenv('PATH', str(empty))


def published(*tags: str) -> list[dict]:
    return [{'tag_name': tag, 'draft': False} for tag in tags]


def downloaded(directory: Path, name: str = ASSET) -> Path:
    path = directory / name
    path.write_bytes(PAYLOAD)
    return path


def checksums_file(directory: Path, digest: str = DIGEST, asset: str = ASSET) -> Path:
    path = directory / 'checksums.txt'
    path.write_text(f'{digest}  {asset}\n')
    return path


class TestTagForVersion:
    """What a bare pin in `packages.yml` resolves to, against what upstream published.

    The pin is deliberately a version and never a tag, because one release is
    spelled `v0.56.0` by lazygit, `0.8.30` by terraformer and `cli/v0.9.0` by the
    personal CLIs — so the matching, not the spelling, is what makes one pin work
    everywhere. Every row below is one of those three shapes or a refusal.
    """

    @pytest.mark.parametrize(
        ('tags', 'pin', 'prefix', 'resolves_to'),
        [
            # lazygit: a `v` the pin does not carry.
            (['v0.55.0', 'v0.56.0'], '0.56.0', '', 'v0.56.0'),
            # terraformer: no `v` at all, and the same pin has to reach it.
            (['0.8.29', '0.8.30'], '0.8.30', '', '0.8.30'),
            # The personal CLIs, in a repo that also releases an API.
            (['api/v2.0.0', 'cli/v0.9.0'], '0.9.0', 'cli/', 'cli/v0.9.0'),
            # A pin someone wrote as the tag still names the same release.
            (['v0.56.0'], 'v0.56.0', '', 'v0.56.0'),
            # Nothing published it. The refusal nothing else in the suite pins.
            (['v0.55.0', 'v0.57.0'], '0.56.0', '', None),
            # The prefix is part of the question: the API's own release is not the CLI's.
            (['v0.9.0'], '0.9.0', 'cli/', None),
            (['cli/v0.9.0'], '0.9.0', '', None),
            # Exact, never a prefix of: 0.9.1 must not answer for a pin of 0.9.
            (['0.9.10'], '0.9.1', '', None),
            (['v0.56.0'], '0.5', '', None),
        ],
    )
    def test_a_bare_pin_matches_whichever_spelling_the_repo_publishes(self, github, tags, pin, prefix, resolves_to):
        github.serve(RELEASE_LIST, published(*tags))

        assert github_release.tag_for_version('owner/repo', pin, prefix) == resolves_to

    def test_a_pin_nothing_published_refuses_instead_of_naming_the_newest(self, github):
        """The one thing a pin does. `resolve_tag` hands this straight to the
        installer, so an answer here of "the latest one" would install something
        the machine did not ask for and report it as the pinned version."""
        github.serve(RELEASE_LIST, published('v0.55.0', 'v0.57.0'))
        github.serve('https://api.github.com/repos/owner/repo/releases/latest', {'tag_name': 'v0.57.0'})

        assert github_release.tag_for_version('owner/repo', '0.56.0') is None
        assert github_release.latest_version('owner/repo') == 'v0.57.0', 'a newest release exists and was still not offered'

    def test_a_draft_never_satisfies_a_pin(self, github):
        """A draft is a tag nobody outside the repo can download. Matching one
        resolves the pin to a release and then fails at the asset."""
        github.serve(RELEASE_LIST, [{'tag_name': 'v0.56.0', 'draft': True}, {'tag_name': 'v0.55.0', 'draft': False}])

        assert github_release.tag_for_version('owner/repo', '0.56.0') is None
        assert github_release.tag_for_version('owner/repo', '0.55.0') == 'v0.55.0'

    def test_the_pin_is_matched_against_one_listing_rather_than_asked_for_by_name(self, github):
        """`releases/tags/v0.56.0` would answer only the spelling the caller guessed,
        which is the guess the bare pin exists to avoid. One listing is also one
        request against a rate limit `check` shares with every declared release."""
        github.serve(RELEASE_LIST, published('v0.56.0'))

        github_release.tag_for_version('owner/repo', '0.56.0')

        assert github.asked == [RELEASE_LIST]

    def test_a_pin_older_than_one_page_of_releases_is_refused_like_one_nothing_published(self, github):
        """One page is the whole of what this reads, and a hundred is what GitHub
        answers with. So a pin from a hundred releases ago is unreachable, and the
        refusal is the same None as a version that was never published — which
        `unresolved` reports to the machine as an upstream fact."""
        page = [f'v1.{minor}.0' for minor in range(200, 100, -1)]
        github.serve(RELEASE_LIST, published(*page))

        assert github_release.tag_for_version('owner/repo', '1.200.0') == 'v1.200.0'
        assert github_release.tag_for_version('owner/repo', '1.50.0') is None

    @unreadable
    def test_an_unreadable_listing_answers_nothing_rather_than_raising(self, monkeypatch, transport):
        """Three ways the same page fails to arrive, and one answer.

        Which is also the conflation worth knowing about: this None and the None
        above are the same value, so `ghrelease.unresolved` reports a network that
        would not answer as "upstream publishes no release for that version".
        """
        monkeypatch.setattr(github_release, 'request', transport)

        assert github_release.tag_for_version('owner/repo', '0.56.0') is None


class TestReleaseAssets:
    """The name-to-id mapping the private-repo download path and the checksum
    selector are both built on."""

    def test_every_published_asset_is_named_with_the_id_the_asset_endpoint_wants(self, github):
        github.serve(
            'https://api.github.com/repos/owner/repo/releases/tags/v1.0.0',
            {'assets': [{'name': ASSET, 'id': 41}, {'name': 'checksums.txt', 'id': 42}]},
        )

        assert github_release.release_assets('owner/repo', 'v1.0.0') == {ASSET: 41, 'checksums.txt': 42}

    def test_a_tag_carrying_a_slash_is_encoded_into_one_path_segment(self, github):
        """`cli/v0.9.0` unencoded reads as `releases/tags/cli/v0.9.0`, which is a
        route the API does not have — so every personal CLI would resolve to no
        assets at all, and that is indistinguishable from a release with none."""
        encoded = 'https://api.github.com/repos/owner/repo/releases/tags/cli%2Fv0.9.0'
        github.serve(encoded, {'assets': [{'name': ASSET, 'id': 7}]})

        assert github_release.release_assets('owner/repo', 'cli/v0.9.0') == {ASSET: 7}
        assert github.asked == [encoded]

    @pytest.mark.parametrize('body', [{'assets': []}, {'tag_name': 'v1.0.0'}], ids=['empty', 'no-assets-key'])
    def test_a_release_publishing_nothing_answers_an_empty_mapping(self, github, body):
        github.serve('https://api.github.com/repos/owner/repo/releases/tags/v1.0.0', body)

        assert github_release.release_assets('owner/repo', 'v1.0.0') == {}

    @unreadable
    def test_an_unreadable_release_answers_an_empty_mapping_rather_than_raising(self, monkeypatch, transport):
        monkeypatch.setattr(github_release, 'request', transport)

        assert github_release.release_assets('owner/repo', 'v1.0.0') == {}

    @unreadable
    def test_an_unreadable_release_reads_as_a_release_that_publishes_no_checksums(self, tmp_path, monkeypatch, transport):
        """`{}` is the answer for both, so the verdict is UNPUBLISHED either way.

        That verdict is a claim about upstream, and here it is a fact about the
        network. An entry declaring `checksum: unpublished` — the declaration that
        says "this release genuinely has none" — installs on that verdict, so an
        API that will not answer installs it unverified. Held here rather than
        argued: the file is untouched and the exit code is 2, not 1.
        """
        monkeypatch.setattr(github_release, 'request', transport)
        payload = downloaded(tmp_path)

        outcome = github_release.verify_release_checksum(payload, ASSET, 'owner/repo', 'v1.0.0')

        assert outcome is github_release.Verification.UNPUBLISHED
        assert payload.read_bytes() == PAYLOAD


class TestVerifyByHand:
    """`verify` answers with its exit code and nothing else.

    `Verification`'s values are the CLI's exit codes so a shell can `case` on `$?`,
    which makes stdout part of the contract too: a caller reading it gets nothing,
    and the log lines go to stderr.
    """

    def test_a_matching_digest_exits_verified_and_prints_nothing(self, tmp_path, capsys):
        payload = downloaded(tmp_path)

        code = github_release.main(['verify', str(payload), ASSET, '--bundle-checksums', str(checksums_file(tmp_path))])

        assert code == github_release.Verification.VERIFIED
        assert capsys.readouterr().out == ''
        assert payload.exists()

    def test_a_tampered_file_exits_failed_and_is_deleted(self, tmp_path):
        payload = downloaded(tmp_path)
        recorded = checksums_file(tmp_path)
        payload.write_bytes(b'not what was digested')

        code = github_release.main(['verify', str(payload), ASSET, '--bundle-checksums', str(recorded)])

        assert code == github_release.Verification.FAILED
        assert not payload.exists()

    @pytest.mark.parametrize('source', [[], ['owner/repo']], ids=['no-repo', 'repo-without-tag'])
    def test_a_source_that_names_no_release_exits_unpublished(self, tmp_path, source):
        """Both positionals are optional and only both together name a release, so
        one of them is the same as neither — a non-GitHub source, which has no
        published checksums to consult."""
        payload = downloaded(tmp_path)

        code = github_release.main(['verify', str(payload), ASSET, *source])

        assert code == github_release.Verification.UNPUBLISHED
        assert payload.exists()

    def test_the_repo_and_tag_positionals_reach_the_release_they_name(self, tmp_path, github, no_github_credential):
        """The whole chain, with only the transport replaced: the release is read,
        its checksums file is chosen out of the asset names, downloaded from the
        browser URL and compared against the bytes on disk.

        Swapping the two positionals is the failure this shape catches, and neither
        a return code nor a printed sentence would show it — the URLs would.
        """
        payload = downloaded(tmp_path)
        github.serve(
            'https://api.github.com/repos/owner/repo/releases/tags/v1.0.0',
            {'assets': [{'name': ASSET, 'id': 1}, {'name': 'checksums.txt', 'id': 2}]},
        )
        github.serve('https://github.com/owner/repo/releases/download/v1.0.0/checksums.txt', f'{DIGEST}  {ASSET}\n'.encode())

        code = github_release.main(['verify', str(payload), ASSET, 'owner/repo', 'v1.0.0'])

        assert code == github_release.Verification.VERIFIED
        assert github.asked == [
            'https://api.github.com/repos/owner/repo/releases/tags/v1.0.0',
            'https://github.com/owner/repo/releases/download/v1.0.0/checksums.txt',
        ]

    def test_an_asset_the_published_file_does_not_list_exits_unlisted(self, tmp_path, github, no_github_credential):
        """Distinct from both its neighbours on purpose: something is published, so
        the tool is one upstream fix away from verifiable, and nothing was compared
        — which is why the download is kept rather than deleted."""
        payload = downloaded(tmp_path)
        github.serve(
            'https://api.github.com/repos/owner/repo/releases/tags/v1.0.0',
            {'assets': [{'name': ASSET, 'id': 1}, {'name': 'checksums.txt', 'id': 2}]},
        )
        github.serve('https://github.com/owner/repo/releases/download/v1.0.0/checksums.txt', b'aaaa  some-other-tool.tar.gz\n')

        code = github_release.main(['verify', str(payload), ASSET, 'owner/repo', 'v1.0.0'])

        assert code == github_release.Verification.UNLISTED
        assert payload.exists()

    def test_checksum_url_names_the_file_directly_for_a_release_github_does_not_host(self, tmp_path, github):
        """hashicorp and the AWS CLI serve their own checksums, so there is no
        release to read the asset names out of and the URL is the declaration."""
        payload = downloaded(tmp_path)
        github.serve('https://releases.hashicorp.com/demo/1.0/demo_SHA256SUMS', f'{DIGEST}  {ASSET}\n'.encode())

        code = github_release.main(
            ['verify', str(payload), ASSET, '--checksum-url', 'https://releases.hashicorp.com/demo/1.0/demo_SHA256SUMS']
        )

        assert code == github_release.Verification.VERIFIED
        assert github.asked == ['https://releases.hashicorp.com/demo/1.0/demo_SHA256SUMS']

    def test_a_checksum_url_that_will_not_answer_exits_failed(self, tmp_path, github):
        """The one place a network failure is FAILED rather than UNPUBLISHED: the
        declaration named a file, so its absence is a broken declaration rather
        than a release that publishes nothing."""
        payload = downloaded(tmp_path)

        code = github_release.main(['verify', str(payload), ASSET, '--checksum-url', 'https://releases.hashicorp.com/gone'])

        assert code == github_release.Verification.FAILED
        assert payload.exists(), 'nothing was compared, so nothing may be deleted'


class TestLookupsByHand:
    """The three verbs that read something and print it, and what they print when
    the answer is nothing."""

    @pytest.mark.parametrize(
        ('url', 'printed'),
        [
            ('https://github.com/sharkdp/fd/releases/download/v10.2.0/fd.tar.gz', 'sharkdp/fd|v10.2.0\n'),
            # A nested module's tag keeps its slashes, which is why the tag is the
            # rest of the path rather than one segment.
            ('https://github.com/owner/repo/releases/download/cli/v0.9.0/icb.tar.gz', 'owner/repo|cli/v0.9.0\n'),
            # Not a GitHub release: recording a checksum against one of these would
            # claim a verification that never happened.
            ('https://releases.hashicorp.com/terraform/1.0/terraform.zip', ''),
            ('https://astral.sh/uv/install.sh', ''),
        ],
    )
    def test_parse_url_prints_the_pair_or_nothing_and_succeeds_either_way(self, capsys, url, printed):
        """Both answers exit 0, so the caller reads the output rather than `$?`.
        The rows that print are what makes an empty answer mean "not a release"
        instead of "the printer is broken"."""
        code = github_release.main(['parse-url', url])

        assert code == 0
        assert capsys.readouterr().out == printed

    @pytest.mark.parametrize(
        ('asset', 'printed'),
        [(ASSET, f'{DIGEST}\n'), ('some-other-tool.tar.gz', '')],
        ids=['listed', 'unlisted'],
    )
    def test_checksum_for_prints_the_digest_or_nothing_and_succeeds_either_way(self, tmp_path, capsys, asset, printed):
        code = github_release.main(['checksum-for', str(checksums_file(tmp_path)), asset])

        assert code == 0
        assert capsys.readouterr().out == printed

    def test_sha256_prints_the_digest_and_nothing_else(self, tmp_path, capsys):
        """A shell reads this through `$(...)`, so a second line of any kind is a
        digest that no longer compares equal to anything."""
        code = github_release.main(['sha256', str(downloaded(tmp_path))])

        assert code == 0
        assert capsys.readouterr().out == f'{DIGEST}\n'

    @pytest.mark.parametrize('argv', [[], ['checksum'], ['sha256']], ids=['no-verb', 'wrong-verb', 'no-file'])
    def test_a_call_the_door_does_not_have_refuses_rather_than_guessing(self, capsys, argv):
        """`sha256` is the fallthrough of the dispatch, so a verb that reaches it by
        accident hashes a file nobody asked about and prints a digest that looks
        exactly like a right answer."""
        with pytest.raises(SystemExit) as refused:
            github_release.main(argv)

        assert refused.value.code == 2
        assert capsys.readouterr().out == ''


class TestModuleEntryPoint:
    """The documented invocation, run the way the docstring writes it.

    In a subprocess because `sys.exit(main())` is the line that turns a
    `Verification` into a shell's `$?`, and calling `main` in process never
    reaches it.
    """

    def run(self, tmp_path: Path, *argv: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, '-m', 'dotfiles.github_release', *argv],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_path,
        )

    def test_the_module_runs_by_hand_and_prints_the_digest(self, tmp_path):
        answered = self.run(tmp_path, 'sha256', str(downloaded(tmp_path)))

        assert answered.returncode == 0
        assert answered.stdout == f'{DIGEST}\n'

    def test_a_failed_verification_leaves_the_shell_a_non_zero_status(self, tmp_path):
        payload = downloaded(tmp_path)
        recorded = checksums_file(tmp_path)
        payload.write_bytes(b'not what was digested')

        answered = self.run(tmp_path, 'verify', str(payload), ASSET, '--bundle-checksums', str(recorded))

        assert answered.returncode == github_release.Verification.FAILED
        assert answered.stdout == '', 'the whole answer is the status, so a `case` on it reads a clean stdout'
