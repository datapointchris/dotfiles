#!/usr/bin/python3
"""Pick an AWS profile, and tell the shell which one.

Everything except the export: reads ~/.aws/config and ~/.aws/credentials,
resolves each profile's account and identity through STS, draws the menu, and
takes the choice. The result goes to stdout for the sourced `aws-profiles` shim
to export, because setting a variable in an interactive shell is the one thing a
subprocess cannot do.

    aws_profiles.py [--refresh]      menu on stderr, decision on stdout

Decision line, tab-separated:
    set<TAB><profile><TAB><region>
    clear
    (nothing, when the choice was invalid or empty)

Name an account by adding `account_label = <name>` to any profile in
~/.aws/config; every profile in that account picks the label up. AWS account
aliases are not used because reading one needs iam:ListAccountAliases, which a
least-privilege user does not have.

Stdlib-only, runs under the system python3.
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CONFIG_PATH = Path(os.environ.get('AWS_CONFIG_FILE', Path.home() / '.aws' / 'config'))
CREDENTIALS_PATH = Path(os.environ.get('AWS_SHARED_CREDENTIALS_FILE', Path.home() / '.aws' / 'credentials'))
CACHE_PATH = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'aws-profiles' / 'identities.json'

# STS calls are independent and each costs a round trip, so the wait is the
# slowest one rather than their sum.
RESOLVE_WORKERS = 8

UNREACHABLE = 'unreachable'
UNKNOWN_ACCOUNT = '?'


def read_ini(path: Path) -> configparser.ConfigParser:
    """strict=False because an ~/.aws/config assembled by several tools over the
    years picks up duplicate keys, and refusing to read it at all is worse than
    taking the last value.
    """
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    if path.is_file():
        parser.read(path)
    return parser


def profile_settings() -> dict[str, dict[str, str]]:
    """Every profile's settings, keyed by profile name.

    Config sections are `[profile name]` except `[default]`, which is bare.
    Credentials sections are always bare, and hold no settings worth reading —
    they are here so a credentials-only profile still appears in the menu.
    """
    settings: dict[str, dict[str, str]] = {}

    config = read_ini(CONFIG_PATH)
    for section in config.sections():
        name = section[len('profile ') :] if section.startswith('profile ') else section
        settings[name] = dict(config[section])

    # Config first, so role profiles — which live only in ~/.aws/config — keep
    # their place, and a credentials-only profile is appended rather than
    # overwriting settings.
    for section in read_ini(CREDENTIALS_PATH).sections():
        settings.setdefault(section, {})

    return settings


def region_for(profile: str, settings: dict[str, dict[str, str]]) -> str:
    """AWS does not inherit region from [default] for a named profile, so a role
    profile without its own leaves every command failing on a missing region.
    Fall back through the profile the role is assumed via, then [default].
    """
    own = settings.get(profile, {})
    if own.get('region'):
        return own['region']

    source = own.get('source_profile')
    if source and settings.get(source, {}).get('region'):
        return settings[source]['region']

    return settings.get('default', {}).get('region', '')


def short_identity(arn: str) -> str:
    """arn:aws:iam::123:user/chris.birch        -> user/chris.birch
    arn:aws:sts::123:assumed-role/Admin/sess -> role/Admin
    """
    trailing = arn.rsplit(':', 1)[-1]
    if trailing.startswith('assumed-role/'):
        return 'role/' + trailing[len('assumed-role/') :].split('/')[0]
    return trailing


def resolve_identity(profile: str) -> dict[str, str]:
    result = subprocess.run(
        ['aws', 'sts', 'get-caller-identity', '--profile', profile, '--output', 'json'],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return {'account': UNKNOWN_ACCOUNT, 'identity': UNREACHABLE}

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {'account': UNKNOWN_ACCOUNT, 'identity': UNREACHABLE}

    return {'account': payload.get('Account', UNKNOWN_ACCOUNT), 'identity': short_identity(payload.get('Arn', ''))}


def read_cache() -> dict[str, dict[str, str]]:
    if not CACHE_PATH.is_file():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except json.JSONDecodeError:
        return {}


def write_cache(cache: dict[str, dict[str, str]]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True) + '\n')


def refresh_cache(profiles: list[str]) -> dict[str, dict[str, str]]:
    with ThreadPoolExecutor(max_workers=RESOLVE_WORKERS) as pool:
        pending = {profile: pool.submit(resolve_identity, profile) for profile in profiles}
    cache = {profile: future.result() for profile, future in pending.items()}
    write_cache(cache)
    return cache


def account_labels(settings: dict[str, dict[str, str]], cache: dict[str, dict[str, str]]) -> dict[str, str]:
    """Account number to label, from whichever profiles carry `account_label`.

    Labelling the account rather than the profile is what lets one label cover
    every profile that reaches the same account.
    """
    labels = {}
    for profile, values in settings.items():
        label = values.get('account_label')
        if not label:
            continue
        account = cache.get(profile, {}).get('account', UNKNOWN_ACCOUNT)
        if account != UNKNOWN_ACCOUNT:
            labels.setdefault(account, label)
    return labels


def build_rows(profiles: list[str], settings: dict[str, dict[str, str]], cache: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    labels = account_labels(settings, cache)
    rows = []
    for number, profile in enumerate(profiles, start=1):
        entry = cache.get(profile, {})
        account = entry.get('account', UNKNOWN_ACCOUNT)
        rows.append(
            {
                'number': str(number),
                'profile': profile,
                'account': account,
                'label': labels.get(account, ''),
                'identity': entry.get('identity', 'unknown'),
                'region': region_for(profile, settings),
                'source_profile': settings.get(profile, {}).get('source_profile', ''),
            }
        )
    return rows


def render_menu(rows: list[dict[str, str]], current_profile: str) -> str:
    """The menu, as one string. Columns are sized from the widest value in each,
    which is why this builds the whole table before printing any of it.
    """
    width = {
        'profile': max([len('PROFILE')] + [len(row['profile']) for row in rows]),
        'account': max([len('ACCOUNT')] + [len(row['account']) for row in rows]),
        'identity': max([len('IDENTITY')] + [len(row['identity']) for row in rows]),
        'label': max([0] + [len(row['label']) for row in rows]),
    }

    lines = ['', '0) Clear current profile', '']

    header = f'    {"PROFILE":<{width["profile"]}}  {"ACCOUNT":<{width["account"]}}  '
    if width['label']:
        header += f'{"LABEL":<{width["label"]}}  '
    header += f'{"IDENTITY":<{width["identity"]}}  REGION'
    lines.append(header)

    for row in rows:
        marker = '*' if row['profile'] == current_profile else ' '
        line = f'{marker}{row["number"]}) {row["profile"]:<{width["profile"]}}  {row["account"]:<{width["account"]}}  '
        if width['label']:
            line += f'{row["label"]:<{width["label"]}}  '
        line += f'{row["identity"]:<{width["identity"]}}  '
        if row['source_profile']:
            line += f'{row["region"]:<9}  ← assumed via {row["source_profile"]}'
        else:
            line += row['region']
        lines.append(line.rstrip())

    return '\n'.join(lines)


def confirm_selection(profile: str, cache: dict[str, dict[str, str]]) -> None:
    """Check the chosen profile for real and rewrite its cache line.

    A rotated key shows as unreachable next time instead of keeping a stale row
    that says it still works.
    """
    entry = resolve_identity(profile)
    cache[profile] = entry
    write_cache(cache)

    if entry['identity'] == UNREACHABLE:
        print(f'{profile} is unreachable — check its credentials', file=sys.stderr)
    else:
        print(f'account {entry["account"]}  {entry["identity"]}', file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='aws_profiles.py', description=__doc__.splitlines()[0])
    parser.add_argument('--refresh', action='store_true', help='re-resolve every account before listing')
    args = parser.parse_args(argv)

    settings = profile_settings()
    profiles = list(settings)
    if not profiles:
        print(f'No profiles found in {CONFIG_PATH} or {CREDENTIALS_PATH}', file=sys.stderr)
        return 1

    cache = read_cache()
    if args.refresh or any(profile not in cache for profile in profiles):
        print('Resolving AWS accounts...', file=sys.stderr)
        cache = refresh_cache(profiles)

    rows = build_rows(profiles, settings, cache)
    print(render_menu(rows, os.environ.get('AWS_PROFILE', '')), file=sys.stderr)
    print('\nSelect option number and press [ENTER]: ', file=sys.stderr)

    try:
        choice = input().strip()
    except (EOFError, KeyboardInterrupt):
        print('', file=sys.stderr)
        return 1

    if choice == '0':
        print('clear')
        return 0

    if not choice.isdigit() or not 1 <= int(choice) <= len(rows):
        print(f'No profile at option {choice}.', file=sys.stderr)
        return 1

    row = rows[int(choice) - 1]
    confirm_selection(row['profile'], cache)
    print(f'set\t{row["profile"]}\t{row["region"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
