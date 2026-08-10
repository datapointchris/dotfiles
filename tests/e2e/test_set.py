"""One section installed over a base, which is the tier that was missing.

Between `test_container.py` (eight seconds, nothing installed) and
`test_machine.py` (ten minutes, everything installed) there was nothing, so every
question about *one installer* cost a whole machine. Three of today's four
failures lived in two sections, and finding them took two ten-minute runs whose
containers were then thrown away.

**A set does not declare its prerequisites, because the resolver already carries
them.** `registry.ToolchainProvider.needed_by` says the Rust toolchain is wanted
when `cargo_packages` resolve, so `--source cargo_packages` over a bare base
installs rustup and then the tools. The only thing a set needs supplied is the
part no section declares: an OS with a package manager, curl, git and unzip on
it, which is what the base image is.

What this tier cannot answer is anything about *order* — whether the symlink pass
ran before tpm read the config it deploys is a question about a whole machine, and
`test_machine.py` keeps it. Sets are about whether a section installs at all.
"""

from __future__ import annotations

import pytest
from harness import Machine

pytestmark = pytest.mark.docker

SECTIONS = (
    'github_releases',
    'custom_installers',
    'cargo_packages',
    'go_tools',
    'uv_tools',
    'git_uv_tools',
    'npm_globals',
)
"""The sections worth their own test, which is every one that fetches something.

`system_packages` is not here: it *is* the base, so a test of it over the base
would assert that a converged machine is converged. The rest each reach a
different upstream in a different way, which is the whole reason a section-level
failure is worth isolating.
"""


def apply_section(machine: Machine, section: str) -> tuple[int, str]:
    """Install one section, and hand back what the machine said about it."""
    result = machine.exec(f'cd {machine.environment.home}/dotfiles && uv run dotfiles packages apply --source {section} 2>&1')
    return result.returncode, result.stdout


@pytest.mark.parametrize('section', SECTIONS)
def test_a_section_installs_over_the_base(over_base: Machine, section: str) -> None:
    """The assertion is the exit code, not the prose.

    `dotfiles apply` exits non-zero when a provider reports a failure, and the
    report names which — so a red result here says which tool, in a minute, on a
    container that is still there to ask.
    """
    code, output = apply_section(over_base, section)

    assert code == 0, f'{section} did not converge:\n{output[-3000:]}'


def test_a_release_that_nests_its_binary_still_lands(over_base: Machine) -> None:
    """glow shipped a flat tarball until v2 and nests it now, which no other test
    can see: `test_release_urls.py` checks that a release publishes the asset a
    function names, never what is inside it."""
    code, output = apply_section(over_base, 'github_releases')

    assert code == 0, output[-2000:]
    assert over_base.succeeds('glow --version')


def test_a_zip_distributed_tool_comes_out_executable(over_base: Machine) -> None:
    """`zipfile.extractall` drops permissions, so awscli installed, symlinked, and
    answered `Permission denied` — which `shutil.which` reports as *not on PATH*."""
    code, output = apply_section(over_base, 'custom_installers')

    assert code == 0, output[-2000:]
    assert over_base.succeeds('aws --version')


def test_a_download_from_a_third_party_host_is_not_sent_a_github_token(over_base: Machine) -> None:
    """mount-s3 comes from an S3 bucket, and S3 answers a bearer token it does not
    recognise with a 400. The credential was going to every host this repo fetches
    from, so an authenticated machine could not install it at all."""
    code, output = apply_section(over_base, 'custom_installers')

    assert code == 0, output[-2000:]
    assert over_base.succeeds('mount-s3 --version')


def test_a_private_repo_tool_installs_when_git_can_authenticate(over_base: Machine) -> None:
    """A `git_uv_tools` entry pins to a release tag, so uv runs `git fetch`. Without
    a credential helper that prompts for a username, finds prompts disabled, and
    fails as though the installer were broken."""
    code, output = apply_section(over_base, 'git_uv_tools')

    assert code == 0, output[-2000:]
