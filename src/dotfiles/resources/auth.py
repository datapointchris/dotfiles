"""Whether this machine can log in to the tools it is declared to need.

A converged machine is not necessarily a working one. Every binary can be
installed, every symlink deployed and every flag set while the CLIs that do the
work all sit logged out. Without this resource `dotfiles check` prints a screen of
converged rows while the data CLIs cannot answer a single request between them.

**The manifest names which; this module says how.** A machine's `auth:` list is
the roster, and the table below is the probe for each name. That is the shape
`custom_installers` and `steps` settled on, and it is forced here for a reason
neither of them had: half the roster is installed outside this repo entirely —
`aws` arrives through a custom installer and `bbkt` by hand on the work box — so
a field on a `packages.yml` row could not reach them. A table of tools in code
would put the roster where every other resource keeps it out of.

**Every probe is local, and that is a constraint rather than a preference.**
`check` runs unattended on the timer `providers/schedule.py` installs, whose
interval is `INTERVAL_SECONDS` there, so a network round trip per declared tool is
not affordable and would report a working login as broken the moment a machine is
offline — on a schedule, with nobody watching to discount it. The
cheap probe is per tool and it *inverts* between them, which is why each one
carries the measurement that picked it: `gh auth token` is 30ms where
`gh auth status` is 333ms, while for the personal data CLIs `auth status` is the
4ms one and `auth token` costs 215ms. Two of them have no cheap CLI probe at all
and are answered by what the tool left on disk.

**Nothing here is ever written**, exactly as `identity.py` is nothing. A login is
interactive and personal — a browser flow, a password, a device code — so an
unauthenticated tool is `Repair.BY_HAND` and `apply` never touches it. Getting
that wrong would turn every `apply` on a headless box into a prompt storm.

**Whether a credential is still current is deliberately out of scope.** An expired
keychain token and a stale SSO cache both read as present here. Asking properly
means a round trip in every case, which is the one thing this resource cannot do;
`<tool> auth status --json` already carries an `expired` field, and that is where
a later pass would start rather than here.
"""

from __future__ import annotations

import contextlib
import dataclasses as dc
import os
import shutil
import sqlite3
import tomllib
from collections.abc import Callable
from pathlib import Path

from dotfiles import evidence
from dotfiles import paths
from dotfiles.effects import NOT_FOUND
from dotfiles.effects import TIMED_OUT
from dotfiles.effects import Completed
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.plan import Plan
from dotfiles.plan import Stage
from dotfiles.privilege import Escalates
from dotfiles.resources import GITHUB_AUTH_ADVICE
from dotfiles.resources import Change
from dotfiles.resources import Examined
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.session import Session

NAME = 'auth'


@dc.dataclass(frozen=True, slots=True)
class Credential:
    """What one probe found, and what to do about it where there is nothing.

    `advice` is required whenever the verdict is `MISSING`, and `Change` refuses
    the same shape one layer down: `apply` cannot log anybody in, so the sentence
    naming the login command is the entire plan for the finding.
    """

    verdict: Verdict
    detail: str = ''
    advice: str = ''


Probe = Callable[[Session], Credential]


@dc.dataclass(frozen=True, slots=True)
class Observed:
    found: dict[str, Credential]
    """Every tool this machine declares, and what asking about it turned up."""

    @property
    def present(self) -> int:
        """How many of the declared tools showed a credential."""
        return sum(1 for credential in self.found.values() if credential.verdict is Verdict.MATCHED)

    @property
    def summary(self) -> str:
        """The count above, rather than a claim that every tool is authenticated.

        The other resources can say "all N are installed" in their converged
        sentence, because a converged sentence is the only one they reach when
        nothing drifted. This one reaches it under `plan` whatever it found —
        nothing here is ever actionable, so `plan` keeps none of it — and
        "all declared tools are authenticated" printed above four missing rows is
        the summary contradicting its own evidence.
        """
        if not self.found:
            return 'this machine declares nothing under `auth:`'
        return f'{self.present} of {len(self.found)} declared tool(s) authenticated'

    @property
    def inventory(self) -> tuple[Examined, ...]:
        """The tools that showed a credential, each with what was found.

        Declaration order rather than sorted, matching the manifest's `auth:` list,
        so the rows read as the roster with the logged-out ones lifted out of it.
        """
        return tuple(Examined(tool, credential.detail) for tool, credential in self.found.items() if credential.verdict is Verdict.MATCHED)


class AuthResource:
    name = NAME
    help = 'the tools declared under `auth:`, and whether each can log in'

    def observe(self, session: Session, plan: Plan) -> Observed:
        return Observed({tool: _asked(tool, session) for tool in session.machine.auth})

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        """One row per tool that could not show a credential.

        An `UNKNOWN` is `Repair.NONE` so that `reconcile.sift` counts it
        unmeasured rather than as an Issue. That is what stops a tool this machine
        has not installed yet being reported twice — the packages resource already
        names it missing, and a second row saying it is also not logged in adds a
        finding nobody can act on until the first one is fixed.
        """
        return tuple(
            Change(
                NAME,
                Stage.AUTH,
                tool,
                credential.verdict,
                repair=Repair.NONE if credential.verdict is Verdict.UNKNOWN else Repair.BY_HAND,
                detail=credential.detail,
                advice=credential.advice,
            )
            for tool, credential in observed.found.items()
            if credential.verdict is not Verdict.MATCHED
        )

    def perform(self, session: Session, change: Change, privilege: Escalates) -> Outcome:
        """Never reached — every change here is BY_HAND, so `actionable` is false.

        Present because the protocol has three methods and a resource that answers
        "not mine to write" explicitly is clearer than one that cannot be called
        and does not say so.
        """
        return Outcome(change, OutcomeStatus.REFUSED, 'a login is personal and interactive; the repo has nothing to write here')


def _asked(tool: str, session: Session) -> Credential:
    """One probe's answer, with an unreadable path reported rather than raised.

    A credential file under a directory this user cannot traverse is one row's
    problem. Letting the `OSError` out of `observe` makes it the whole resource's:
    the walk turns it into `auth could not be examined` and says nothing about the
    tools it did measure, which is the shape of the macOS `weakpass_edit` failure
    `evidence.py` records.

    A tool with no probe is `UNKNOWN` rather than dropped, the same answer
    `providers/steps.py` gives an undeclared row. `validate.declaration` reports it
    as an error against the manifests; this is what a reader sees in the meantime.
    """
    if tool not in PROBES:
        return Credential(Verdict.UNKNOWN, f'no probe in resources/auth.py for {tool}')
    try:
        return PROBES[tool](session)
    except OSError as unreadable:
        return Credential(Verdict.UNKNOWN, f'{tool} could not be asked: {unreadable}')


def _uninstalled(tool: str) -> Credential:
    """A tool that is not here has no login to be missing.

    `UNKNOWN` with no advice, which lands in the unmeasured bucket rather than the
    exit code. Reporting it as a missing credential would blame the login for a
    machine that has simply not installed the binary yet, and the packages resource
    is already saying so in its own row.
    """
    return Credential(Verdict.UNKNOWN, f'{tool} is not on PATH, so there is nothing to log in to')


def _unanswered(tool: str, answer: Completed) -> Credential | None:
    """A probe that never ran is not evidence about a credential, so it says so.

    `effects.run` reports both a deadline and a binary the kernel would not start
    as exit codes rather than exceptions — deliberately, so no caller needs its own
    `which` guard — which leaves a `PROBE_SECONDS` timeout arriving at a probe
    looking exactly like a clean "logged out". Read as one, a hung keychain daemon
    prints `the OS keychain holds no token` and advises a login on a machine that
    may well be logged in. The deadline is per tool and `PROBES` holds several
    sharing this closure, so the cost multiplies on a resource whose whole
    constraint is being cheap enough to run unattended.

    `UNKNOWN` rather than `MISSING`, which is where `_uninstalled` and `_asked`'s
    unreadable-path guard already put a question that could not be asked: `sift`
    counts it unmeasured and keeps it out of the exit code. `diagnose.probed` splits
    the same two codes off the same `run` for the same reason.

    None where the command answered, whatever it answered — a non-zero exit from a
    binary that ran is the probe working.
    """
    if answer.returncode == TIMED_OUT:
        return Credential(Verdict.UNKNOWN, f'{tool} did not answer within {evidence.PROBE_SECONDS:g}s')
    if answer.returncode == NOT_FOUND:
        return Credential(Verdict.UNKNOWN, f'{tool} is on PATH but could not be executed')
    return None


def _data_home(session: Session) -> Path:
    """`$XDG_DATA_HOME`, or this session's home with the default under it.

    The variable rather than the session alone, because it is a real knob every
    tool here honours and a machine that sets it elsewhere would otherwise be read
    at a path nothing writes to.
    """
    declared = os.environ.get('XDG_DATA_HOME')
    return Path(declared) if declared else session.home / '.local' / 'share'


def _config_home(session: Session) -> Path:
    declared = os.environ.get('XDG_CONFIG_HOME')
    return Path(declared) if declared else session.home / '.config'


def _holds_something(path: Path) -> bool:
    """Whether a file exists and holds more than whitespace.

    Emptiness matters: `bbkt config init` writes the token file before anything
    puts a token in it, and `aws configure` leaves a credentials file behind when
    the profile it wrote is later removed. Both read as logged in on existence
    alone.

    Stripped rather than sized, which is `bbkt`'s own rule for the same file — it
    trims what it reads and refuses an empty result — so a file holding a bare
    newline reads the same way here as it does to the tool that owns it.

    Bytes rather than text. Decoding raises `UnicodeDecodeError`, which is a
    `ValueError` and so travels straight through the `OSError` guard in `_asked`,
    out of `observe` and into `auth could not be examined` — one stray byte in
    `~/.aws/credentials` costing every other tool its measurement. Three of the
    probes reach this call, and none of them interprets what it finds: the
    question is whether the file holds more than whitespace, which bytes answer.
    """
    return path.is_file() and bool(path.read_bytes().strip())


def _github(session: Session) -> Credential:
    """Read off the run's shared measurement rather than probed again.

    `evidence.have_github_credentials` already answers this for the resources that
    gate an install on it — `$GITHUB_TOKEN`, else `gh auth token` — so a probe of
    its own here would spend the cost twice for a verdict the run already holds,
    and two probes can disagree inside one report. It is also the cheap half of the
    pair: `gh auth status` validates the token against the API at 333ms, which is
    both slower and a network call.
    """
    if not shutil.which('gh') and not os.environ.get('GITHUB_TOKEN'):
        return _uninstalled('gh')
    if session.preconditions.github_auth:
        return Credential(Verdict.MATCHED, 'a credential is present')
    return Credential(Verdict.MISSING, 'no GITHUB_TOKEN, and `gh auth token` has nothing', advice=GITHUB_AUTH_ADVICE)


def _keychain_cli(tool: str) -> Probe:
    """A personal data CLI holding an Authelia token in the OS keychain.

    `auth status` rather than `auth token`, which inverts what `gh` wants and was
    measured rather than assumed. Status loads the token from the keychain and
    reports on it without making an HTTP call at all — `nomad/cli/internal/cli/auth.go`
    is the shared implementation, where logged out is `ErrNotLoggedIn` and exit 1 —
    so it is 4-5ms whichever state the machine is in. `auth token` refreshes, which
    costs 215ms on exactly the machine where the answer is yes.

    One closure for the four of them rather than four near-identical functions:
    they share a command set and an issuer, and a difference between them would be
    a difference worth seeing here rather than buried in a copy.
    """

    def probe(session: Session) -> Credential:
        if not shutil.which(tool):
            return _uninstalled(tool)
        answer = run([tool, 'auth', 'status'], output=Output.QUIET, timeout=evidence.PROBE_SECONDS)
        if answer.ok:
            return Credential(Verdict.MATCHED, answer.stdout.strip().splitlines()[0] if answer.stdout.strip() else 'logged in')
        if (unanswered := _unanswered(tool, answer)) is not None:
            return unanswered
        return Credential(Verdict.MISSING, 'the OS keychain holds no token', advice=f'log in with `{tool} auth login`')

    return probe


def _atuin_syncs(session: Session) -> bool:
    """Whether this machine's atuin config asks for a sync at all.

    `true` where the file is absent or will not parse, which is atuin's own
    default for the setting: a machine that never deployed a config still wants
    to hear that it is logged out, and a typo in the TOML must not silently
    answer the question it stopped this from reading.

    `ValueError` rather than `TOMLDecodeError`, which is the rest of this repo's
    idiom. `read_text` decodes, so one stray byte raises `UnicodeDecodeError` —
    also a `ValueError`, and one that travels straight through the `OSError`
    guard in `_asked` and costs every other tool its measurement.

    `ATUIN_CONFIG_DIR` is the knob atuin itself honours, and `atuin info` prints
    it, so a machine that moves the config is read where it actually keeps it.
    """
    declared = os.environ.get('ATUIN_CONFIG_DIR')
    directory = Path(declared) if declared else _config_home(session) / 'atuin'
    try:
        return bool(tomllib.loads((directory / 'config.toml').read_text()).get('auto_sync', True))
    except (OSError, ValueError):
        return True


def _atuin_session(session: Session) -> bool:
    """Whether atuin holds a sync token, asked of both places it has kept one.

    atuin 18 moved the token out of `~/.local/share/atuin/session` and into a
    `session` row in `meta.db`, leaving a `files_migrated` row beside it to mark
    the move. Measured 2026-08-15, straight after a `register` and a `sync` that
    both succeeded: the file is absent and the row is there. Reading the file
    alone reports a working login as missing forever, and the machine would be
    told to run the login it had just run — which is the upstream move this
    probe's own docstring predicted and the reason it says so.

    Read-only through a URI, so the probe can neither create the database it is
    asking about nor take a write lock on one atuin is mid-sync in. Any sqlite
    complaint is a no rather than a raise: `observe` guards `OSError` alone, and
    a locked store is a question that could not be asked rather than a resource
    that could not be examined.
    """
    if (_data_home(session) / 'atuin' / 'session').is_file():
        return True
    meta = _data_home(session) / 'atuin' / 'meta.db'
    if not meta.is_file():
        return False
    try:
        with contextlib.closing(sqlite3.connect(f'file:{meta}?mode=ro', uri=True)) as store:
            stored = store.execute("select value from meta where key = 'session'").fetchone()
    except sqlite3.Error:
        return False
    return bool(stored and stored[0])


def _atuin(session: Session) -> Credential:
    """The stored token, because `atuin status` reaches the sync server.

    `atuin status` measures 13ms on this box only because it is logged out and
    stops before the network; once a session exists it queries the server, so the
    one machine state where the answer is yes is the one that costs a round trip.
    There is no cheaper local answer, and `atuin status` is not a fallback.

    The one tool on the roster whose login is optional, so it is the one that
    asks whether a login is wanted before asking whether one is held. Everything
    else here cannot do its job logged out; atuin logged out is a local history
    store that still records, searches and answers `doit review` and `doit kit`
    about this machine. `UNKNOWN` for that case, which is where `_uninstalled` already
    puts a tool with nothing to log in to.
    """
    if not shutil.which('atuin'):
        return _uninstalled('atuin')
    if not _atuin_syncs(session):
        return Credential(Verdict.UNKNOWN, 'auto_sync is off, so history stays on this machine and no server holds an account')
    if _atuin_session(session):
        return Credential(Verdict.MATCHED, 'a sync session is stored')
    return Credential(Verdict.MISSING, 'no stored session, so nothing reaches the configured server', advice='log in with `atuin login`')


def _claude(session: Session) -> Credential:
    """The OAuth block in Claude Code's own credential file.

    `claude` exposes no auth verb to ask, so the file is the only local answer.
    It carries `mcpOAuth` beside the Claude login and a machine can hold one with
    no other, which is why the block is what is looked for rather than the file.

    Searched as bytes rather than parsed. A refresh rewrites this file, and a read
    landing mid-write raises `JSONDecodeError` — a `ValueError`, which travels
    straight through the `OSError` guard in `_asked` and costs every other tool
    its measurement, for a file that is whole again a second later. This is
    `_holds_something`'s reasoning applied to a file that happens to be JSON.
    """
    if not shutil.which('claude'):
        return _uninstalled('claude')
    if os.environ.get('ANTHROPIC_API_KEY'):
        return Credential(Verdict.MATCHED, 'ANTHROPIC_API_KEY is set')
    try:
        if b'claudeAiOauth' in (session.home / '.claude' / '.credentials.json').read_bytes():
            return Credential(Verdict.MATCHED, 'an OAuth session is stored')
    except OSError:
        pass
    return Credential(
        Verdict.MISSING,
        'no OAuth session and no ANTHROPIC_API_KEY',
        advice='run `claude` and complete the browser login',
    )


def _aws(session: Session) -> Credential:
    """Three places a credential can be, answered by stats rather than a round trip.

    `aws sts get-caller-identity` is the real answer and is 698ms and networked;
    `aws configure list` is 415ms of Python interpreter startup for something two
    stats decide. Neither is affordable on a scheduled check.

    Static keys, an SSO cache and the environment are genuinely three ways to be
    logged in rather than one fact spelled three ways, so all three are asked.
    """
    if not shutil.which('aws'):
        return _uninstalled('aws')
    if os.environ.get('AWS_ACCESS_KEY_ID'):
        return Credential(Verdict.MATCHED, 'AWS_ACCESS_KEY_ID is set')

    declared = os.environ.get('AWS_SHARED_CREDENTIALS_FILE')
    credentials = Path(declared) if declared else session.home / '.aws' / 'credentials'
    if _holds_something(credentials):
        return Credential(Verdict.MATCHED, f'{paths.under_home(credentials, session.home)} holds a profile')

    cache = session.home / '.aws' / 'sso' / 'cache'
    if cache.is_dir() and any(cache.iterdir()):
        return Credential(Verdict.MATCHED, 'an SSO session is cached')
    return Credential(
        Verdict.MISSING,
        'no credentials file, no SSO cache and no AWS_ACCESS_KEY_ID',
        advice='run `aws configure`, or `aws sso login` for an SSO profile',
    )


def _bbkt(session: Session) -> Credential:
    """`config path token`, which resolves locally; never `config check`.

    `bbkt config check` is the honest answer to "does this work" and says so in its
    own help — *connect to the instance and report who you are*. That makes it a
    round trip to an employer's Bitbucket from a check that runs on a timer,
    whether or not anyone is at the desk. `config path token` reads the config
    file and prints where the token would be, which honours a `token_file`
    override this repo has no business guessing at.
    """
    if not shutil.which('bbkt'):
        return _uninstalled('bbkt')
    if os.environ.get('BBKT_TOKEN'):
        return Credential(Verdict.MATCHED, 'BBKT_TOKEN is set')

    located = run(['bbkt', 'config', 'path', 'token'], output=Output.QUIET, timeout=evidence.PROBE_SECONDS)
    if (unanswered := _unanswered('bbkt', located)) is not None:
        return unanswered
    token = Path(located.stdout.strip()) if located.ok and located.stdout.strip() else None
    if token is not None and _holds_something(token):
        return Credential(Verdict.MATCHED, f'{paths.under_home(token, session.home)} holds a token')
    return Credential(Verdict.MISSING, 'no token file and no BBKT_TOKEN', advice='run `bbkt config init`, or set BBKT_TOKEN')


def _jira(session: Session) -> Credential:
    """The config `jira init` writes, or the token in the environment.

    The one path here taken from upstream convention rather than measured, because
    jira is declared by the work box alone. `jira init --help` and
    `eza -1a ~/.config/.jira/` settle it there in one line each, and
    `$JIRA_CONFIG_FILE` is honoured so a box that keeps it elsewhere reads correctly
    whatever the default turns out to be.

    `jira me` is the networked answer and is not used, for the reason every other
    probe here gives.
    """
    if not shutil.which('jira'):
        return _uninstalled('jira')
    if os.environ.get('JIRA_API_TOKEN'):
        return Credential(Verdict.MATCHED, 'JIRA_API_TOKEN is set')

    declared = os.environ.get('JIRA_CONFIG_FILE')
    config = Path(declared) if declared else _config_home(session) / '.jira' / '.config.yml'
    if _holds_something(config):
        return Credential(Verdict.MATCHED, f'{paths.under_home(config, session.home)} holds a configured account')
    return Credential(Verdict.MISSING, 'no jira config and no JIRA_API_TOKEN', advice='run `jira init`')


PROBES: dict[str, Probe] = {
    'gh': _github,
    'icb': _keychain_cli('icb'),
    'learning': _keychain_cli('learning'),
    'meso': _keychain_cli('meso'),
    'nomad': _keychain_cli('nomad'),
    'atuin': _atuin,
    'claude': _claude,
    'aws': _aws,
    'bbkt': _bbkt,
    'jira': _jira,
}
"""Every tool a manifest may name in its `auth:` list, and the local probe for it.

Asserted against the manifests in both directions: `validate.declaration` reports
a declared name with no probe, and `tests/resources/test_auth.py` reports a probe
no manifest declares — which validate structurally cannot ask, because a synthetic
tree can replace the manifests while the functions here are always the real ones.
"""


RESOURCE = AuthResource()
