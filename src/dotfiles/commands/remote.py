"""Whether this machine can exchange an artefact with the one on the other side.

One verb, for the same reason `network check` has one: the question has a single
answer and `check` is already the word for "report what is wrong". It writes
nothing anywhere — not to the machine and not to the remote.

**Presence of the transport is not readiness, so both are measured.** A box with
`ifiles` installed and no credential for it answers `command -v` perfectly and
fails at the first upload, which is exactly the state standards/configuration.md
§ "A declared requirement states what has to be true, not only that the thing
exists" describes. The listing is therefore attempted rather than inferred.
"""

from __future__ import annotations

import typer

from dotfiles import remote as transport
from dotfiles.commands import QuietOption
from dotfiles.commands import VerboseOption
from dotfiles.commands import verbosity
from dotfiles.output import MATCHED
from dotfiles.output import VERDICT_COLOURS
from dotfiles.output import VERDICT_MARKS
from dotfiles.output import console
from dotfiles.output import emit_json
from dotfiles.output import err_console
from dotfiles.output import hint
from dotfiles.output import render_row
from dotfiles.output import render_verdict
from dotfiles.output import section_line
from dotfiles.reconcile import ResourceVerdict
from dotfiles.vocabulary import ExitCode

app = typer.Typer(no_args_is_help=True, help='Whether this machine can exchange an artefact with the remote')

JsonOption = typer.Option(False, '--json', help='Emit machine-readable output on stdout')


@app.command('check')
def check(as_json: bool = JsonOption, verbose: int = VerboseOption, quiet: bool = QuietOption) -> None:
    """Report whether the configured remote is declared, installed and answering.

    Exit 3 on a fault rather than 0, so a caller learns the answer without parsing
    the output. A machine that has declared no remote at all is a fault here and
    nowhere else: every other verb treats an absent `[remote]` as an ordinary state
    and refuses only when asked to use one, while this verb exists to be asked
    exactly that question.

    An undeclared `mkdir` or `delete` is a fact rather than a finding. Both are
    optional, and reporting them as faults would exit non-zero on every working
    remote that never needed one.
    """
    verbosity(verbose, quiet)
    found = transport.read()
    measured = transport.measure(found)
    faults = [reach for reach in measured if reach.faulty]

    if as_json:
        emit_json(
            {
                'declared': found.declared,
                'problem': found.problem,
                'root': found.remote.root if found.remote else '',
                'program': found.remote.transport.program if found.remote else '',
                'faults': len(faults),
                'measured': [
                    {'subject': reach.subject, 'ok': reach.ok, 'required': reach.required, 'detail': reach.detail} for reach in measured
                ],
            }
        )
        raise typer.Exit(ExitCode.ISSUE if faults else ExitCode.CONVERGED)

    verdict = ResourceVerdict.ISSUE if faults else ResourceVerdict.CONVERGED
    word = str(verdict)
    detail = f'{len(measured) - len(faults)} of {len(measured)} measured'
    console.print(section_line(VERDICT_MARKS[word], 'remote', detail, VERDICT_COLOURS[word]))
    for reach in measured:
        label = MATCHED if reach.ok else ('issue' if reach.required else 'absent')
        render_row(label, reach.subject, reach.detail, VERDICT_COLOURS['issue'] if reach.faulty else '')

    if not found.declared:
        hint(transport.ADVICE)
    render_verdict(word, f'{detail} for the remote', err_console)
    raise typer.Exit(ExitCode.ISSUE if faults else ExitCode.CONVERGED)
