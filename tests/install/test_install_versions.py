"""The version `packages resolve` names for a Go tool, which is the one it asks the module proxy for."""

from typing import NoReturn

import httpx2
import pytest

from dotfiles import catalog
from dotfiles import github_release
from dotfiles import install_versions

PROXY = install_versions.GO_PROXY_URL


def gone(url: str, status: int) -> NoReturn:
    asked = httpx2.Request('GET', url)
    raise httpx2.HTTPStatusError(f'{status}', request=asked, response=httpx2.Response(status, request=asked))


def test_a_go_tool_resolves_to_the_highest_release_its_module_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    """The package path walks up to the module, a capital is escaped, and a pre-release is passed over."""
    answers: dict[str, bytes | int] = {
        f'{PROXY}/github.com/!owner/tool/cmd/tool/@v/list': 404,
        f'{PROXY}/github.com/!owner/tool/cmd/@v/list': 410,
        f'{PROXY}/github.com/!owner/tool/@v/list': b'v1.2.0\nv1.10.0-rc.1\nv1.9.3\n',
    }

    def proxy(url: str, accept: str | None = None) -> bytes:
        answer = answers.get(url, 404)
        return answer if isinstance(answer, bytes) else gone(url, answer)

    monkeypatch.setattr(github_release, 'request', proxy)
    entry = catalog.GoTool.from_mapping({'name': 'tool', 'package': 'github.com/Owner/tool/cmd/tool'})

    assert install_versions.version_of(entry) == '1.9.3'
