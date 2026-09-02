"""Whether the credential helpers git is configured with can actually run.

`auth.py` asks the same shape of question about a roster the *manifest* names.
This one has no roster: a helper is whatever the include chain resolved to, so
the subjects are discovered from the configuration and differ per machine and per
remote. That is the whole reason it is a separate resource rather than four more
rows in `auth` — nothing declares these, and nothing could.

**The failure this was built for is not an authentication failure.** On the WSL
box the helper is a Windows executable reached across `/mnt/c`, and Linux runs a
PE binary only while the `binfmt_misc` handler WSL registers is present. When it
is not, every `.exe` fails with `Exec format error` and git reports it as an
authentication problem — the push fails, the credential prompt returns, and
nothing anywhere names the interpreter that went missing. A reboot fixes it,
which is what keeps it looking like a flaky credential store.

So the measurement is deliberately *not* a round trip. Three things are asked in
order, and each is a different fault with a different fix: is a helper configured
at all, is the program it names present, and will the kernel start it. Only the
last needs the helper to run, and it runs with no arguments and a closed
conversation — enough to prove the binary starts, and not enough to ask anyone
for a secret.

**Asking for an actual credential is `show --probe` and never `check`.** `check`
runs unattended on the timer `providers/schedule.py` installs. A real `get` is
what makes a helper open a browser or a GUI prompt, and a scheduled check that
can raise a login window on an idle desk is a check nobody leaves enabled. The
probe is opt-in, interactive by assumption, and still refuses to prompt —
`GIT_TERMINAL_PROMPT=0` and `GCM_INTERACTIVE=never` go into its environment.

The layering is read through `gitconfig.read()` rather than a second `git config`
call, which is what makes the origin available: every finding here names the file
that set the helper, and on a machine with five config files that is most of the
answer.
"""

from __future__ import annotations

import dataclasses as dc
import shlex
import shutil
from pathlib import Path

from dotfiles import evidence
from dotfiles import gitconfig
from dotfiles.effects import NOT_FOUND
from dotfiles.effects import TIMED_OUT
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.plan import Plan
from dotfiles.plan import Stage
from dotfiles.privilege import Escalates
from dotfiles.resources import Change
from dotfiles.resources import Examined
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.session import Session

NAME = 'credentials'

HELPER_KEY = 'credential.helper'
HELPER_PREFIX = 'credential.'
HELPER_SUFFIX = '.helper'

NO_PROMPT = {'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'never'}
"""What stops a probe turning into a login.

Both halves are needed and they belong to different programs. git's own variable
suppresses the terminal prompt it falls back to when no helper answers; GCM's
suppresses the browser and GUI dialog it opens on its own initiative, which git
knows nothing about. Neither is a guarantee about a third-party helper, which is
the other reason `check` never asks for a credential at all.
"""

INTERPRETER_HINT = (
    'a Windows helper under /mnt/c needs the WSL binfmt handler; '
    'check `cat /proc/sys/fs/binfmt_misc/WSLInterop`, and `wsl.exe --shutdown` re-registers it'
)


@dc.dataclass(frozen=True, slots=True)
class Helper:
    """One configured helper, and where the configuration came from."""

    scope: str
    """The URL this helper is keyed on, or '' when it applies to every remote."""

    value: str
    """The raw config value, exactly as git stores it."""

    origin: Path

    @property
    def resets(self) -> bool:
        """Whether this is git's idiom for clearing inherited helpers.

        An empty value is not a helper. `common.gitconfig` sets one before each
        real helper precisely so a system-wide entry cannot stack underneath, and
        reading that as a broken helper would report a fault on every machine —
        which is how a check earns being switched off.
        """
        return not self.value.strip()

    @property
    def argv(self) -> tuple[str, ...]:
        """The command git would run, split the way the shell it uses would split it.

        **A helper value is a command line, never a filename.** git starts every
        one of them through a shell, so a path containing a space is escaped in
        the config and the escaping belongs to the shell rather than to the file:
        `/mnt/c/Program\\ Files/...` names one file whose name has a space in it.
        Taking the value as written looks for a directory called `Program\\`,
        reports a helper git runs perfectly well as missing, and — because
        `_asked` stops at the first fault — never reaches the interpreter question
        this resource was built to ask. A real login failure then sits hidden
        behind a fault that is not real.

        Which of git's three rules applies is still decided on the raw value,
        before any splitting, because that is the order git decides it in. An
        unescaped space stays broken and is meant to. git cannot run that either,
        and reporting the first word missing is the error git itself prints.
        """
        value = self.value.strip()
        if self.shell_form:
            return tuple(_split(value[1:].strip()))
        if '/' in value or '\\' in value:
            return tuple(_split(value))
        return (f'git-credential-{value}',)

    @property
    def program(self) -> str:
        """The executable git would run, by git's own three resolution rules.

        A leading `!` is a shell command, and only its first word is a program —
        `!gh auth git-credential` is answered by whether `gh` runs, not by what
        `gh auth git-credential` returns. Anything containing a separator is a
        path and is used as written. Everything else is a bare name that git
        expands to `git-credential-<name>` and looks up on PATH.
        """
        argv = self.argv
        return argv[0] if argv else ''

    @property
    def shell_form(self) -> bool:
        """Whether git hands this to a shell rather than executing it directly."""
        return self.value.strip().startswith('!')

    def invocation(self, operation: str) -> list[str]:
        """The argv git itself would use to ask this helper to do something.

        The shell form is the one that cannot be assembled by appending: git runs
        `!cmd args` through `sh -c` with the operation on the end, so
        `!gh auth git-credential` asking for a credential is
        `sh -c 'gh auth git-credential get'` — never `gh get`, which is not a
        command and would report every `!` helper as broken.

        **A caller must establish there is a command before asking for one.** This
        appends unconditionally, so an empty value yields `sh -c ' get'` and the
        shell runs whatever `get` resolves to on PATH. `probe` is the only caller
        and checks `program` first.
        """
        value = self.value.strip()
        if self.shell_form:
            return ['sh', '-c', f'{value[1:].strip()} {operation}']
        return [*self.argv, operation]

    @property
    def label(self) -> str:
        return self.scope or 'every remote'


@dc.dataclass(frozen=True, slots=True)
class Found:
    """What asking about one helper turned up."""

    helper: Helper
    verdict: Verdict
    detail: str = ''
    advice: str = ''


@dc.dataclass(frozen=True, slots=True)
class Observed:
    found: tuple[Found, ...]

    @property
    def working(self) -> int:
        return sum(1 for entry in self.found if entry.verdict is Verdict.MATCHED)

    @property
    def summary(self) -> str:
        if not self.found:
            return 'git is configured with no credential helper on this machine'
        return f'{self.working} of {len(self.found)} configured helper(s) runnable'

    @property
    def inventory(self) -> tuple[Examined, ...]:
        """The helpers that run, keyed the way `diff` keys the ones that do not.

        Same `label → program` item as a change here, so a broken helper and a
        working one are the same row with a different verdict rather than two
        spellings of one helper.
        """
        return tuple(
            Examined(f'{entry.helper.label} → {entry.helper.program}', entry.detail)
            for entry in self.found
            if entry.verdict is Verdict.MATCHED
        )


class CredentialsResource:
    name = NAME
    help = 'the git credential helpers this machine is configured with'

    def observe(self, session: Session, plan: Plan) -> Observed:
        return Observed(tuple(_asked(helper) for helper in helpers()))

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        """One row per helper that will not run.

        `UNKNOWN` is `Repair.NONE`, following `auth.py`: a helper that could not
        be measured is not evidence that it is broken, and counting it as an Issue
        would put a timeout on a busy machine into the exit code.
        """
        return tuple(
            Change(
                NAME,
                Stage.CREDENTIALS,
                f'{entry.helper.label} → {entry.helper.program}',
                entry.verdict,
                repair=Repair.NONE if entry.verdict is Verdict.UNKNOWN else Repair.BY_HAND,
                detail=entry.detail,
                # The origin on its own line rather than in `observed`, which the
                # renderer spells `(is 'X')` — true of a value and misleading of a
                # file. What a reader needs is the config to open, and on a machine
                # with five of them that is most of the fix.
                advice='\n'.join(filter(None, [entry.advice, f'set in {entry.helper.origin}'])),
                observed=entry.helper.value,
            )
            for entry in observed.found
            if entry.verdict is not Verdict.MATCHED
        )

    def perform(self, session: Session, change: Change, privilege: Escalates) -> Outcome:
        """Never reached — every change here is BY_HAND, so `actionable` is false.

        Nothing here is the repo's to write. A helper that is missing is a tool to
        install, and one the kernel will not start is a fault in the machine
        underneath git rather than in any file this repo deploys.
        """
        return Outcome(change, OutcomeStatus.REFUSED, 'a credential helper is machine state; the repo has nothing to write here')


def helpers(scope: str = '--global') -> tuple[Helper, ...]:
    """Every configured helper, read off the layering rather than asked for again.

    `gitconfig.read()` already resolves the include chain and keeps the file each
    setting came from, so this costs nothing extra and every finding can name the
    file to go and edit. A second `git config --get-urlmatch` would answer for one
    URL at a time and would not say where the answer lived.
    """
    layering = gitconfig.read(scope)
    found = []
    for setting in layering.settings:
        if setting.key == HELPER_KEY:
            found.append(Helper('', setting.value, setting.origin))
        elif setting.key.startswith(HELPER_PREFIX) and setting.key.endswith(HELPER_SUFFIX):
            found.append(Helper(setting.key[len(HELPER_PREFIX) : -len(HELPER_SUFFIX)], setting.value, setting.origin))
    return tuple(helper for helper in found if not helper.resets)


def _asked(helper: Helper) -> Found:
    """The three questions, in the order that makes each answer actionable.

    Present-but-unrunnable is `STALE` rather than `MISSING`, and the distinction is
    the whole point of the resource: the configuration is correct and the machine
    underneath it is not, so the fix is nothing to do with git. `MISSING` would
    send a reader to `common.gitconfig` to fix a binfmt registration.
    """
    program = helper.program
    if not program:
        return Found(helper, Verdict.STALE, 'the value starts with `!` and names no command', advice='set a helper, or remove the line')

    located = Path(program) if ('/' in program or '\\' in program) else _on_path(program)
    if located is None:
        return Found(
            helper,
            Verdict.MISSING,
            f'{program} is not on PATH',
            advice=f'install what provides {program}, or point the helper at a path that exists',
        )
    if not located.exists():
        return Found(
            helper,
            Verdict.MISSING,
            f'{located} does not exist',
            advice='correct the path, or install the helper it names',
        )

    answer = run([str(located)], output=Output.QUIET, timeout=evidence.PROBE_SECONDS, env=NO_PROMPT)
    if answer.returncode == TIMED_OUT:
        return Found(helper, Verdict.UNKNOWN, f'{located} did not answer within {evidence.PROBE_SECONDS:g}s')
    if answer.returncode == NOT_FOUND:
        # The file is there and the kernel refused it, which is the WSL case. The
        # transcript carries the OS's own `strerror` — `effects.run` folds every
        # OSError to this code and keeps the wording — so the reader sees `Exec
        # format error` in the words the shell would have used.
        return Found(
            helper,
            Verdict.STALE,
            f'{located} exists but the kernel would not start it: {answer.transcript.strip() or "no reason given"}',
            advice=INTERPRETER_HINT if _is_windows_binary(located) else 'check the file is executable and built for this architecture',
        )
    return Found(helper, Verdict.MATCHED, f'{located} runs')


def _split(command: str) -> list[str]:
    """A command line as a shell would split it, leaving an unclosed quote alone.

    `shlex` raises on a value that ends mid-quote. That is a fault in the config
    and not in the helper, so the value is handed back whole and fails the
    existence question with the text that was actually written — which is what a
    reader needs to find the line, and better than a traceback out of `check`.
    """
    try:
        return shlex.split(command)
    except ValueError:
        return [command]


def _on_path(program: str) -> Path | None:
    found = shutil.which(program)
    return Path(found) if found else None


def _is_windows_binary(path: Path) -> bool:
    """Whether the advice about binfmt applies, decided by the two things that
    make it apply: a PE extension, or a path into a mounted Windows drive."""
    return path.suffix.lower() == '.exe' or str(path).startswith('/mnt/')


def probe(helper: Helper) -> tuple[bool, str]:
    """Ask a helper for an actual credential. Interactive by assumption.

    Never reached from `observe`. This is what `show --probe` runs, and it is the
    only thing here that can make a helper contact a server or open a window.

    The request is git's credential protocol on stdin: a `key=value` line per
    field and a blank line to end it. A helper that has the credential answers
    with the same format including `password=`; one that does not answers with
    nothing and exits 0, which is indistinguishable from success on the exit code
    alone and is why the output is what gets read.
    """
    # A helper naming no command has no program to ask, and `invocation` cannot
    # say so: it appends the operation word, so an empty command assembles
    # `sh -c ' get'` and the shell resolves `get` on PATH and runs whatever is
    # there. `--probe` then executes a binary the configuration never named, on the
    # one entry the resource had already ruled unusable. `program` is where that
    # judgement already lives, so this asks it rather than re-deciding.
    if not helper.program:
        return False, 'the helper names no command, so there is nothing to ask'

    scope = helper.scope or 'https://github.com'
    protocol, _, rest = scope.partition('://')
    host = rest or protocol
    request = f'protocol={protocol if rest else "https"}\nhost={host}\n\n'

    answer = run(
        helper.invocation('get'),
        output=Output.QUIET,
        timeout=evidence.PROBE_SECONDS,
        env=NO_PROMPT,
        stdin_text=request,
    )
    if answer.returncode in (TIMED_OUT, NOT_FOUND):
        return False, answer.transcript.strip() or 'the helper did not run'
    if not answer.ok:
        return False, answer.transcript.strip() or f'the helper exited {answer.returncode}'
    if 'password=' in answer.stdout:
        return True, f'returned a credential for {host}'
    return False, f'ran and returned no credential for {host}; log in with whatever owns {helper.program}'


RESOURCE = CredentialsResource()
