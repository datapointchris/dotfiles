"""Build the Windows tool bundle for a Git Bash machine behind a firewall.

The WSL counterpart of src/dotfiles/create_bundle.py: run it where GitHub is
reachable, move the tarball across, then `task windows:offline`.

    python -m dotfiles.windows_bundle <output.tar.gz> [--print-path]

The archive holds a flat set of .exe files plus versions.txt, which is what
`dotfiles windows apply --offline` expects.

Checksums are verified here for the same reason they are in the Linux bundler:
the machine this is built for cannot reach the release API, so it cannot learn
which asset holds a checksum, and verification has to happen where it can. The
shell version this replaced did not verify at all.

Reached as `dotfiles windows create`, and still runnable as `python -m` for a
build on a machine with no installed CLI. It carried a stdlib-only rule for a
system interpreter until 2026-08-08; see src/dotfiles/create_bundle.py for why
that rule named nobody.
"""

from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

from dotfiles import github_release
from dotfiles.windows import TOOLS
from dotfiles.windows import Tool

log = logging.getLogger('windows-bundle')


class BundleError(Exception):
    """A failure that should end the build with a message rather than a traceback."""


def version_num(tag: str) -> str:
    """The tag from its first digit on: v0.9.8 and 0.9.8 both give 0.9.8."""
    match = re.search(r'[0-9].*', tag)
    return match.group(0) if match else tag


def expand_asset(pattern: str, tag: str) -> str:
    return pattern.replace('{version}', tag).replace('{version_num}', version_num(tag))


def extract_exe(archive: Path, exe_name: str, destination: Path) -> None:
    """Pull one .exe out of a release zip.

    Searched rather than taken from a known path: these repos disagree about
    whether the binary sits at the archive root or under a versioned directory.
    """
    with tempfile.TemporaryDirectory() as workspace:
        extracted = Path(workspace)
        with zipfile.ZipFile(archive) as zip_file:
            zip_file.extractall(extracted)  # noqa: S202

        found = next((path for path in extracted.rglob(exe_name) if path.is_file()), None)
        if found is None:
            raise BundleError(f'{exe_name} not found inside {archive.name}')
        shutil.move(str(found), destination)


def fetch_tool(tool: Tool, staging: Path) -> str:
    """Download one tool into the staging directory and return its tag."""
    tag = github_release.latest_version(tool.repo)
    if not tag:
        raise BundleError(f'Could not fetch latest release tag for {tool.repo}')

    asset = expand_asset(tool.asset, tag)
    url = f'https://github.com/{tool.repo}/releases/download/{tag}/{asset}'
    log.info('  %s (%s)', tool.name, tag)

    with tempfile.TemporaryDirectory() as workspace:
        download = Path(workspace) / asset
        if not github_release.download_asset(url, download, tool.repo, tag, asset):
            raise BundleError(f'Failed to download {url}')

        outcome = github_release.verify_release_checksum(download, asset, tool.repo, tag)
        if outcome is github_release.Verification.FAILED:
            raise BundleError(f'Checksum verification failed for {tool.name}')
        if outcome is github_release.Verification.UNPUBLISHED:
            log.warning('    %s publishes no checksum for %s', tool.repo, asset)

        if asset.endswith('.exe'):
            shutil.move(str(download), staging / tool.exe)
        else:
            extract_exe(download, tool.exe, staging / tool.exe)

    return tag


def build(output: Path) -> Path:
    """Build the bundle and return the archive's path."""
    if output.suffix not in ('.gz', '.tgz'):
        output = output.with_name(output.name + '.tar.gz')
    output.parent.mkdir(parents=True, exist_ok=True)

    log.info('Building Windows tool bundle -> %s', output)

    with tempfile.TemporaryDirectory() as workspace:
        staging = Path(workspace)
        versions = [f'{tool.name} {fetch_tool(tool, staging)}' for tool in TOOLS]
        (staging / 'versions.txt').write_text('\n'.join(versions) + '\n')

        with tarfile.open(output, 'w:gz') as tar:
            for path in sorted(staging.iterdir()):
                tar.add(path, arcname=path.name)

    log.info('Bundle complete: %d binaries', len(TOOLS))
    log.info('  Archive: %s', output)
    log.info('  Move it to the target machine, then run:')
    log.info('    task windows:offline -- %s', output)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='windows_bundle.py', description=__doc__.splitlines()[0])
    parser.add_argument('output', help='where to write the bundle (.tar.gz is appended if missing)')
    parser.add_argument('--print-path', action='store_true', help="print the finished archive's path on stdout")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stderr)

    try:
        archive = build(Path(args.output))
    except BundleError as error:
        log.error('%s', error)
        return 1

    if args.print_path:
        print(archive)
    return 0


if __name__ == '__main__':
    sys.exit(main())
