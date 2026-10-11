"""A product CLI's config template holds exactly what the CLI's own login writes.

goclilogin's login fills a missing config file with `api`, `issuer` and
`client_id`, one `key = "value"` line each, in that order, and nothing else. A
template of that shape makes a file a CLI wrote at login a rendering, so the
next apply overwrites it with this machine's values instead of refusing it as
somebody's file. A header comment added to one of these templates breaks that,
and nothing else would notice until a machine refused its target.
"""

from __future__ import annotations

import string

import pytest
import yaml

from dotfiles import paths
from dotfiles.symlinks import template


def login_config_templates() -> list[str]:
    register = yaml.safe_load((paths.REPO_ROOT / 'install' / 'flags.yml').read_text())
    (entry,) = (e for e in register['required'] if e['name'] == 'OAUTH_CLIENT_SUFFIX')
    return entry['consumers']


@pytest.mark.parametrize('consumer', login_config_templates())
def test_a_config_a_cli_wrote_at_login_before_the_values_were_set_is_adopted(consumer: str) -> None:
    source = paths.REPO_ROOT / consumer
    filled = string.Template(source.read_text()).substitute(HOMELAB_DOMAIN='example.com', OAUTH_CLIENT_SUFFIX='cli-host')
    keys = [line.split(' = ', 1)[0] for line in filled.splitlines()]
    assert keys == ['api', 'issuer', 'client_id']
    assert all(line.split(' = ', 1)[1].startswith('"') for line in filled.splitlines())
    assert template.is_rendering_of(source, filled)
