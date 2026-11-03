"""`persona-review`: put a reviewer persona in front of a subject, for a machine and operating system.

`list` and `matrix` read the catalog, `run` calls a model, and `runs` and `show` read stored runs
without one. `run --mock` does everything a real run does except the call, writing the persona's
canned report instead, so a change to the catalog, prompts or storage is exercised for no tokens.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from typing import Any

from dotfiles.persona_review import matrix
from dotfiles.persona_review import runs
from dotfiles.persona_review.matrix import CatalogError

SEVERITIES = ('critical', 'high', 'medium', 'low', 'informational')
TOKEN_LABELS = {
    'input_tokens': 'uncached input',
    'cache_creation_input_tokens': 'cache write',
    'cache_read_input_tokens': 'cache read',
    'output_tokens': 'output',
}


def emit(payload: Any) -> None:
    print(json.dumps(payload, indent=2))


def tokens_line(tokens: dict[str, int]) -> str:
    return ' · '.join(f'{label} {tokens.get(kind, 0):,}' for kind, label in TOKEN_LABELS.items())


def severity_counts(report: dict[str, Any] | None) -> str:
    counted = Counter(finding.get('severity') for finding in (report or {}).get('findings') or [])
    return ' · '.join(f'{counted[level]} {level}' for level in SEVERITIES if counted[level]) or 'no findings'


def list_catalog(args: argparse.Namespace) -> int:
    catalog = matrix.load()
    listed = {axis: {name: entry.text('title') for name, entry in values.items()} for axis, values in catalog.axes.items()}
    listed['scenario'] = {name: ' × '.join(str(raw.get(axis)) for axis in matrix.AXES) for name, raw in catalog.scenarios.items()}
    problems = catalog.problems()
    if args.json:
        emit({'axes': listed, 'problems': problems})
    else:
        for axis, values in listed.items():
            print(axis.replace('_', ' '))
            for name, title in values.items():
                print(f'  {name:<32} {title}')
        for problem in problems:
            print(f'problem: {problem}', file=sys.stderr)
    return 1 if problems else 0


def show_matrix(args: argparse.Namespace) -> int:
    catalog = matrix.load()
    named = {tuple(str(raw.get(axis)) for axis in matrix.AXES): name for name, raw in catalog.scenarios.items()}
    points: list[dict[str, str | None]] = [
        {**dict(zip(matrix.AXES, point, strict=True)), 'scenario': named.get(point)} for point in catalog.combinations()
    ]
    if args.json:
        emit(points)
        return 0
    print(f'{"persona":<32} {"machine":<18} {"operating system":<24} {"subject":<12} scenario')
    for point in points:
        axes = f'{point["persona"]:<32} {point["machine"]:<18} {point["operating_system"]:<24} {point["subject"]:<12}'
        print(f'{axes} {point["scenario"] or ""}')
    return 0


def run(args: argparse.Namespace) -> int:
    catalog = matrix.load()
    axes = (args.persona, args.machine, args.operating_system, args.subject)
    try:
        if args.scenario and any(axes):
            raise CatalogError('name a scenario or all four axes, not both')
        if args.scenario:
            scenario = catalog.scenario(args.scenario)
        elif all(axes):
            scenario = catalog.compose(*axes, submission=args.submission or '')
        else:
            raise CatalogError('name a scenario, or --persona, --machine, --os and --subject together')
    except CatalogError as exc:
        print(f'persona-review: {exc}', file=sys.stderr)
        return 2
    max_turns = args.max_turns or int(scenario.persona.fields.get('max_turns') or 50)
    effort = args.effort or scenario.effort
    record = runs.start(
        scenario, model=args.model, effort=effort, max_turns=max_turns, timeout=args.timeout, only=args.only, mock=args.mock
    )
    if args.json:
        emit(record)
    else:
        render(record)
    return 1 if record['failure'] else 0


def list_runs(args: argparse.Namespace) -> int:
    found = runs.records()[: args.limit]
    if args.json:
        emit(found)
        return 0
    for record in found:
        report = record.get('report')
        state = f'failed {record["failure"]["key"]}' if record.get('failure') else (report or {}).get('verdict', '')
        model = record.get('model') or record['requested_model']
        print(f'{record["run_id"]:<52} {model:<20} {record["effort"]:<7} {state:<24} {severity_counts(report)}')
    return 0


def show(args: argparse.Namespace) -> int:
    found = runs.record(args.run_id) if args.run_id else next(iter(runs.records()), None)
    if found is None:
        print(f'persona-review: no run {args.run_id or "stored yet"}', file=sys.stderr)
        return 1
    if args.json:
        emit(found)
    else:
        render(found)
    return 0


def render(record: dict[str, Any]) -> None:
    scenario, subject = record['scenario'], record['subject']
    print(f'run       {record["run_id"]}')
    print(f'scenario  {scenario["name"]}')
    print(f'          {scenario["persona"]} × {scenario["machine"]} × {scenario["operating_system"]} × {scenario["subject"]}')
    print(f'subject   {subject["repository"]} at {subject["commit"][:12]} ({subject["ref"]}), {subject["file_count"]} files')
    model = record.get('model') or record['requested_model']
    print(f'model     {model} at {record["effort"]}, Claude Code {record.get("claude_code_version") or "unknown"}')
    requests = record.get('model_requests', 'unknown')
    counted = f"{record.get('num_turns')} turns by claude's count"
    print(f'requests  {requests} of {record["max_turns"]} allowed, {counted}, {record["duration_seconds"]}s')
    print(f'tokens    {tokens_line(record["tokens"])}')
    if record.get('failure'):
        print(f'failed    {record["failure"]["key"]}: {record["failure"]["cause"]}')
        return
    report = record['report']
    print(f'verdict   {report["verdict"]}')
    print(f'findings  {severity_counts(report)}')
    print()
    print(report['summary'])
    ranked = sorted(report['findings'], key=lambda f: SEVERITIES.index(f['severity']))
    for finding in ranked:
        places = ', '.join(f'{loc["path"]}:{loc["line_start"]}-{loc["line_end"]}' for loc in finding['locations'])
        print()
        print(f'{finding["id"]}  {finding["severity"]:<13} {finding["cwe"]:<9} {finding["title"]}')
        print(f'         {places}')
        print(f'         fix ({finding["remediation_kind"]}): {finding["remediation"]}')
    for heading, lines in (('conditions', report['conditions']), ('limitations', report['limitations'])):
        if lines:
            print(f'\n{heading}')
            for line in lines:
                print(f'  - {line}')
    print(f'\ninventory  {len(report["inventory"])} items; --json prints them')


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog='persona-review', description=__doc__.splitlines()[0].split(': ', 1)[1])
    verbs = root.add_subparsers(dest='verb', required=True)

    listed = verbs.add_parser('list', help='every persona, machine, operating system, subject and scenario')
    listed.add_argument('--json', action='store_true')
    listed.set_defaults(handler=list_catalog)

    points = verbs.add_parser('matrix', help='every combination the machines allow, and the scenario naming it')
    points.add_argument('--json', action='store_true')
    points.set_defaults(handler=show_matrix)

    running = verbs.add_parser('run', help='run one review, by scenario or by naming all four axes')
    running.add_argument('scenario', nargs='?', help='a scenario from `list`')
    running.add_argument('--persona')
    running.add_argument('--machine')
    running.add_argument('--os', dest='operating_system')
    running.add_argument('--subject')
    running.add_argument('--submission', help="the submitter's words, for a run named by its axes")
    running.add_argument('--model', default='opus', help='the model claude is given (default: opus)')
    running.add_argument(
        '--effort', choices=matrix.EFFORTS, help=f"the effort claude is given (default: the persona's effort, else {matrix.DEFAULT_EFFORT})"
    )
    running.add_argument(
        '--max-turns', type=int, help="cap on model requests, passed as claude's --max-turns (default: the persona's max_turns)"
    )
    running.add_argument('--timeout', type=int, default=3600, help='seconds before the call is killed (default: 3600)')
    running.add_argument('--only', action='append', default=[], metavar='PATH', help='export only this subject path; repeatable')
    running.add_argument('--mock', action='store_true', help="write the persona's canned report instead of calling a model")
    running.add_argument('--json', action='store_true')
    running.set_defaults(handler=run)

    stored = verbs.add_parser('runs', help='stored runs, newest first')
    stored.add_argument('-n', '--limit', type=int, default=20)
    stored.add_argument('--json', action='store_true')
    stored.set_defaults(handler=list_runs)

    shown = verbs.add_parser('show', help='one stored run, the newest by default')
    shown.add_argument('run_id', nargs='?')
    shown.add_argument('--json', action='store_true')
    shown.set_defaults(handler=show)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == '__main__':
    sys.exit(main())
