"""What belongs here rather than in `tests/matrix/`.

A resource is reached two ways: by the CLI verb a person types, and by the
function that verb calls. `tests/matrix/` asserts the first and is the default —
a property visible through `plan`, `check`, `apply` or `--json` is a row in one
of its tables, and asserting it here as well leaves this copy to go stale behind
the table.

**A test earns a place here by needing something the front door cannot show.**
There are four of those, and they are the whole list:

- a real subprocess argv — which command a probe actually ran, not that it ran
- an internal field no verb prints — `consulted_network`, `Outcome.status`,
  `Change.observed`, `Change.repair`, `Change.actionable`
- the real repo declaration, where the claim is about this repo's own
  `packages.yml`, `flags.yml` or manifests rather than a synthetic one
- a patched module constant, such as `auth.evidence.PROBE_SECONDS`

A test asserting nothing but an exit code and a `--json` field is at the wrong
altitude and belongs in a matrix table.

No fixtures live here yet. The file is the directory's own, and this is the note
that decides what lands in it.
"""

from __future__ import annotations
