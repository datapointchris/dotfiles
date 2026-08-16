"""A chord AeroSpace binds never reaches tmux.

AeroSpace is a macOS window manager, so it takes a key before the terminal below
it ever sees one. tmux's root-table bindings — the ones reachable with no prefix,
which is every `-n` binding — are therefore live only for as long as AeroSpace
stays silent about the same chord. Nothing errors when the two agree on a key:
the tmux binding simply stops happening.

Held by a comment before this. `tmux.conf` pointed at two commented lines in
`aerospace.toml` and asked the reader not to uncomment them, which made the
comment correct and left dead configuration in place to keep it that way.

Only `[mode.main.binding]` is read. The resize and service modes are entered
deliberately and left again, so a chord bound there is not competing for a key
someone is typing into a shell.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TMUX_CONF = REPO / 'configs' / 'common' / '.config' / 'tmux' / 'tmux.conf'
AEROSPACE_TOML = REPO / 'configs' / 'display' / 'aqua' / '.config' / 'aerospace' / 'aerospace.toml'

ROOT_BINDING = re.compile(r"""^\s*bind(?:-key)?\b.*?\s-n\s+(?:"([^"]+)"|'([^']+)'|(\S+))""")
"""A tmux binding in the root table. `-N "..."` carries a quoted description and
comes first, so the key is matched off `-n` rather than off the line's last word.
Both quote styles appear in the file and a chord holding a backslash needs one."""

TMUX_MODIFIERS = {'M': 'alt', 'C': 'ctrl', 'S': 'shift'}

SHIFTED = {'{': '[', '}': ']', '<': ',', '>': '.', ':': ';', '"': "'", '|': '\\', '?': '/', '_': '-', '+': '=', '~': '`'}
"""What a US keyboard produces with shift held. tmux spells the shifted glyph and
AeroSpace spells the modifier, so one of them has to be decomposed to compare."""

AEROSPACE_NAMES = {
    'comma': ',',
    'period': '.',
    'semicolon': ';',
    'quote': "'",
    'backslash': '\\',
    'slash': '/',
    'minus': '-',
    'equal': '=',
    'backtick': '`',
    'leftSquareBracket': '[',
    'rightSquareBracket': ']',
}

NAMED_KEYS = frozenset({'tab', 'enter', 'space', 'esc', 'backspace', 'delete', 'up', 'down', 'left', 'right', 'home', 'end'})

MODIFIER_WORDS = frozenset({'alt', 'ctrl', 'shift', 'cmd'})

Chord = tuple[frozenset[str], str]


def canonical(modifiers: frozenset[str], base: str, *, source: str) -> Chord:
    """One spelling for a chord, whichever config wrote it.

    Raises rather than skipping an unrecognised key. A translation table that
    silently drops what it does not know reports agreement it never checked, and
    the collision this file exists to catch is itself silent.
    """
    if len(base) == 1 and base.isalpha() and base.isupper():
        return frozenset(modifiers | {'shift'}), base.lower()
    if base in SHIFTED:
        return frozenset(modifiers | {'shift'}), SHIFTED[base]
    if len(base) == 1 and (base.isalnum() or base in set(SHIFTED.values())):
        return frozenset(modifiers), base.lower()
    if base.lower() in NAMED_KEYS:
        return frozenset(modifiers), base.lower()
    raise ValueError(f'{source} names a key this comparison cannot spell: {base!r}')


def tmux_chord(key: str) -> Chord:
    match = re.fullmatch(r'((?:[MCS]-)*)(.+)', key)
    if match is None:
        raise ValueError(f'tmux.conf binds a key this comparison cannot parse: {key!r}')
    prefix, base = match.groups()
    modifiers = frozenset(TMUX_MODIFIERS[letter] for letter in prefix.split('-') if letter)
    return canonical(modifiers, base, source='tmux.conf')


def aerospace_chord(key: str) -> Chord:
    tokens = key.split('-')
    modifiers = frozenset(token for token in tokens if token in MODIFIER_WORDS)
    remainder = [token for token in tokens if token not in MODIFIER_WORDS]
    if len(remainder) != 1:
        raise ValueError(f'aerospace.toml binds a key this comparison cannot parse: {key!r}')
    base = AEROSPACE_NAMES.get(remainder[0], remainder[0])
    return canonical(modifiers, base, source='aerospace.toml')


def tmux_root_bindings() -> dict[Chord, str]:
    """Every chord tmux claims without a prefix, keyed by the canonical chord."""
    found = {}
    for line in TMUX_CONF.read_text(encoding='utf-8').splitlines():
        if line.lstrip().startswith('#'):
            continue
        match = ROOT_BINDING.match(line)
        if match is None:
            continue
        key = match.group(1) or match.group(2) or match.group(3)
        found[tmux_chord(key)] = key
    return found


def aerospace_main_bindings() -> dict[Chord, str]:
    """Every chord AeroSpace claims in its ordinary mode.

    tomllib does the commenting-out for us: a commented line is not a key, so
    nothing here has to recognise a `#`."""
    declaration = tomllib.loads(AEROSPACE_TOML.read_text(encoding='utf-8'))
    bindings = declaration['mode']['main']['binding']
    return {aerospace_chord(key): key for key in bindings}


def test_tmux_binds_something_in_the_root_table() -> None:
    """Guards the two tests below, which pass on an empty set for either reason —
    tmux really binding nothing, or the regex having stopped matching."""
    assert len(tmux_root_bindings()) >= 5


def test_aerospace_binds_something_in_main_mode() -> None:
    assert len(aerospace_main_bindings()) >= 5


def test_no_chord_is_claimed_by_both() -> None:
    """AeroSpace wins in silence, so the tmux binding is what disappears."""
    tmux = tmux_root_bindings()
    aerospace = aerospace_main_bindings()

    collisions = sorted((tmux[chord], aerospace[chord]) for chord in tmux.keys() & aerospace.keys())

    assert collisions == [], 'AeroSpace takes these before tmux sees them: ' + ', '.join(f'{a} shadows tmux {t}' for t, a in collisions)


@pytest.mark.parametrize(
    ('key', 'expected'),
    [
        ('M-,', (frozenset({'alt'}), ',')),
        ('M-{', (frozenset({'alt', 'shift'}), '[')),
        ('M-n', (frozenset({'alt'}), 'n')),
        ('C-M-h', (frozenset({'ctrl', 'alt'}), 'h')),
    ],
)
def test_a_tmux_key_normalises_to_the_chord_aerospace_would_spell(key: str, expected: Chord) -> None:
    assert tmux_chord(key) == expected


@pytest.mark.parametrize(
    ('key', 'expected'),
    [
        ('alt-comma', (frozenset({'alt'}), ',')),
        ('alt-shift-leftSquareBracket', (frozenset({'alt', 'shift'}), '[')),
        ('alt-n', (frozenset({'alt'}), 'n')),
        ('ctrl-shift-alt-h', (frozenset({'ctrl', 'shift', 'alt'}), 'h')),
    ],
)
def test_an_aerospace_key_normalises_to_the_chord_tmux_would_spell(key: str, expected: Chord) -> None:
    assert aerospace_chord(key) == expected


def test_an_unspellable_key_fails_rather_than_being_skipped() -> None:
    with pytest.raises(ValueError, match='cannot spell'):
        aerospace_chord('alt-f13')
