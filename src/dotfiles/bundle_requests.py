"""The request a restricted box leaves for a builder, and the builder's two answers.

The file server has no push, so both ends poll one directory per manifest,
`<root>/requests/<manifest>/`:

- `<id>.json` is the request. The restricted box writes it after publishing its
  status, and the builder deletes it once the bundle is uploaded.
- `<id>.building.json` is the builder's acknowledgement, written before it starts
  and deleted with the request.
- `<id>.failed.json` is the builder's failure, carrying the error and the tail of
  the build's log. It stays until a newer request supersedes the one it answers.

The bundle's own record names the request id, which is how the requester tells
its bundle from any other on the shelf. `docs/architecture/offline-bundles.md`
holds the timings and the failure modes.
"""

from __future__ import annotations

import collections
import dataclasses as dc
import datetime as dt
import json
import logging as stdlib_logging
import os
import tempfile
import time
from collections.abc import Callable
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from dotfiles import checkout
from dotfiles import coordinates as axes
from dotfiles import create_bundle
from dotfiles import logging
from dotfiles import machine as machines
from dotfiles import offline_bundle
from dotfiles import output
from dotfiles import paths
from dotfiles import publishing
from dotfiles import remote as transport
from dotfiles import runs
from dotfiles import sinks
from dotfiles import status as status_document
from dotfiles.refusal import Refusal
from dotfiles.resources import OutcomeStatus
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode

log = logging.get_logger('bundle-requests')

REQUEST_SUFFIX = '.json'
BUILDING_SUFFIX = '.building.json'
FAILED_SUFFIX = '.failed.json'

REQUEST_POLL_SECONDS = 15
SERVE_POLL_SECONDS = 20
ACKNOWLEDGE_DEADLINE_SECONDS = 120
REQUEST_TIMEOUT_SECONDS = 15 * 60
STILL_WAITING_EVERY_SECONDS = 60
LOG_TAIL_LINES = 40

SERVE_UNIT = 'dotfiles-bundle-serve.service'
SERVE_FEATURE = 'serve_bundles'
"""The manifest boolean that installs `SERVE_UNIT`, so the advice can name the builder's manifest."""

BUILD_VERB = 'build'
"""The verb a build's run record is filed under, one of `vocabulary.RECORDED_VERBS`, so `dotfiles report list` shows each build."""


class MalformedRequest(Refusal):
    """A file on the requests shelf that does not parse as what its name says it is."""


@dc.dataclass(frozen=True, slots=True)
class Request:
    id: str
    machine: str
    arch: str
    status: str
    """The exact status filename on the status shelf, so two boxes sharing a manifest cannot be confused."""
    requested_at: str
    dotfiles_commit: str
    entries: tuple[str, ...] = ()
    """The entry names wanted. Empty asks for every bundled entry the status shows behind."""

    @property
    def filename(self) -> str:
        return f'{self.id}{REQUEST_SUFFIX}'

    def as_dict(self) -> dict[str, Any]:
        return {**dc.asdict(self), 'entries': list(self.entries)}


def request_from(document: Any) -> Request:
    if not isinstance(document, dict):
        raise MalformedRequest(f'a request is a JSON object, and this is a {type(document).__name__}')
    missing = [field.name for field in dc.fields(Request) if field.name != 'entries' and not isinstance(document.get(field.name), str)]
    if missing:
        raise MalformedRequest(f'the request carries no {", ".join(missing)}')
    unsafe = [name for name in ('id', 'status') if not bare_filename(document[name])]
    if unsafe:
        raise MalformedRequest(f'the request names its {", ".join(unsafe)} as a path rather than a filename')
    entries = document.get('entries') or []
    if not isinstance(entries, list) or not all(isinstance(name, str) for name in entries):
        raise MalformedRequest('the request names its entries as something other than a list of strings')
    return Request(**{field.name: document[field.name] for field in dc.fields(Request) if field.name != 'entries'}, entries=tuple(entries))


def bare_filename(value: str) -> bool:
    """Whether `value` names a file in one directory, so joining it onto another stays there.

    A request's `id` names the builder's files on the remote and its `status` the
    local file the status lands in. Anyone holding the remote's token can write a
    request, and an absolute path discards the prefix it is joined onto.
    """
    return value not in ('', '.', '..') and Path(value).name == value


@dc.dataclass(frozen=True, slots=True)
class Acknowledgement:
    request: str
    started_at: str
    builder: str
    pid: int


@dc.dataclass(frozen=True, slots=True)
class Failure:
    request: str
    failed_at: str
    builder: str
    error: str
    log_tail: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {**dc.asdict(self), 'log_tail': list(self.log_tail)}


@dc.dataclass(frozen=True, slots=True)
class Shelf:
    """One manifest's request directory, sorted by what each file is."""

    requests: tuple[str, ...]
    """Request ids, oldest first. An id leads with its UTC stamp, so text order is time order."""
    building: frozenset[str]
    failed: frozenset[str]


def shelf_of(names: Sequence[str]) -> Shelf:
    requests: list[str] = []
    building: set[str] = set()
    failed: set[str] = set()
    for name in names:
        if name.endswith(BUILDING_SUFFIX):
            building.add(name.removesuffix(BUILDING_SUFFIX))
        elif name.endswith(FAILED_SUFFIX):
            failed.add(name.removesuffix(FAILED_SUFFIX))
        elif name.endswith(REQUEST_SUFFIX):
            requests.append(name.removesuffix(REQUEST_SUFFIX))
    return Shelf(tuple(sorted(requests)), frozenset(building), frozenset(failed))


def now() -> str:
    return runs.stamp(dt.datetime.now(dt.UTC).replace(microsecond=0))


def put(where: transport.Remote, directory: str, name: str, document: dict[str, Any]) -> None:
    with tempfile.TemporaryDirectory() as workspace:
        local = Path(workspace) / name
        local.write_text(json.dumps(document, indent=2) + '\n')
        transport.push(where, local, directory)


def read_object(where: transport.Remote, directory: str, name: str) -> dict[str, Any]:
    """One file from the shelf as a JSON object, or `MalformedRequest` where it is not one.

    Read the same way by both halves. A file another box wrote may be half uploaded
    or hand edited, and neither may end the run that reads it.
    """
    with tempfile.TemporaryDirectory() as workspace:
        pulled = transport.pull(where, f'{directory}/{name}', Path(workspace) / name, timeout=transport.SMALL_OPERATION_SECONDS)
        try:
            document = json.loads(pulled.read_text())
        except ValueError as unreadable:
            raise MalformedRequest(f'{name} on the remote is not JSON: {unreadable}') from unreadable
    if not isinstance(document, dict):
        raise MalformedRequest(f'{name} on the remote is a JSON {type(document).__name__}, not an object')
    return document


def dotfiles_commit() -> str:
    found = checkout.git(paths.REPO_ROOT, 'rev-parse', '--short=12', 'HEAD')
    return found.stdout.strip() if found.ok else ''


# ─────────────────────────────────────────────────────────────────────────────
# The restricted box
# ─────────────────────────────────────────────────────────────────────────────


def obtain_bundle(machine: str | None, entries: Sequence[str]) -> Path | None:
    """Ask a builder for a bundle carrying `entries`, wait for it, then download, verify and stage it.

    Returns the archive it staged, or None once the output has said why there is
    none: the remote did not answer, the builder failed, a newer request took this
    one's place, or nothing arrived within `REQUEST_TIMEOUT_SECONDS`.
    """
    try:
        return requested_and_staged(machine, tuple(sorted(set(entries))))
    except Refusal as refused:
        said(f'no bundle was obtained: {refused}', warning=True)
        if refused.advice:
            pointed(refused.advice)
        return None


def refuse_unbundled(machine: str | None, entries: Sequence[str]) -> None:
    """Refuse an entry this machine's plan bundles nothing under, before anything reaches the remote.

    The builder refuses the same names the same way, after a status upload and
    a wait. `create_bundle.left_out_of` is the one judge for both ends.
    """
    try:
        create_bundle.left_out_of(Session.resolve(machine).plan, tuple(entries))
    except create_bundle.BundleError as refused:
        raise Refusal(str(refused), code=ExitCode.USAGE) from refused


def said(message: str, *, warning: bool = False) -> None:
    """One step on the restricted box's side, as a line of the run's output and of its log file.

    Debug in the file, so the console sink does not print it a second time beside
    the rendered line.
    """
    if warning:
        log.debug(message, warning=True)
        output.warn(message)
        return
    log.debug(message)
    output.render_note(message)


def pointed(advice: str) -> None:
    """What to do next, as the run's advice line and a line of its log file."""
    log.debug(advice)
    output.hint(advice)


def requester(*, offline: bool, forced: bool) -> Callable[[str | None, Sequence[str]], Path | None] | None:
    """`obtain_bundle` where an apply may ask a builder for what it is missing, or None.

    `--request-bundle` always may, `--offline` included. Otherwise the box's config
    decides, and `--offline` never reaches the remote on its own.
    """
    if forced:
        return obtain_bundle
    if offline:
        return None
    found = transport.read()
    if found.remote is None or not found.remote.request_bundle_when_blocked_items_are_behind:
        return None
    return obtain_bundle


def requested_and_staged(machine: str | None, entries: tuple[str, ...]) -> Path | None:
    where = transport.reachable()
    said(f'the remote at {where.root} answers')

    session = Session.resolve(machine)
    named = session.machine_name
    box = publishing.discriminator(session.machine.coordinates.network_trust)
    published = status_document.publish(where, machine)
    said(f'published status {published.name}')

    request = Request(
        id=f'{dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")}-{box}',
        machine=named,
        arch=str(axes.detect_arch()),
        status=published.name,
        requested_at=now(),
        dotfiles_commit=dotfiles_commit(),
        entries=entries,
    )
    directory = transport.requests_for(where, named)
    already_listed = set(offline_bundle.on_remote(where, named))
    put(where, directory, request.filename, request.as_dict())
    wanted = ', '.join(entries) if entries else 'every bundled entry this status shows behind'
    said(f'sent request {request.id} for {wanted} to {directory}')

    record = waited_for(where, request, already_listed)
    if record is None:
        return None
    said('downloading it')
    archive = offline_bundle.fetch(where, named, record.name, record)
    said(f'verified it against its record, sha256 {record.sha256[:12] or "unpublished"}')
    staged = offline_bundle.stage(archive, named, box)
    said(f'staged at {paths.under_home(staged)}')
    return archive


def waited_for(where: transport.Remote, request: Request, already_listed: set[str]) -> offline_bundle.Record | None:
    """Poll until a bundle names this request, the builder fails it, or time runs out.

    A bundle on the shelf answers before a failed marker does: a builder that
    uploaded and then could not tidy up still built it. With no acknowledgement by
    `ACKNOWLEDGE_DEADLINE_SECONDS` no builder is running, so the wait stops there
    rather than holding the apply for `REQUEST_TIMEOUT_SECONDS`.
    """
    directory = transport.requests_for(where, request.machine)
    began = time.monotonic()
    acknowledged: Acknowledgement | None = None
    said_waiting = 0.0

    while time.monotonic() - began < REQUEST_TIMEOUT_SECONDS:
        time.sleep(REQUEST_POLL_SECONDS)
        waited = time.monotonic() - began
        try:
            found = shelf_of(transport.listed(where, directory) or ())
            answered = answering(where, request.machine, request.id, already_listed)
            if answered is not None:
                if acknowledged is None:
                    said('a builder acknowledged and built it between two polls')
                said(f'bundle listed: {answered.name}')
                return answered
            if request.id in found.failed:
                failure = read_object(where, directory, f'{request.id}{FAILED_SUFFIX}')
                said(
                    f'{failure.get("builder", "the builder")} could not build request {request.id}: {failure.get("error", "")}',
                    warning=True,
                )
                tail = failure.get('log_tail')
                for line in tail if isinstance(tail, list) else []:
                    said(f'  {line}')
                pointed('fix what the error names, then run: dotfiles bundle request')
                return None
            if acknowledged is None and request.id in found.building:
                document = read_object(where, directory, f'{request.id}{BUILDING_SUFFIX}')
                acknowledged = Acknowledgement(**{field.name: document.get(field.name, '') for field in dc.fields(Acknowledgement)})
                said(f'{acknowledged.builder} acknowledged it at {acknowledged.started_at} and is building')
            if request.id not in found.requests:
                said(f'request {request.id} left the remote with no bundle answering it, so a newer request took its place', warning=True)
                return None
        except transport.RemoteError as unanswered:
            said(f'the remote did not answer this poll, still waiting: {unanswered}', warning=True)
            continue
        except MalformedRequest as unreadable:
            said(f'{unreadable}, so the next poll reads it again', warning=True)
            continue

        if acknowledged is None and waited >= ACKNOWLEDGE_DEADLINE_SECONDS:
            minutes = ACKNOWLEDGE_DEADLINE_SECONDS // 60
            said(f'no builder acknowledged request {request.id} within {minutes} minutes, so this run stops waiting', warning=True)
            said(f'the builder is the {SERVE_UNIT} user unit on the machine running the {builder_manifests()} manifest')
            said('the request stays on the remote, so a builder that starts later still answers it')
            pointed(f'check it there: systemctl --user status {SERVE_UNIT}; journalctl --user -u {SERVE_UNIT}')
            return None
        if waited - said_waiting >= STILL_WAITING_EVERY_SECONDS:
            said(f'still {"building" if acknowledged else "waiting for a builder"}, {int(waited) // 60}m{int(waited) % 60:02d}s in')
            said_waiting = waited

    said(f'no bundle answered request {request.id} within {REQUEST_TIMEOUT_SECONDS // 60} minutes', warning=True)
    said('the request stays on the remote, so the builder can still answer it')
    pointed('collect it later: dotfiles bundle list, then dotfiles bundle download; or ask again: dotfiles bundle request')
    return None


def builder_manifests() -> str:
    """Every manifest that turns `SERVE_FEATURE` on, as one phrase."""
    named = []
    for name in machines.names():
        try:
            if machines.load(name).wants(SERVE_FEATURE):
                named.append(name)
        except machines.MachineError:
            continue
    return ' or '.join(named) or f'(none: no manifest sets {SERVE_FEATURE})'


def answering(where: transport.Remote, machine: str, request_id: str, already_listed: set[str]) -> offline_bundle.Record | None:
    """The record of a bundle that answers this request, reading only archives new since it was sent.

    An archive is uploaded before its record, so one listed with no record yet is
    read again on the next poll rather than set aside as somebody else's.
    """
    shelf = transport.bundles_for(where, machine)
    for name in offline_bundle.on_remote(where, machine):
        if name in already_listed:
            continue
        record = offline_bundle.record_on_remote(where, shelf, name)
        if not record.sha256:
            continue
        already_listed.add(name)
        if record.description.request == request_id:
            return record
    return None


# ─────────────────────────────────────────────────────────────────────────────
# The builder
# ─────────────────────────────────────────────────────────────────────────────


class LogTail(stdlib_logging.Handler):
    """The last lines a build logged, for the failed marker."""

    def __init__(self) -> None:
        super().__init__(level=stdlib_logging.INFO)
        self.lines: collections.deque[str] = collections.deque(maxlen=LOG_TAIL_LINES)

    def emit(self, record: stdlib_logging.LogRecord) -> None:
        message = record.msg.get('event', '') if isinstance(record.msg, dict) else record.getMessage()
        self.lines.append(f'{record.name}: {message}')


def serve(once: bool) -> bool:
    """Answer requests every `SERVE_POLL_SECONDS`, or in one pass under `once`. False when a build failed.

    The loop returns True once the checkout's HEAD moves. Its unit restarts on any
    exit, so the next build runs on the code an update pulled rather than the
    modules this process imported.
    """
    where = transport.require()
    if not where.transport.declares(transport.Operation.DELETE):
        raise transport.RemoteError(
            'bundle serve deletes each request it answers, and no remote.transport.delete is declared',
            advice='declare delete in the [remote.transport] table of config.toml',
        )
    started_on = dotfiles_commit()
    log.info(
        f'serving bundle requests under {where.directory(transport.REQUESTS)} as {paths.machine_id()}, '
        f'every {SERVE_POLL_SECONDS}s, on dotfiles commit {started_on or "(unknown)"}'
    )
    finished_here: set[str] = set()
    while True:
        if not once and (moved_to := dotfiles_commit()) != started_on:
            log.info(f'the checkout moved from {started_on} to {moved_to}, so this process exits for its unit to restart it')
            return True
        try:
            clean = serve_pass(where, finished_here)
        except transport.RemoteError as unanswered:
            log.warning(f'the remote did not answer this pass: {unanswered}')
            clean = False
        if once:
            return clean
        time.sleep(SERVE_POLL_SECONDS)


def serve_pass(where: transport.Remote, finished_here: set[str]) -> bool:
    """Build each box's newest request on every manifest's shelf, deleting the ones it supersedes.

    `finished_here` holds the requests this process built or failed. A request the
    remote would not let it remove, or whose failed marker it refused, then stays
    on the shelf without being built again on every pass. It also holds each
    directory refused for naming no manifest, so the refusal is logged once.
    """
    manifests = transport.listed(where, where.directory(transport.REQUESTS)) or ()
    declared = set(machines.names())
    clean = True
    for machine in sorted(name.rstrip('/') for name in manifests):
        if machine not in declared:
            if machine not in finished_here:
                log.warning(f'{transport.REQUESTS}/{machine} names no manifest this checkout declares, so its requests are left alone')
                finished_here.add(machine)
            continue
        directory = transport.requests_for(where, machine)
        found = shelf_of(transport.listed(where, directory) or ())
        newest = {box_of(request_id): request_id for request_id in found.requests}
        for old in found.requests:
            if old == newest[box_of(old)]:
                continue
            log.info(f'request {old} for {machine} is superseded by {newest[box_of(old)]}, deleting it')
            for suffix, present in ((REQUEST_SUFFIX, True), (BUILDING_SUFFIX, old in found.building), (FAILED_SUFFIX, old in found.failed)):
                if present:
                    transport.remove(where, f'{directory}/{old}{suffix}')
        for request_id in sorted(newest.values()):
            if request_id in found.failed or request_id in finished_here:
                continue
            clean = answer(where, machine, request_id) and clean
            finished_here.add(request_id)
    return clean


def box_of(request_id: str) -> str:
    """The box a request id names after its UTC stamp, so one box's request supersedes only its own."""
    return request_id.partition('-')[2]


def answer(where: transport.Remote, machine: str, request_id: str) -> bool:
    """Acknowledge, build and upload one request, or leave a failed marker saying why."""
    directory = transport.requests_for(where, machine)
    identity = runs.begin(machine, BUILD_VERB)
    sinks.open_log(identity)
    tail = LogTail()
    stdlib_logging.root.addHandler(tail)
    record = runs.start(identity, {'request': request_id})
    watch = runs.Stopwatch()
    try:
        request = request_from(read_object(where, directory, f'{request_id}{REQUEST_SUFFIX}'))
        if request.id != request_id:
            raise MalformedRequest(f'{request_id}{REQUEST_SUFFIX} names itself {request.id}')
        record.flags.update({'status': request.status, 'entries': list(request.entries), 'arch': request.arch})
        acknowledgement = Acknowledgement(request.id, now(), paths.machine_id(), os.getpid())
        put(where, directory, f'{request.id}{BUILDING_SUFFIX}', dc.asdict(acknowledgement))
        log.info(f'acknowledged request {request.id} for {machine}, asked for {", ".join(request.entries) or "every bundled entry"}')
        log.info(
            f'the request was made at dotfiles commit {request.dotfiles_commit or "(unknown)"}, '
            f'and this checkout is at {dotfiles_commit() or "(unknown)"}'
        )

        with watch.step('fetch'):
            status = transport.pull(
                where, f'{transport.statuses_for(where, machine)}/{request.status}', paths.status_cache() / request.status
            )
        log.info(f'downloaded status {request.status}')

        with watch.step('act'):
            archive = create_bundle.build(
                machine, request.arch, use_cache=True, against=status, entries=request.entries, request=request.id
            )
            offline_bundle.publish(where, archive)
        log.info(f'uploaded {archive.name} and its record to {transport.bundles_for(where, machine)}')

        try:
            transport.remove(where, f'{directory}/{request.filename}')
            transport.remove(where, f'{directory}/{request.id}{BUILDING_SUFFIX}')
        except transport.RemoteError as untidy:
            log.warning(f'the bundle is uploaded, and request {request.id} could not be removed from the remote: {untidy}')
        log.info(f'answered request {request.id}')
        record.record_outcome(f'bundle-request/{request_id}', 'built', str(OutcomeStatus.DONE), watch.finish(), archive.name)
        return True
    except Exception as failed:
        log.error(f'request {request_id} for {machine} failed: {failed}')
        record.record_outcome(f'bundle-request/{request_id}', 'failed', str(OutcomeStatus.FAILED), watch.finish(), str(failed))
        record.record_issue(f'bundle-request/{request_id}', str(OutcomeStatus.FAILED), str(failed))
        failure = Failure(request_id, now(), paths.machine_id(), str(failed), tuple(tail.lines))
        try:
            put(where, directory, f'{request_id}{FAILED_SUFFIX}', failure.as_dict())
            transport.remove(where, f'{directory}/{request_id}{BUILDING_SUFFIX}')
        except transport.RemoteError as unwritten:
            log.error(f'the failure could not be left on the remote either: {unwritten}')
        return False
    finally:
        stdlib_logging.root.removeHandler(tail)
        try:
            runs.write(runs.finish(record), latest_follows=False)
        except OSError as unwritten:
            log.warning(f'the run record for request {request_id} was not written: {unwritten}')
        logging.configure()
        logging.clear_run()
