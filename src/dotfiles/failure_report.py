"""Installer failure records, and the report rendered from them.

An installer that fails calls `record`, which appends one JSON object to the
file named by $FAILURE_RECORDS. When the installer exits, `apply.run_installer`
renders those records plus the installer's console output into the entries a
person reads in $FAILURES_LOG.

    python -m dotfiles.failure_report record <tool> <url> [version] [reason] [detail]
    python -m dotfiles.failure_report render --records F --console F --script S --tool T --exit N

Records used to be FAILURE_TOOL='x' lines on stderr, parsed back out with grep,
cut, sed and awk. Every part of that was a workaround for stderr carrying two
kinds of thing at once: the wrapper had to filter markers out of what it showed,
markers had to be stripped from captured output so it could not forge a record,
and splitting several failures apart needed an awk state machine. A file of JSON
objects has none of those problems, and the path is in an environment variable
rather than a file descriptor, so it can be printed and read.

Reached from bash as `dotfiles_python -m dotfiles.failure_report`, which
`install/common/lib/python.sh` defines as the CLI's own `sys.executable` and
documents as never the system interpreter. It carried a stdlib-only rule for that
system interpreter until 2026-08-08, by which time nothing had invoked it that way
for months.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# A TLS, proxy or "too many errors" failure states its cause on the last lines,
# under however much progress preceded it.
DETAIL_MAX_LINES = int(os.environ.get('FAILURE_DETAIL_MAX_LINES', '25'))

# What installers pass when the failure has no download behind it. Printing it
# back reads as a corrupted field.
UNKNOWN_URL = 'unknown'

NO_OUTPUT_NOTE = '(no error output captured — the installer printed nothing)'


def tail(text: str, limit: int = DETAIL_MAX_LINES) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    return '\n'.join(lines[-limit:])


def read_records(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    records = []
    for line in path.read_text().splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def render_entry(record: dict, script: str, tool: str, action: str, fallback_detail: str = '') -> str:
    """One report entry. Plain text: this file is read later, and often
    elsewhere, so escape sequences in it are noise. The summary heading that
    introduces the whole report is still drawn by formatting.sh.
    """
    failure_tool = record.get('tool') or tool
    url = record.get('url', '')
    version = record.get('version', '')
    reason = record.get('reason', '')
    detail = record.get('detail') or fallback_detail

    heading = f'{failure_tool} - {action.capitalize()} Failed'
    lines = ['', '', f'❌ {heading}', '─' * (len(heading) + 15), f'Installer: {Path(script).name}']

    if reason:
        lines.append(f'Error: {reason}')
    if url and url != UNKNOWN_URL:
        lines.append(f'Download URL: {url}')
    if version and version != 'latest':
        lines.append(f'Version: {version}')

    lines.append('')
    # Silence is a finding: it says the installer wrote nothing, not that the
    # report lost it. Without this a reader retries the install to find out which.
    lines.append(detail if detail else NO_OUTPUT_NOTE)
    lines.append('')
    return '\n'.join(lines)


def render_report(records: list[dict], console_output: str, script: str, tool: str, exit_code: int, action: str) -> str:
    unattributed = tail(console_output)

    if not records:
        # An installer that dies before it can report emits nothing. Name the
        # exit status rather than writing a blank entry — one that reached the
        # report as a bare heading was indistinguishable from the report itself
        # having dropped the failure.
        silent = {'reason': f'Installer exited {exit_code} without reporting a failure'}
        return render_entry(silent, script, tool, action, unattributed)

    # Unattributed output can only be assigned to a failure when there is exactly
    # one; with several, it is impossible to say which tool produced it.
    fallback = unattributed if len(records) == 1 else ''
    return ''.join(render_entry(record, script, tool, action, fallback) for record in records)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='failure_report.py', description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest='command', required=True)

    record = commands.add_parser('record', help='append a failure record for the wrapper to render')
    record.add_argument('tool', help='the tool that failed')
    record.add_argument('url', help='where it is downloaded from, or "unknown"')
    record.add_argument('version', nargs='?', default='unknown', help='the version attempted')
    record.add_argument('reason', nargs='?', default='Installation failed', help='which step failed')
    record.add_argument('detail', nargs='?', default='', help='verbatim output of the command that failed')

    render = commands.add_parser('render', help='append report entries for one installer run')
    render.add_argument('--records', required=True, help='the JSONL file the installer wrote')
    render.add_argument('--console', required=True, help="the installer's captured output")
    render.add_argument('--script', required=True, help='the installer script that ran')
    render.add_argument('--tool', required=True, help='the tool name the wrapper was invoked with')
    render.add_argument('--exit', type=int, required=True, dest='exit_code', help='the installer exit status')
    render.add_argument('--action', default='installation', help='"installation" or "update"')
    render.add_argument('--log', required=True, help='the report file to append to')

    args = parser.parse_args(argv)

    if args.command == 'record':
        entry = {
            'tool': args.tool,
            'url': args.url,
            'version': args.version or 'unknown',
            'reason': args.reason,
            'detail': tail(args.detail),
        }
        records_path = os.environ.get('FAILURE_RECORDS')
        if not records_path:
            # Run standalone there is nothing collecting records, so say it
            # plainly rather than writing machine text nobody will parse.
            print(f'[ERROR] ✗ {entry["tool"]}: {entry["reason"]}', file=sys.stderr)
            if entry['detail']:
                print(entry['detail'], file=sys.stderr)
            return 0
        with Path(records_path).open('a') as handle:
            handle.write(json.dumps(entry) + '\n')
        return 0

    console = Path(args.console)
    report = render_report(
        read_records(Path(args.records)),
        console.read_text() if console.is_file() else '',
        args.script,
        args.tool,
        args.exit_code,
        args.action,
    )
    with Path(args.log).open('a') as handle:
        handle.write(report)
    return 0


if __name__ == '__main__':
    sys.exit(main())
