"""The signed push that starts a builder once a request is on the file server.

The file server offers no upload hook, so uploading a request wakes nothing. The
box follows the upload with one POST to `[remote].request_hook_url`, carrying only
the request's id. The request itself stays on the file server. The body is signed
the way GitHub signs a webhook, so any webhook receiver can check it, and what
answers at that URL is not this tool's to know.

A push only shortens the wait. The builder's scheduled pass answers a request whose
push never arrived, so nothing here retries and nothing here fails a run. A box
behind a monitored egress pushes once per real request, because a repeating call
reads as a beacon.

The secret sits in a 0600 file under this tool's state. It never reaches an
argument, the environment, a log line or git.
"""

from __future__ import annotations

import dataclasses as dc
import hashlib
import hmac
import json
import os
import tempfile
from enum import StrEnum
from pathlib import Path

import httpx2

from dotfiles import github_release
from dotfiles import paths

SECRET_FILENAME = 'remote-hook-secret'
SIGNATURE_HEADER = 'X-Hub-Signature-256'
NO_REQUEST = ''
"""The id a signed no-op carries, which `remote check` sends so a receiver starts nothing."""

PUSH_TIMEOUT_SECONDS = 60
"""The receiver answers once its own script has ended, which is usually about a second."""

ANSWER_CHARACTERS = 200

SIGNATURE_REFUSAL = 'hook rules'
"""What webhook receivers say when a hook's rules refuse a request.

A wrong signature answers `Error occurred while evaluating hook rules.`, or `Hook
rules were not satisfied.` while the receiver holds two secrets during a rotation.
The script's own failures never say it, so this tells a wrong secret from a broken hook.
"""

STORE_SECRET = 'place the secret: dotfiles remote hook-secret set'


class Answer(StrEnum):
    """What came of one push, so a caller reads a value rather than a sentence."""

    TOOK = 'took'
    NO_SECRET = 'no-secret'
    WRONG_SECRET = 'wrong-secret'
    REFUSED = 'refused'
    """The signature was good, and the receiver's script could not start the work."""

    UNREACHED = 'unreached'


@dc.dataclass(frozen=True, slots=True)
class Push:
    answer: Answer
    detail: str
    status: int = 0
    advice: str = ''


def secret_path() -> Path:
    return paths.STATE_HOME / SECRET_FILENAME


def held_secret() -> str:
    """The secret's text, or '' where this box holds none it can read."""
    try:
        return secret_path().read_text().strip()
    except OSError:
        return ''


def store_secret(value: str) -> Path:
    """Write the secret by rename, from a file `mkstemp` creates at 0600, so no reader meets a wider or partial one."""
    where = secret_path()
    where.parent.mkdir(parents=True, exist_ok=True)
    handle, staged = tempfile.mkstemp(dir=str(where.parent), prefix=f'.{where.name}.')
    try:
        with os.fdopen(handle, 'w') as target:
            target.write(f'{value}\n')
        os.replace(staged, where)
    except BaseException:
        Path(staged).unlink(missing_ok=True)
        raise
    return where


def signed(secret: str, body: bytes) -> str:
    return f'sha256={hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()}'


def push(url: str, request_id: str) -> Push:
    """One signed POST naming `request_id`, with whatever came of it as a value and never an exception."""
    secret = held_secret()
    if not secret:
        return Push(Answer.NO_SECRET, f'this box holds no secret at {paths.under_home(secret_path())}', advice=STORE_SECRET)

    body = json.dumps({'request': request_id}).encode()
    headers = {'Content-Type': 'application/json', 'User-Agent': github_release.USER_AGENT, SIGNATURE_HEADER: signed(secret, body)}
    try:
        answered = httpx2.post(url, content=body, headers=headers, timeout=PUSH_TIMEOUT_SECONDS)
    except httpx2.HTTPError as unreached:
        return Push(Answer.UNREACHED, f'{url} did not answer: {unreached}')

    spoken = answered.text.strip()[:ANSWER_CHARACTERS]
    if answered.is_success:
        return Push(Answer.TOOK, spoken, answered.status_code)
    if SIGNATURE_REFUSAL in spoken.lower():
        return Push(
            Answer.WRONG_SECRET,
            f'the hook refused this signature, so the secret at {paths.under_home(secret_path())} is wrong',
            answered.status_code,
            STORE_SECRET,
        )
    return Push(Answer.REFUSED, f'the hook answered {answered.status_code}: {spoken}', answered.status_code)
