"""The four axes a review is drawn from, and the scenarios that pick one value on each.

A review is one point in a test matrix: a persona reviewing a subject for a machine running an
operating system. Each axis is a directory of YAML files beside this module, one file per value,
named for the value. A machine's `operating_systems` says which points exist, the way a CI matrix's
`exclude` does. A scenario names one value per axis and adds the submitter's own words.
"""

from __future__ import annotations

import dataclasses as dc
import itertools
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).parent

AXES = {
    'persona': 'personas',
    'machine': 'machines',
    'operating_system': 'operating-systems',
    'subject': 'subjects',
}
"""Each axis, beside the directory holding its values."""

EFFORTS = ('low', 'medium', 'high', 'xhigh', 'max')
"""What `claude --effort` takes. It ignores any other value and runs at its default, so the catalog refuses one."""

DEFAULT_EFFORT = 'medium'
"""For a persona that names none."""


class CatalogError(Exception):
    """A name no file declares, or a file whose fields do not agree with its neighbors."""


@dc.dataclass(frozen=True)
class Entry:
    axis: str
    name: str
    fields: dict[str, Any]
    path: Path

    def text(self, key: str) -> str:
        return str(self.fields.get(key) or '').strip()


@dc.dataclass(frozen=True)
class Scenario:
    name: str
    persona: Entry
    machine: Entry
    operating_system: Entry
    subject: Entry
    submission: str

    def names(self) -> dict[str, str]:
        return {
            'name': self.name,
            'persona': self.persona.name,
            'machine': self.machine.name,
            'operating_system': self.operating_system.name,
            'subject': self.subject.name,
            'submission': self.submission,
        }

    @property
    def effort(self) -> str:
        return self.persona.text('effort') or DEFAULT_EFFORT

    @property
    def rubric(self) -> Path:
        return HERE / 'rubrics' / f'{self.persona.fields["rubric"]}.md'

    @property
    def report_schema(self) -> Path:
        return HERE / 'schemas' / f'{self.persona.fields["report_schema"]}.schema.json'

    @property
    def mock_report(self) -> Path:
        return HERE / 'mock-reports' / f'{self.persona.fields["report_schema"]}.json'


def read_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text())
    if not isinstance(loaded, dict):
        raise CatalogError(f'{path} holds no mapping')
    if loaded.get('name') != path.stem:
        raise CatalogError(f'{path} names itself {loaded.get("name")!r}, not its filename {path.stem!r}')
    return loaded


@dc.dataclass(frozen=True)
class Catalog:
    axes: dict[str, dict[str, Entry]]
    scenarios: dict[str, dict[str, Any]]

    def entry(self, axis: str, name: str) -> Entry:
        values = self.axes[axis]
        if name not in values:
            raise CatalogError(f'no {axis} named {name!r}; known: {", ".join(sorted(values))}')
        return values[name]

    def compose(self, persona: str, machine: str, operating_system: str, subject: str, *, submission: str = '', name: str = '') -> Scenario:
        chosen = Scenario(
            name=name or f'{persona}--{machine}--{operating_system}--{subject}',
            persona=self.entry('persona', persona),
            machine=self.entry('machine', machine),
            operating_system=self.entry('operating_system', operating_system),
            subject=self.entry('subject', subject),
            submission=submission.strip(),
        )
        runs = chosen.machine.fields.get('operating_systems') or []
        if operating_system not in runs:
            raise CatalogError(f'machine {machine} runs {", ".join(runs)}, not {operating_system}')
        if chosen.effort not in EFFORTS:
            raise CatalogError(f'persona {persona} names effort {chosen.effort!r}; known: {", ".join(EFFORTS)}')
        return chosen

    def scenario(self, name: str) -> Scenario:
        if name not in self.scenarios:
            raise CatalogError(f'no scenario named {name!r}; known: {", ".join(sorted(self.scenarios))}')
        raw = self.scenarios[name]
        return self.compose(
            raw['persona'], raw['machine'], raw['operating_system'], raw['subject'], submission=raw.get('submission') or '', name=name
        )

    def combinations(self) -> list[tuple[str, str, str, str]]:
        """Every point of the matrix a machine's `operating_systems` allows."""
        points = itertools.product(self.axes['persona'], self.axes['machine'].values(), self.axes['subject'])
        return [
            (persona, machine.name, operating_system, subject)
            for persona, machine, subject in points
            for operating_system in machine.fields.get('operating_systems') or []
        ]

    def problems(self) -> list[str]:
        """Every reference in the catalog that names nothing."""
        found = []
        for machine in self.axes['machine'].values():
            for operating_system in machine.fields.get('operating_systems') or []:
                if operating_system not in self.axes['operating_system']:
                    found.append(f'machine {machine.name} names operating system {operating_system!r}, which no file declares')
        for name in self.scenarios:
            try:
                scenario = self.scenario(name)
            except CatalogError as exc:
                found.append(f'scenario {name}: {exc}')
                continue
            for path in (scenario.rubric, scenario.report_schema, scenario.mock_report):
                if not path.is_file():
                    found.append(f'persona {scenario.persona.name} names {path.relative_to(HERE)}, which does not exist')
        return found


def load(root: Path = HERE) -> Catalog:
    axes = {
        axis: {path.stem: Entry(axis, path.stem, read_yaml(path), path) for path in sorted((root / directory).glob('*.yml'))}
        for axis, directory in AXES.items()
    }
    scenarios = {path.stem: read_yaml(path) for path in sorted((root / 'scenarios').glob('*.yml'))}
    return Catalog(axes, scenarios)
