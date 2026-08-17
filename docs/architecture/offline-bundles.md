# Offline Bundles

A bundle is a tarball of installers, carried to a box that cannot fetch them
itself. This page is the arrangement between the two machines. Each end's own
half sits in its module: `src/dotfiles/create_bundle.py` builds one,
`src/dotfiles/offline_bundle.py` fetches and unpacks it, `src/dotfiles/paths.py`
classifies where it lands, and `src/dotfiles/providers/bundle.py` is the manifest
the two programs agree on.

`docs/reference/support/corporate.md` is the runbook — what to type, in order.

## Two machines and one exchange

The personal box has a network. The work box does not reach GitHub. Everything
here follows from those two facts and a third: the work box is read-only with
respect to the personal fleet, so the channel back has to be narrow enough to
describe in a sentence.

```text
  PERSONAL BOX                                      WORK BOX

  status download ──┐                     ┌── status show   packages, toolchains
        (pull)      │                     │        │
                    │                     │        ▼
                    │                     │   redaction gate ── withholds the row,
                    ▼                     │        │            refuses the rest
  bundle create --against <status>        └── status upload
        │                                          ▲
        │  resolve upstream for every item         │
        │  omit what the status already has ───────┘
        ▼        record it in bundle.json
  bundle upload ──────────────┐
                              ▼
                        bundle download   confirm, sha256, into the cache
                              │
                              ▼
                        bundle stage      staged/<archive name>/
                              │
                              ▼
                        apply --offline   providers read across the stack
```

Each round is planned against the last. The blocked box publishes what it has,
the builder leaves out everything already current, and the next bundle is
smaller than the one before it. A box that has never published gets everything.

## A machine declares its transport, and every call runs with stdin closed

A machine names a transport program and its argv templates in
`~/.config/dotfiles/config.toml`. `src/dotfiles/remote.py` holds the keys, and
why that table stays a document rather than a program.

Write each template with whatever flag makes the program answer without a
terminal. Nothing here can supply one — `src/dotfiles/effects.py` closes stdin
for every child it runs. `ifiles` refuses an unconfirmed delete on closed stdin,
so a `delete` template written without `--force` leaves retention reported and
never performed.

## What travels back is packages, toolchains, and nothing else

`~/dev/workstations.md` § "The seam between them" is the arrangement this cuts
through. The status document is the single hole in that seam. It stays narrow
because the code narrows it, not because somebody reads each one before it goes.

Two guards stand in front of it, and `src/dotfiles/publishing.py` is the account
of both — why an allowlist rather than a denylist, why a row carrying an
identifying name is withheld rather than the whole document refused, and why the
trust coordinate decides which names count.

## The automatic legs are off by default

Three `[remote]` settings close the loop with nothing typed: fetching a bundle,
publishing a status, publishing a run's record. All three default false.

Read that as one decision rather than three. The employer network is what
decides it: the fault worth avoiding there is a machine reaching a server nobody
pointed it at. Each leg's module records what its own setting gates —
`src/dotfiles/reconcile.py`, `src/dotfiles/commands/status.py` and
`src/dotfiles/commands/report.py`.

## Related

- [Restricted Networks](../reference/support/corporate.md) — the runbook, in order
- [Observability](observability.md) — the interchange document this all rides on
- [GitHub Releases](github-releases.md) — how the assets a bundle carries are named
- [Management Interface](management-interface.md) — the verbs and the two front doors
