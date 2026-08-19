"""Append a content hash to every hand-written CSS and JS URL.

Material fingerprints its own bundle, so `assets/main.<hash>.min.css` changes
name whenever its bytes change. The files listed in `extra_css` and
`extra_javascript` do not, and the hub sits behind a CDN that caches CSS and JS
for four hours by default. An edit to `extra.css` therefore stayed invisible
for that long while the HTML around it updated on its own shorter rule.

Hashing the query makes a changed file a different URL, so it is fetched the
moment it changes and an unchanged one still caches.
"""

import hashlib
from pathlib import Path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def _busted(value: str, docs_dir: Path) -> str:
    if '://' in value or '?' in value:
        return value
    source = docs_dir / value
    if not source.is_file():
        return value
    return f'{value}?h={_digest(source)}'


def on_config(config):
    docs_dir = Path(config['docs_dir'])

    config['extra_css'] = [_busted(item, docs_dir) for item in config['extra_css']]

    for script in config['extra_javascript']:
        # MkDocs 1.6 wraps these in ExtraScriptValue; a plain string is still
        # accepted in the config and arrives unwrapped.
        if isinstance(script, str):
            continue
        script.path = _busted(script.path, docs_dir)

    config['extra_javascript'] = [_busted(item, docs_dir) if isinstance(item, str) else item for item in config['extra_javascript']]

    return config
