"""Tests for github_release.py

The checksum rules here are shared by the offline bundler and the shell
installer, so a divergence would mean a bundle verifying differently from a live
install. Every fallback below was earned by a real release.

Run with: pytest tests/install/test_github_release.py
"""

import httpx2

from dotfiles import github_release


class TestChecksumAssetSelection:
    def test_a_per_asset_sidecar_wins_over_a_combined_file(self):
        names = ['tool.tar.gz', 'tool.tar.gz.sha256', 'checksums.txt']
        assert github_release.select_checksum_asset(names, 'tool.tar.gz') == 'tool.tar.gz.sha256'

    def test_a_combined_file_is_the_fallback(self):
        names = ['tool.tar.gz', 'checksums.txt']
        assert github_release.select_checksum_asset(names, 'tool.tar.gz') == 'checksums.txt'
        assert github_release.select_checksum_asset(['SHA256SUMS'], 'tool.tar.gz') == 'SHA256SUMS'

    def test_signatures_and_certificates_are_never_mistaken_for_checksums(self):
        # tflint publishes all three; picking a .sig would compare the asset
        # against a signature.
        names = ['checksums.txt.keyless.sig', 'checksums.txt.pem', 'checksums.txt']
        assert github_release.select_checksum_asset(names, 'tool.zip') == 'checksums.txt'

        for aux in ['checksums.txt.sig', 'checksums.txt.asc', 'checksums.json', 'checksums.txt-bsd']:
            assert github_release.select_checksum_asset([aux], 'tool.zip') is None

    def test_a_release_publishing_nothing_usable_returns_none(self):
        assert github_release.select_checksum_asset(['tool.tar.gz', 'README.md'], 'tool.tar.gz') is None
        assert github_release.select_checksum_asset([], 'tool.tar.gz') is None


class TestChecksumLookup:
    def test_the_sha256sum_format_including_the_binary_marker(self):
        text = 'abc123  other.tar.gz\ndef456  tool.tar.gz\n'
        assert github_release.checksum_for_asset(text, 'tool.tar.gz') == 'def456'
        assert github_release.checksum_for_asset('def456 *tool.tar.gz\n', 'tool.tar.gz') == 'def456'

    def test_a_leading_path_is_stripped_only_when_nothing_matched_exactly(self):
        # `sha256sum ./*.tar.gz` in CI records ./tool.tar.gz for an asset named
        # tool.tar.gz — the same file under a different spelling.
        assert github_release.checksum_for_asset('def456  ./tool.tar.gz\n', 'tool.tar.gz') == 'def456'
        # An exact match still wins over a base-name match elsewhere in the file.
        text = 'aaa  ./tool.tar.gz\nbbb  tool.tar.gz\n'
        assert github_release.checksum_for_asset(text, 'tool.tar.gz') == 'bbb'

    def test_case_differences_are_accepted_because_github_resolves_them(self):
        # The shape that earned this: lazygit fetched Linux_x86_64 against a
        # recorded linux_x86_64, until its URL builder was corrected.
        text = 'def456  lazygit_0.44_linux_x86_64.tar.gz\n'
        assert github_release.checksum_for_asset(text, 'lazygit_0.44_Linux_x86_64.tar.gz') == 'def456'

    def test_a_bare_digest_counts_only_in_a_file_containing_nothing_else(self):
        digest = 'a' * 64
        assert github_release.checksum_for_asset(f'{digest}\n', 'tool.tar.gz') == digest
        # In a combined file the same line would be an unrelated stray.
        assert github_release.checksum_for_asset(f'{digest}\nbbb  other.tar.gz\n', 'tool.tar.gz') is None

    def test_an_unreadable_table_yields_nothing_rather_than_a_wrong_digest(self):
        # yq publishes an rhash table: name first, one column per algorithm.
        assert github_release.checksum_for_asset('yq_linux_amd64 MD5:abc SHA256:def\n', 'yq_linux_amd64') is None

    def test_carriage_returns_do_not_defeat_the_match(self):
        assert github_release.checksum_for_asset('def456  tool.tar.gz\r\n', 'tool.tar.gz') == 'def456'


class TestReleaseUrl:
    def test_repo_and_tag_are_recovered_including_a_tag_with_slashes(self):
        assert github_release.parse_release_url('https://github.com/sharkdp/fd/releases/download/v10.2.0/fd.tar.gz') == (
            'sharkdp/fd',
            'v10.2.0',
        )
        assert github_release.parse_release_url('https://github.com/o/r/releases/download/cli/v1.0/x.tar.gz') == ('o/r', 'cli/v1.0')

    def test_anything_that_is_not_a_github_release_is_rejected(self):
        # Recording a checksum for one of these would claim a verification that
        # never happened — hashicorp serves from releases.hashicorp.com.
        assert github_release.parse_release_url('https://releases.hashicorp.com/terraform/1.0/terraform.zip') is None
        assert github_release.parse_release_url('https://astral.sh/uv/install.sh') is None


class TestVerification:
    """The exit codes are the shell library's `case` labels, so they are part of
    the interface, not an implementation detail.
    """

    def test_a_matching_digest_verifies(self, tmp_path):
        payload = tmp_path / 'tool.tar.gz'
        payload.write_text('payload bytes')
        checksums = tmp_path / 'checksums.txt'
        checksums.write_text(f'{github_release.sha256_of(payload)}  tool.tar.gz\n')

        outcome = github_release.verify_release_checksum(payload, 'tool.tar.gz', bundle_checksums=checksums)

        assert outcome is github_release.Verification.VERIFIED
        assert outcome == 0
        assert payload.exists()

    def test_a_tampered_file_fails_and_is_deleted(self, tmp_path):
        payload = tmp_path / 'tool.tar.gz'
        payload.write_text('payload bytes')
        checksums = tmp_path / 'checksums.txt'
        checksums.write_text(f'{github_release.sha256_of(payload)}  tool.tar.gz\n')
        payload.write_text('tampered')

        outcome = github_release.verify_release_checksum(payload, 'tool.tar.gz', bundle_checksums=checksums)

        assert outcome is github_release.Verification.FAILED
        # Deleted so a retry cannot extract bytes that already failed.
        assert not payload.exists()

    def test_an_asset_the_bundle_does_not_record_defers_rather_than_failing(self, tmp_path):
        payload = tmp_path / 'other.tar.gz'
        payload.write_text('payload')
        checksums = tmp_path / 'checksums.txt'
        checksums.write_text('abc  tool.tar.gz\n')

        # No repo/tag either, so there is nothing to fall through to.
        outcome = github_release.verify_release_checksum(payload, 'other.tar.gz', bundle_checksums=checksums)

        assert outcome is github_release.Verification.UNPUBLISHED
        assert payload.exists()

    def test_a_non_github_source_with_no_checksum_url_is_unpublished(self, tmp_path):
        payload = tmp_path / 'terraform.zip'
        payload.write_text('payload')

        assert github_release.verify_release_checksum(payload, 'terraform.zip') is github_release.Verification.UNPUBLISHED


class TestSidecarChecksums:
    """A per-asset `<asset>.sha256` names its subject in its filename, so a bare
    digest inside it is unambiguous in a way the same line in a combined file is
    not.
    """

    # Verbatim from ripgrep's Windows sidecar, which Windows CertUtil produces.
    CERTUTIL = (
        'SHA256 hash of ripgrep-15.2.0-x86_64-pc-windows-msvc.zip:\r\n'
        '71b2fef860abe467217a538ff31de02f5258807c0129f771846f87bd029aafc5\r\n'
        'CertUtil: -hashfile command completed successfully.\r\n'
    )
    ASSET = 'ripgrep-15.2.0-x86_64-pc-windows-msvc.zip'

    def test_a_certutil_sidecar_yields_its_digest(self):
        digest = github_release.checksum_for_asset(self.CERTUTIL, self.ASSET, from_sidecar=True)
        assert digest == '71b2fef860abe467217a538ff31de02f5258807c0129f771846f87bd029aafc5'

    def test_the_same_text_in_a_combined_file_is_still_refused(self):
        # Two lines of prose around it, so the digest names no asset. Trusting it
        # in a combined file would attach one tool's digest to another's bytes.
        assert github_release.checksum_for_asset(self.CERTUTIL, self.ASSET) is None

    def test_a_named_entry_still_wins_over_a_bare_digest(self):
        text = f'{"a" * 64}\ndeadbeef  {self.ASSET}\n'
        assert github_release.checksum_for_asset(text, self.ASSET, from_sidecar=True) == 'deadbeef'

    def test_every_sidecar_suffix_is_recognised_as_one(self):
        for suffix in github_release.CHECKSUM_SIDECAR_SUFFIXES:
            names = ['tool.tar.gz', f'tool.tar.gz{suffix}']
            assert github_release.select_checksum_asset(names, 'tool.tar.gz').endswith(suffix)


class TestChecksumStaging:
    """Where the published checksums file is put while it is being read.

    A fixed path is shared by every user on the box and identical on every run, so
    anyone can plant a symlink there for `write_bytes` to follow. A stale file
    another user owns is the quieter half of the same fault: the write raises, the
    download reads as failed, and every install of that tool fails for good with a
    message blaming the network.
    """

    ASSET = 'tool.tar.gz'

    def stage(self, tmp_path, monkeypatch) -> list:
        """Verify one asset, recording where the checksums file was written to."""
        payload = tmp_path / self.ASSET
        payload.write_text('payload bytes')
        staged: list = []

        monkeypatch.setattr(github_release, 'release_assets', lambda repo, tag: {self.ASSET: 1, 'checksums.txt': 2})

        def download(url, destination, repo='', tag='', asset_name=''):
            staged.append(destination)
            destination.write_text(f'{github_release.sha256_of(payload)}  {self.ASSET}\n')
            return True

        monkeypatch.setattr(github_release, 'download_asset', download)

        outcome = github_release.verify_release_checksum(payload, self.ASSET, repo='owner/repo', tag='v1.0.0')
        assert outcome is github_release.Verification.VERIFIED
        return staged

    def test_two_runs_never_stage_at_the_same_path(self, tmp_path, monkeypatch):
        """The security property in the form a test can hold: an attacker cannot
        know where the next run will write, because no two runs agree on it."""
        first = self.stage(tmp_path, monkeypatch)
        second = self.stage(tmp_path, monkeypatch)

        assert first[0] != second[0]

    def test_the_staged_file_and_its_directory_are_gone_afterwards(self, tmp_path, monkeypatch):
        staged = self.stage(tmp_path, monkeypatch)[0]

        assert not staged.exists()
        assert not staged.parent.exists()


class TestLatestVersion:
    """The prefixed form exists because four declared releases are CLIs living in
    a repo that also releases an API and a web app. `releases/latest` there
    answers with whichever component shipped most recently, so asking it about
    `icb` reports the CLI outdated every time the API ships."""

    def test_no_prefix_reads_the_latest_release_endpoint(self, monkeypatch):
        seen = []

        def fake(url, accept=None):
            seen.append(url)
            return b'{"tag_name": "v1.2.3"}'

        monkeypatch.setattr(github_release, 'request', fake)

        assert github_release.latest_version('owner/repo') == 'v1.2.3'
        assert seen == ['https://api.github.com/repos/owner/repo/releases/latest']

    def test_a_prefix_takes_the_newest_release_carrying_it(self, monkeypatch):
        payload = b'[{"tag_name": "api/2.0.0", "draft": false}, {"tag_name": "cli/1.4.0", "draft": false}]'
        monkeypatch.setattr(github_release, 'request', lambda url, accept=None: payload)

        assert github_release.latest_version('owner/repo', 'cli/') == 'cli/1.4.0'

    def test_a_double_digit_minor_outranks_a_single_digit_one(self, monkeypatch):
        """GitHub ranks these tags as strings, so 0.9.1 arrives ahead of 0.10.0.

        Measured against meso 2026-08-14: cli/v0.9.1 came back first while
        cli/v0.10.0 was newer by both created_at and published_at. Taking the
        first match froze the tool at 0.9.x and reported the machine converged.
        """
        payload = b'[{"tag_name": "cli/v0.9.1", "draft": false}, {"tag_name": "cli/v0.10.0", "draft": false}]'
        monkeypatch.setattr(github_release, 'request', lambda url, accept=None: payload)

        assert github_release.latest_version('owner/repo', 'cli/') == 'cli/v0.10.0'

    def test_a_draft_is_not_a_release_anyone_can_install(self, monkeypatch):
        payload = b'[{"tag_name": "cli/2.0.0", "draft": true}, {"tag_name": "cli/1.4.0", "draft": false}]'
        monkeypatch.setattr(github_release, 'request', lambda url, accept=None: payload)

        assert github_release.latest_version('owner/repo', 'cli/') == 'cli/1.4.0'

    def test_a_prefix_nothing_matches_answers_nothing(self, monkeypatch):
        payload = b'[{"tag_name": "api/2.0.0", "draft": false}]'
        monkeypatch.setattr(github_release, 'request', lambda url, accept=None: payload)

        assert github_release.latest_version('owner/repo', 'cli/') is None

    def test_an_unreachable_api_answers_nothing_rather_than_raising(self, monkeypatch):
        def refuse(url, accept=None):
            raise httpx2.ConnectError('no route to host')

        monkeypatch.setattr(github_release, 'request', refuse)

        assert github_release.latest_version('owner/repo') is None
        assert github_release.latest_version('owner/repo', 'cli/') is None


class TestLatestTag:
    """For a project that tags every build and publishes no release.

    `aws/aws-cli` is the only one, and it is why this exists at all: its
    `releases/latest` answers 404 while `tags` lists `2.36.19`.
    """

    @staticmethod
    def answering(monkeypatch, names: list[str]) -> None:
        payload = ('[' + ', '.join(f'{{"name": "{name}"}}' for name in names) + ']').encode()
        monkeypatch.setattr(github_release, 'request', lambda url, accept=None: payload)

    def test_the_greatest_version_wins_whatever_order_the_page_arrives_in(self, monkeypatch):
        """GitHub documents no ordering for this endpoint. It answers newest-first
        in practice, and comparing rather than trusting that costs one pass over a
        list already in memory."""
        self.answering(monkeypatch, ['2.36.9', '2.36.19', '2.36.17'])

        assert github_release.latest_tag('aws/aws-cli') == '2.36.19'

    def test_a_major_version_still_maintained_does_not_win(self, monkeypatch):
        """aws-cli tags v1 alongside v2, and 1.42.0 sorts above 2.36.19 as a
        string. Compared as numbers, it does not."""
        self.answering(monkeypatch, ['1.42.0', '2.36.19'])

        assert github_release.latest_tag('aws/aws-cli') == '2.36.19'

    def test_a_tag_holding_no_version_is_skipped_rather_than_guessed_at(self, monkeypatch):
        self.answering(monkeypatch, ['nightly', '2.36.19', 'latest'])

        assert github_release.latest_tag('aws/aws-cli') == '2.36.19'

    def test_a_prefix_narrows_to_one_component_of_a_monorepo(self, monkeypatch):
        self.answering(monkeypatch, ['api/9.0.0', 'cli/1.2.0', 'cli/1.10.0'])

        assert github_release.latest_tag('owner/repo', 'cli/') == 'cli/1.10.0'

    def test_nothing_parseable_answers_nothing(self, monkeypatch):
        self.answering(monkeypatch, ['nightly', 'latest'])

        assert github_release.latest_tag('owner/repo') is None

    def test_an_unreachable_api_answers_nothing_rather_than_raising(self, monkeypatch):
        def refuse(url, accept=None):
            raise httpx2.ConnectError('no route to host')

        monkeypatch.setattr(github_release, 'request', refuse)

        assert github_release.latest_tag('aws/aws-cli') is None


class TestCredentialScope:
    """Where a GitHub token is allowed to go, which is two hosts and no others.

    It went on every request this module made, whatever the host — so
    `s3.amazonaws.com`, `releases.hashicorp.com`, `awscli.amazonaws.com` and
    `pypi.org` each received a GitHub PAT. S3 answered the one it did not
    recognise with a 400, which is how it surfaced: `mount-s3` stopped installing
    on any machine whose environment carried a token.
    """

    def test_the_api_and_the_site_are_authenticated(self):
        assert github_release.authorized_host('https://api.github.com/repos/owner/repo/releases/latest')
        assert github_release.authorized_host('https://github.com/owner/repo/releases/download/v1/asset.tar.gz')

    def test_a_third_party_host_is_not(self):
        for url in (
            'https://s3.amazonaws.com/mountpoint-s3-release/latest/x86_64/mount-s3.tar.gz',
            'https://releases.hashicorp.com/terraform-ls/0.39.0/terraform-ls.zip',
            'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip',
            'https://pypi.org/pypi/pyyaml/6.0/json',
        ):
            assert not github_release.authorized_host(url), url

    def test_the_asset_cdn_is_not_authenticated_even_though_github_redirects_there(self):
        """A release download lands on an S3-backed CDN carrying a pre-signed URL
        that needs nothing from us. Sending the token there is both the 400 and the
        leak, on the request path that runs most often."""
        assert not github_release.authorized_host('https://objects.githubusercontent.com/github-production-release-asset/1/2')

    def test_a_lookalike_host_is_not_authenticated(self):
        """Suffix matching would hand the token to anyone who can register a
        domain ending in the right letters."""
        for url in ('https://api.github.com.evil.test/x', 'https://notgithub.com/x', 'https://github.com.evil.test/x'):
            assert not github_release.authorized_host(url), url

    def test_the_client_strips_the_credential_across_a_redirect(self):
        """httpx2 pops `Authorization` when a redirect leaves the origin, which is
        the behaviour a release download needs by design: that URL redirects to a
        CDN, and a client carrying the header through leaks the credential on the
        request path that runs most often.

        Asserted against the client rather than reimplemented, because the
        reimplementation is what this replaced.
        """
        client = httpx2.Client()
        original = client.build_request('GET', 'https://github.com/owner/repo/releases/download/v1/a.tar.gz')
        original.headers['Authorization'] = 'Bearer ghp_pretend'
        redirected = httpx2.Response(302, headers={'Location': 'https://objects.githubusercontent.com/x'}, request=original)

        following = client._build_redirect_request(original, redirected)

        assert 'authorization' not in following.headers

    def test_the_client_keeps_it_on_a_same_origin_redirect(self):
        client = httpx2.Client()
        original = client.build_request('GET', 'https://api.github.com/repos/owner/repo/releases/assets/1')
        original.headers['Authorization'] = 'Bearer ghp_pretend'
        redirected = httpx2.Response(302, headers={'Location': 'https://api.github.com/elsewhere'}, request=original)

        following = client._build_redirect_request(original, redirected)

        assert following.headers['Authorization'] == 'Bearer ghp_pretend'
