"""Tests for github_release.py

The checksum rules here are shared by the offline bundler and the shell
installer, so a divergence would mean a bundle verifying differently from a live
install. Every fallback below was earned by a real release.

Run with: pytest tests/install/test_github_release.py
"""

import github_release


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
