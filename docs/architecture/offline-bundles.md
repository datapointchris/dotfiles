# Offline Bundles

A bundle is a tarball of installers, carried to a box that cannot fetch them
itself. This page is the arrangement between the two machines. Each end's own
half sits in its module: `src/dotfiles/create_bundle.py` builds one,
`src/dotfiles/offline_bundle.py` fetches and unpacks it, `src/dotfiles/paths.py`
classifies where it lands, and `src/dotfiles/providers/bundle.py` is the manifest
the two programs agree on.

`docs/reference/support/corporate.md` is the runbook. It carries both ends in
order: what to type where the network is, and what to type at the blocked box.

## Two machines and one exchange

The connected box has a network. The restricted box does not reach GitHub.
Everything here follows from those two facts and a third: the restricted box is
read-only with respect to the fleet, so the channel back has to be narrow enough
to describe in a sentence.

```text
  CONNECTED BOX                                  RESTRICTED BOX

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
                        apply --offline   unpacks the newest archive into
                              │           staged/<archive name>/, then reads
                              │           across the whole stack
                              ▼
  report download ◀──── report upload     what that apply decided and ran
        (pull)
```

Each round is planned against the last. The blocked box publishes what it has,
the builder leaves out everything already current, and the next bundle is
smaller than the one before it. A box that has never published gets everything.

## Each item is routed to the bundle or the network, so one apply converges the box

The restricted box is only partly blocked, and its config says which part:
`[network] blocked` lists the hosts it refuses. `src/dotfiles/routing.py` reads
the list once per run, from the deployed config or, on a first apply, from the
trust copy the symlink stage will deploy.

Every item reaches two kinds of host, and they are routed apart. The version
check asks one and the download fetches from another. A release tool on this
network asks `api.github.com` for its newest version and takes its bytes from the
bundle, because only the asset hosts are blocked. So it is measured against
upstream and installed from what the bundle carries. An item whose download
reaches no blocked host installs from the network, exactly as on an open one.

`registry.Provider.hosts` is the one answer to which hosts an item reaches. The
routing reads it, and so does `dotfiles network check` when it names the items a
declared host affects. A second table of hosts would let the two disagree about
one item.

*Rejected:* one `--offline` switch for the whole run. It sent every provider to
the bundle, so apt was never asked what was behind and no plugin was pulled,
though both answer on this network. Converging the box took a second, networked
apply that skipped the resources reaching blocked hosts.

`--offline` keeps the list and contacts no remote. Where no list is declared, it
counts every host as blocked, which is the only reading available to a box that
says nothing about its network.

## The apply unpacks; `bundle stage` is for looking first

An apply that routes any item to the bundle stages the newest archive it finds
for this machine. It skips the unpacking only when that archive is already among
the staged directories. So downloading and applying is the whole sequence, and a
bundle fetched to replace an out-of-date one takes effect on the next run.

With no archive anywhere the run goes on. Everything the network serves still
installs. An apply that may ask a builder asks for what the bundle would have
supplied. Otherwise each such item gets a row naming its blocked host and the
bundle it needs. The one exception is `--offline` with no list declared and no
request, where nothing could install, so the run refuses before measuring.

`bundle stage` unpacks without installing anything, which is what `bundle check`
and `bundle show` read. Reach for it to see what a bundle covers before letting
it change the machine, or to unpack a tarball carried across by hand from a path
the search does not reach.

A newer archive staged on top does not discard what is under it.
`src/dotfiles/providers/__init__.py` reads the stack newest first, so an older
full bundle still supplies everything a sparse one on top of it left out.

The read verbs stage nothing — a `check` that unpacked a tarball would be
writing. They say so instead: `plan --offline` and `check --offline` warn when an
archive on disk is newer than what they measured against.

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

Nothing written on a firewalled machine travels back, and that is the arrangement
this cuts through. The status document is the single hole in that seam. It stays narrow
because the code narrows it, not because somebody reads each one before it goes.

Two guards stand in front of it, and `src/dotfiles/publishing.py` is the account
of both — why an allowlist rather than a denylist, why a row carrying an
identifying name is withheld rather than the whole document refused, and why the
trust coordinate decides which names count.

## For go, cargo and winget the bundler is the only verifier

Four sections stage a GitHub asset — `github_releases`, `go_tools`,
`cargo_packages` and `winget_packages` — and `create_bundle.verify_against_upstream`
checks each download against the digest its release published. Only the first is
checked again when it installs. `providers/gotool.py`, `providers/cargo.py` and
`providers/winget.py` open what a bundle staged and install it, so a machine
unpacking a bundle takes those bytes on the builder's word.

That is why all four declare `checksum:` even though the field gates an install
for only one. `catalog.CHECKSUM_STATES` carries the vocabulary and what the
declaration is measured against; the decision recorded here is that a section
whose only verifier is the builder still declares, because an asset nobody can
verify is worth counting wherever it is staged.

The bundle's own `checksums.txt` cannot stand in for it. That file records the
digest of the file that was downloaded, and for an extracted binary or a repacked
tarball the downloaded file is not what the bundle carries.

## A restricted box requests its own bundle, and a builder answers on the same server

The file server has no push, so both ends poll it. A request and its two answers
live in `<root>/requests/<manifest>/`, and `src/dotfiles/bundle_requests.py`
owns their shapes.

An apply runs the restricted box's half itself, between its measure pass and its
walk. It asks for the entries `packages.bundle_need` names: blocked items missing
or behind that no staged bundle carries. Once the bundle is staged it measures
those resources again, so the same run installs them. It asks where
`request_bundle_when_blocked_items_are_behind` is on or `--request-bundle` is
given, and `--offline` alone never asks. `bundle request` is the same half with
no apply around it.

```text
  RESTRICTED BOX          REMOTE <root>/            BUILDER
  bundle request          (m = manifest)            bundle serve

  probe
  status upload ────────→ status/m/<file>
  write request ────────→ requests/m/<id>.json ◀─── poll every 20 s,
                                                    newest per m,
                                                    older deleted
                          <id>.building.json ◀───── acknowledge
                          status/m/<file> ────────→ download
                                                    bundle create
                                                     --against <file>
                                                     --entry ...
                          bundles/m/<archive> ◀──── upload, with a
                                                    record naming <id>
                          <id>.json, .building ◀─── delete
  poll every 15 s ◀────── record naming <id>
  download, verify,
  stage
```

**Who writes and who deletes.**

| File | Written by | Deleted by |
| --- | --- | --- |
| `<id>.json`, the request | restricted box | builder, after the upload, or when a newer request supersedes it |
| `<id>.building.json` | builder, before it starts | builder, with the request or on failure |
| `<id>.failed.json` | builder, when a build fails | builder, when a newer request supersedes it |

An id is `<UTC stamp>-<box>`, where the box is the discriminator a status
filename carries. The request names the exact status file, its machine, CPU,
dotfiles commit and entries. Naming the file is what keeps two boxes sharing a
manifest apart, which `--against latest` refuses to guess. The bundle's
`bundle.json` carries `request`, and that field is how the waiting box knows the
bundle is its own.

**Timings.** The builder polls every 20 seconds. The requester polls every 15,
warns after 2 minutes with no acknowledgement, and gives up after 15. The warning
names the `dotfiles-bundle-serve` unit and the manifest that enables it, through
`serve_bundles`. A timeout leaves the request in place, so a late builder still
answers it and `bundle download` collects the result.

**What goes wrong, and what each end says.**

- *No builder running.* No acknowledgement arrives. The requester names the unit
  at 2 minutes and stops at 15.
- *The build fails.* The builder writes `<id>.failed.json` with the error and the
  last 40 log lines, and the requester prints both and stops. The failed request
  is not retried. The box's next request supersedes it.
- *An entry the builder's checkout does not declare.* `bundle create --entry`
  refuses the name, which arrives as a failed marker. The usual cause is a builder
  checkout behind the requester's, and both commits are in the builder's log.
- *Another box sharing the manifest asks later.* Its request supersedes this one.
  The builder deletes the older request, and the requester reports that a newer
  request took its place.
- *The remote stops answering mid-wait.* Each end logs the poll that failed and
  keeps polling. The builder never exits on it, and its unit restarts it if it
  does.

`--entry` scopes a build to the named entries plus uv and the wheelhouse. The
rest of the plan is recorded as `left_out` rather than in `current`, because
`current` means measured on the target and these were only not asked for. A
scoped bundle is sparse, so it never becomes the base a stack reads through.

Each build writes a run record under the verb `bundle-build`, and its event log
holds the build's whole debug stream. `dotfiles report list` on the builder shows
them, and its journal carries the console lines.

## The automatic legs are off by default

Four `[remote]` settings close the loop with nothing typed: fetching a bundle,
publishing a status, publishing a run's record, and requesting a bundle when
blocked items are behind. All four default false.

Read that as one decision rather than four. The restricted network is what
decides it: the fault worth avoiding there is a machine reaching a server nobody
pointed it at. Each leg's module records what its own setting gates —
`src/dotfiles/reconcile.py`, `src/dotfiles/commands/status.py`,
`src/dotfiles/commands/report.py` and `src/dotfiles/bundle_requests.py`.

The nonfleet config turns the request on, because the box it serves cannot
download what its network blocks. The other three stay off there too.

## Related

- [Restricted Networks](../reference/support/corporate.md) — the runbook for both ends, in order
- [Observability](observability.md) — the interchange document this all rides on
- [GitHub Releases](github-releases.md) — how the assets a bundle carries are named
- [Management Interface](management-interface.md) — the verbs, and what `task` keeps for itself
