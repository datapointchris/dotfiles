"""One fake remote, shared by every test that drives a transport.

A real executable backed by a real directory, refusing what a real remote
refuses: listing a directory that is not there, downloading a name that does not
exist, uploading into a path nobody created. A fake that accepted everything
would assert the caller's mental model rather than challenge it — and the
constraint it exists for is the one that costs an artefact, an upload the
transport reroutes somewhere no `list` will ever find it.

One module rather than a copy per suite, because a second fake drifts from the
first and the test that would catch the drift is the one using the other copy.
That is the same failure `standards/testing.md` § "A fake enforces the service's
constraints" describes about replaying responses.

A plain module and not a `conftest.py`: two conftests are both the module
`conftest` to an importer, so `from conftest import ...` resolves to whichever
one the tool looked at first. `tests/shell/shells.py` is the same shape.
"""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path

RELAY = """#!{python}
import pathlib, shutil, sys

ROOT = pathlib.Path({root!r})


def resolve(remote):
    return ROOT / remote.strip("/")


def main(argv):
    verb, rest = argv[0], argv[1:]
    if verb == "probe":
        # Answers whenever the server is there, whatever is or is not on it —
        # which is the property a probe has to have. A root that does not exist
        # yet is the ordinary state of a fresh remote.
        return 0 if ROOT.is_dir() else 4
    if verb == "list":
        directory = resolve(rest[0])
        if not directory.is_dir():
            print(f"{{rest[0]}} is not a directory", file=sys.stderr)
            return 4
        for entry in sorted(directory.iterdir()):
            print(entry.name)
        return 0
    if verb == "mkdir":
        resolve(rest[0]).mkdir(parents=True, exist_ok=True)
        return 0
    if verb == "upload":
        local, directory = pathlib.Path(rest[0]), resolve(rest[1])
        if not directory.is_dir():
            print(f"{{rest[1]}} is not a directory", file=sys.stderr)
            return 4
        shutil.copy2(local, directory / local.name)
        return 0
    if verb == "download":
        source, local = resolve(rest[0]), pathlib.Path(rest[1])
        if not source.is_file():
            print(f"{{rest[0]}} is not a file", file=sys.stderr)
            return 4
        shutil.copy2(source, local)
        return 0
    if verb == "delete":
        target = resolve(rest[0])
        if not target.exists():
            print(f"{{rest[0]}} is not there", file=sys.stderr)
            return 4
        target.unlink()
        return 0
    print(f"no such verb {{verb}}", file=sys.stderr)
    return 2


sys.exit(main(sys.argv[1:]))
"""

SPY = """#!{python}
import json, pathlib, sys

pathlib.Path({record!r}).open("a").write(json.dumps(sys.argv[1:]) + "\\n")
sys.exit({code})
"""

TABLE = """
[remote]
root = "{root}"
{extra}
[remote.transport]
program = "{program}"
probe = ["probe"]
list = ["list", "{{dir}}"]
upload = ["upload", "{{local}}", "{{dir}}"]
download = ["download", "{{remote}}", "{{local}}"]
mkdir = ["mkdir", "{{dir}}"]
delete = ["delete", "{{remote}}"]
"""
"""A complete table, including both optional operations.

Everything a real machine would declare, so a test that needs `mkdir` or
`delete` does not have to assemble its own — and so the shape a reader copies out
of the suite is the shape that works. `tests/install/test_remote.py` writes
narrower tables deliberately, to assert what each omission costs.
"""


def executable(directory: Path, name: str, script: str) -> Path:
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


def install_relay(bin_dir: Path, server: Path, name: str = 'relay') -> Path:
    """Put the fake transport on PATH, serving one directory as the remote."""
    server.mkdir(parents=True, exist_ok=True)
    return executable(bin_dir, name, RELAY.format(python=sys.executable, root=str(server)))


def install_spy(bin_dir: Path, record: Path, *, name: str = 'spy', code: int = 0) -> Path:
    """A transport that records the argv it was handed and does nothing else.

    The only question a fake cannot answer: whether the argv the caller *built* is
    the one the transport was meant to receive. A successful upload through the
    fake is satisfied by two different correct-looking commands.
    """
    return executable(bin_dir, name, SPY.format(python=sys.executable, record=str(record), code=code))


def recorded(record: Path) -> list[list[str]]:
    return [json.loads(line) for line in record.read_text().splitlines()] if record.exists() else []


def declare(config_home: Path, *, program: str = 'relay', root: str = '/artefacts', extra: str = '') -> Path:
    """Write a real config.toml where `settings.config_file()` will look for it.

    `extra` goes *inside* `[remote]` rather than after the whole table, because
    TOML sections are positional: a key appended at the end belongs to
    `[remote.transport]`, where nothing reads it. Getting that wrong here is how a
    test asserting an automatic path passes against a machine that never turned
    it on.
    """
    written = config_home / 'dotfiles'
    written.mkdir(parents=True, exist_ok=True)
    path = written / 'config.toml'
    path.write_text(TABLE.format(program=program, root=root, extra=extra))
    return path
