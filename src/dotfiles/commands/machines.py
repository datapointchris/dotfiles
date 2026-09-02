"""The declaration side: what a machine resolves to, before anything checks it.

`machines show` is the resolve command — the one `machine-axes.md` § 8 insists
must exist *before* anything varies per coordinate, or the system becomes
unauditable. It
renders the whole `Plan`: the coordinates, the flags, and every item with the
selector that pulled it in. Nothing about an install is decided outside that
object, so what this prints is what a run will do.
"""

from __future__ import annotations

import os
from pathlib import Path

import typer

from dotfiles import catalog
from dotfiles import machine as machines
from dotfiles import paths
from dotfiles import plan as planning
from dotfiles import resolve as resolver
from dotfiles import validate
from dotfiles.commands import QuietOption
from dotfiles.commands import VerboseOption
from dotfiles.commands import verbosity
from dotfiles.output import EVIDENCE_INDENT
from dotfiles.output import console
from dotfiles.output import emit_json
from dotfiles.output import emit_text
from dotfiles.output import error
from dotfiles.output import hint
from dotfiles.output import section_line
from dotfiles.resources import env
from dotfiles.vocabulary import ExitCode

app = typer.Typer(no_args_is_help=True, help='Machine manifests: what each machine declares')


def precondition_note(precondition: planning.Precondition) -> str:
    """The `[amd_gpu]` suffix on a row, or '' where the item has no precondition.

    A named function rather than an f-string inside the render loop, because the
    escape is the whole content: rich reads `[amd_gpu]` as a style tag and swallows
    it silently, so an unescaped annotation is invisible on every entry that
    declares one. A value that exists only inside a printed
    sentence cannot be asserted without asserting the sentence — and asserting
    the row means pinning a terminal width, which belongs to whoever ran the
    command rather than to us.
    """
    return rf'  \[{precondition}]' if precondition else ''


def manifest_names() -> list[str]:
    """Every manifest in the repo, by name. Read from disk, never listed anywhere."""
    if not paths.MANIFESTS_DIR.is_dir():
        return []
    return sorted(path.stem for path in paths.MANIFESTS_DIR.glob('*.yml'))


def _resolve_machine(name: str | None) -> str:
    """Fall back to $MACHINE, which `~/.env` sets and every install path reads."""
    resolved = name or os.environ.get('MACHINE')
    if resolved:
        return resolved

    error('no machine given and MACHINE is unset in the environment')
    hint(f'name one of: {", ".join(manifest_names())}')
    raise typer.Exit(ExitCode.USAGE)


def _manifest_path(name: str) -> Path:
    """The path, with a name nothing declares refused the way every door refuses it.

    The sentence is `machine.manifest_path`'s, so this is the conversion to a usage
    error and nothing else. Wording it here is what let one tool answer the same
    question two ways depending on which verb was asked.
    """
    return machines.manifest_path(name)


def _loaded(name: str) -> machines.Machine:
    """One manifest, with both ways of not getting one answered as they are elsewhere.

    A name nothing declares is a usage error. A manifest that exists and will not
    parse is an Issue, with every reason printed — the same split `_plan` makes,
    and the same one `Session.resolve` makes for the verbs that want a Session.

    A caller wanting only the exception should reach for this rather than calling
    `manifest_path` for its side effect: that answers whether the *file* is there
    and says nothing about whether it reads, so an unparseable manifest went
    straight through it and out of the leaf as exit 1 with both streams empty.
    """
    return machines.load(name)


@app.command('list')
def list_machines(as_json: bool = typer.Option(False, '--json', help='Emit the names as JSON')) -> None:
    """List the machines this repo can install."""
    names = manifest_names()
    if as_json:
        emit_json(names)
        return
    for name in names:
        console.print(name)


@app.command('show')
def show_machine(
    name: str = typer.Argument(None, help='Machine name (default: $MACHINE)'),
    owner: str = typer.Option(None, '--owner', help='Only what this GitHub owner publishes'),
    raw: bool = typer.Option(False, '--raw', help='Print the manifest as written, resolving nothing'),
    as_json: bool = typer.Option(False, '--json', help='Emit the resolved plan as JSON'),
) -> None:
    """Resolve a machine and print everything it should have.

    `--raw` is the manifest as written. Everything else is the resolution, which
    is a different question: the manifest says `system_packages: core` and the
    resolution says which 25 packages that is on this machine's package manager.
    """
    resolved = _resolve_machine(name)
    # Before resolving, so a typo stays a usage error naming the machines that do
    # exist rather than a report that this one's declaration cannot be read.
    path = _manifest_path(resolved)

    if raw:
        emit_text(path.read_text())
        return

    plan = _plan(resolved, owner)

    if as_json:
        emit_json({**plan.machine.as_dict(), 'items': [item.as_dict() for item in plan.items]})
        return

    _render(plan)


def _plan(name: str, owner: str | None = None) -> planning.Plan:
    """Resolve, turning either loader's refusal into the report it is.

    A traceback would be the wrong shape for both: an invalid declaration is a
    finding about the repo, not a crash in the tool reading it.
    """
    return resolver.resolve(catalog.load(), machines.load(name), owner=owner)


def _section(name: str, detail: str) -> None:
    """One group of the resolution, in the columns every report's sections use.

    No mark, and that is the honest answer rather than a gap: this command resolves
    a *declaration* and measures nothing, so there is no verdict to put in front of
    the name. The column stays so a reader moving between this and `dotfiles plan`
    finds each section's detail in the same place.

    On stdout with the rows beneath it, unlike the reports, because here the
    listing is the answer and `--json` carries the same thing. Sending it through
    `render_row` would put a machine's declared plan on stderr and let `-q` remove
    it — so the rows keep their own widths and take `EVIDENCE_INDENT` alone, which
    is what makes a heading read as one.
    """
    console.print()
    console.print(section_line(' ', name, detail))


def _render(plan: planning.Plan) -> None:
    machine = plan.machine
    console.print(f'[bold]{machine.name}[/]  {machine.platform_label}')

    _section('coordinates', 'where this machine sits on each axis')
    for axis, value in machine.coordinates.as_dict().items():
        console.print(f'{EVIDENCE_INDENT}{axis:<16} {value}')

    _section('flags', f'{len(machine.flags)} feature switch(es) written to ~/.env')
    for flag, value in machine.flags.items():
        console.print(f'{EVIDENCE_INDENT}{flag:<26} {value}')

    if machine.requirements:
        _section('by hand', f'{len(machine.requirements)} thing(s) apply will never supply')
        for requirement in machine.requirements:
            console.print(f'{EVIDENCE_INDENT}{requirement.path or requirement.name} — {requirement.description}')

    for stage in planning.Stage:
        items = plan.for_stage(stage)
        if not items:
            continue
        _section(stage.name.lower(), f'{len(items)} item(s)')
        for item in items:
            console.print(
                f'{EVIDENCE_INDENT}{item.provider:<14} {item.name:<28} {item.reason.selector}{precondition_note(item.precondition)}'
            )

    # In the sections' own columns, because a bare count at column 0 is a shape no
    # report here uses: no name, so the number belongs to nothing on screen, and no
    # column, so it lines up with none of the groups it sums. `total` is the honest
    # name — this command resolves a declaration and measures nothing, so there is
    # no verdict to put in front of it.
    _section('total', f'{len(plan.items)} item(s) this machine declares')


@app.command('requirements')
def machine_requirements(
    name: str = typer.Argument(None, help='Machine name (default: $MACHINE)'),
    as_json: bool = typer.Option(False, '--json', help='Emit the register as JSON'),
    as_safekeep: bool = typer.Option(False, '--safekeep', help='Emit the files as safekeep [[back_up_paths]] blocks'),
) -> None:
    """What this machine needs that `apply` will never supply.

    The register in `install/flags.yml`: values that must be set by hand below
    the OVERRIDES marker, and files that arrive from somewhere other than this
    repo. Everything the repo knows a machine needs while deliberately not
    knowing its contents.

    Declaration, not state — it answers for any machine, including one you are
    not standing on, so it never reports whether a file is actually there.
    `dotfiles check` is the half that looks.
    """
    if as_json and as_safekeep:
        raise typer.BadParameter('--json and --safekeep are two formats of one answer; pick one')

    machine = _loaded(_resolve_machine(name))

    if as_json:
        emit_json([_requirement_dict(entry) for entry in machine.requirements])
    elif as_safekeep:
        emit_text(_safekeep_block(machine))
    else:
        _render_requirements(machine)


def _requirement_dict(entry: machines.Requirement) -> dict[str, object]:
    return {
        'name': entry.name,
        'kind': 'file' if entry.is_file else 'value',
        'path': entry.path,
        'description': entry.description,
        'restore': entry.restore or (env.RESTORE if entry.is_file else 'set it below the OVERRIDES marker in ~/.env'),
        'tags': list(entry.tags),
        'consumers': list(entry.consumers),
        'narrowing': dict(entry.narrowing),
        'requires_values': list(entry.requires_values),
        'file_must_exist': entry.file_must_exist,
    }


def _render_requirements(machine: machines.Machine) -> None:
    console.print(f'[bold]{machine.name}[/]')

    if values := machine.required_values:
        _section('values', f'{len(values)} set by hand below the OVERRIDES marker in ~/.env')
        width = max(len(entry.name) for entry in values)
        for entry in values:
            console.print(f'{EVIDENCE_INDENT}{entry.name:<{width}}  {entry.description}', markup=False, highlight=False)
            # A rebuild that sets the value and never puts the file there has a
            # machine that answers and cannot work, which is what the check now
            # reports and what this listing owes a person doing it by hand.
            if entry.file_must_exist:
                console.print(f'{EVIDENCE_INDENT}{"":<{width}}  the file it names has to be there too', markup=False, highlight=False)

    if files := machine.required_files:
        _section('files', f'{len(files)} restored by hand, never written by apply')
        width = max(len(entry.path) for entry in files)
        for entry in files:
            console.print(f'{EVIDENCE_INDENT}{entry.path:<{width}}  {entry.description}', markup=False, highlight=False)
            # Only where it is not the default, so the one entry safekeep cannot
            # restore is the one that stands out rather than the one that blends in.
            if entry.restore:
                console.print(f'{EVIDENCE_INDENT}{"":<{width}}  {entry.restore}', markup=False, highlight=False)
            # Restoring the file is half the job where it reads a value: a rebuild
            # that puts every file back and none of the values still has a machine
            # that cannot run them.
            if needed := [name for name in entry.requires_values if name in {value.name for value in machine.required_values}]:
                console.print(f'{EVIDENCE_INDENT}{"":<{width}}  needs {", ".join(needed)} set first', markup=False, highlight=False)

    if not machine.requirements:
        # A section and an indented row, like the two groups above, rather than a
        # sentence at a two-space indent of its own. An empty register is an answer
        # to the same question `values` and `files` answer, and a reader scanning
        # the name column for it finds nothing where a heading should be.
        _section('by hand', 'nothing')
        console.print(f'{EVIDENCE_INDENT}every file and value this machine needs is written by an apply')


SAFEKEEP_TAG = 'dotfiles'
"""So `safekeep restore --tag dotfiles` is exactly this register and nothing else."""


def _safekeep_block(machine: machines.Machine) -> str:
    """The register as safekeep's own `[[back_up_paths]]` syntax.

    A block to paste rather than a whole config, and the distinction is not
    cosmetic: required-to-operate is a strict subset of worth-backing-up, so a
    generated config would silently drop ~/.ssh and every other file this repo
    has no opinion about. What can be generated is the part the repo can prove.

    Required *values* are named in a trailing comment rather than dropped. They
    have no path to back up — they live below the OVERRIDES marker in ~/.env —
    but a rebuild that restores every file and none of them still has a broken
    machine, and this is the only listing that knows both halves.
    """
    lines = [
        f'# The files {machine.name} needs that dotfiles will never write.',
        f'# Generated by `dotfiles machines requirements {machine.name} --safekeep`.',
    ]

    for entry in machine.required_files:
        tags = ', '.join(f'"{tag}"' for tag in (SAFEKEEP_TAG, *entry.tags))
        # The declaration verbatim, variable and all. This block is generated *for* a
        # named machine and pasted *on* it, so expanding here would bake the generating
        # machine's answer into another machine's config — and an entry declared through
        # a variable is per-machine precisely because those differ. safekeep expands it
        # at the point of use.
        lines += ['', f'# {entry.description}', '[[back_up_paths]]', f'path = "{entry.path}"', f'tags = [{tags}]']

    if values := machine.required_values:
        lines += ['', '# No path to back up, and still needed on a rebuild — set below the OVERRIDES', '# marker in ~/.env:']
        lines += [f'#   {entry.name} - {entry.description}'.rstrip(' -') for entry in values]

    # Trailing newline because `emit_text` writes byte for byte, and this is
    # pasted into a TOML file rather than read on a terminal.
    return '\n'.join([*lines, ''])


@app.command('check')
def check_machines(
    name: str = typer.Argument(None, help='Machine name (default: every manifest)'),
    as_json: bool = typer.Option(False, '--json', help='Emit the findings as JSON'),
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Validate the declaration: every manifest, and packages.yml's own structure.

    Whole-declaration, whether or not a machine is named. `packages.yml` is
    shared, so a manifest cannot be validated without it, and a typo in
    `linux-lxc-server.yml` is invisible from the Mac where the commit happens —
    which is why this is what gates commits. Narrowing to one machine arrives
    with the resolver; the argument is accepted now so the surface does not move.

    Exits 3 on an error and 0 on warnings alone. An invalid declaration is the
    archetypal Issue — nothing `apply` can repair — so it takes `check`'s code
    rather than drift's, which is what lets the same number mean the same thing
    whether it came from here or from the whole-machine walk.
    """
    verbosity(verbose, quiet)
    if name:
        _manifest_path(name)
        hint(f'checking every manifest, not only {name}: packages.yml is shared by all of them')

    found = validate.declaration()
    if as_json:
        emit_json([finding.as_dict() for finding in found])
    else:
        _render_findings(found)
    raise typer.Exit(ExitCode.ISSUE if validate.errors(found) else ExitCode.CONVERGED)


def _render_findings(findings: tuple[validate.Finding, ...]) -> None:
    """Grouped by section, because that is the file a reader has to open next."""
    by_section: dict[str, list[validate.Finding]] = {}
    for finding in findings:
        by_section.setdefault(finding.section, []).append(finding)

    for section in sorted(by_section):
        console.print(f'\n[bold cyan]{section}[/]')
        for finding in by_section[section]:
            colour = 'red' if finding.severity is validate.Severity.ERROR else 'yellow'
            console.print(f'  [{colour}]{finding.severity:<7}[/] {finding.message}', highlight=False)

    broken, warned = len(validate.errors(findings)), len(findings) - len(validate.errors(findings))
    console.print()
    console.print(f'{broken} errors, {warned} warnings')


@app.command('edit')
def edit_machine(name: str = typer.Argument(None, help='Machine name (default: $MACHINE)')) -> None:
    """Open a machine's manifest in $EDITOR."""
    path = _manifest_path(_resolve_machine(name))
    os.execvp(editor := os.environ.get('EDITOR', 'nvim'), [editor, str(path)])
