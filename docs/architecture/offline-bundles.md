# Offline Bundles

A bundle carries every installer a machine needs to converge with no network. It
is built where the network is, for a machine that is not the one building it, and
this page is about how it gets there and back.

`docs/reference/support/corporate.md` is the runbook — what to type, in order.
This is why each piece is shaped the way it is.

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
                    │                     │   redaction gate ── refuses on
                    ▼                     │        │            hostname / account
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

## The transport is a program this repo never names

A machine declares one in `~/.config/dotfiles/config.toml` and dotfiles builds an
argv from the templates beside it. The credential, the protocol and the retry
behaviour stay owned by the CLI that owns them.

```toml
[remote]
root = "/dotfiles"
keep = 5
fetch_bundle_when_none_is_staged = false
publish_status_after_offline_apply = false

[remote.transport]
program  = "ifiles"
probe    = ["auth", "status"]
list     = ["list", "{dir}"]
upload   = ["upload", "{local}", "{dir}"]
download = ["download", "{remote}", "{local}"]
mkdir    = ["mkdir", "{dir}"]
delete   = ["delete", "{remote}"]
```

**The whole contract is that `list` prints one name per line on stdout.** There is
no JSON dialect and no field mapping, because everything needed to rank a bundle
and describe it is in the name and in the small record uploaded beside it. That is
what keeps the table a document rather than a program: a fixed argv with one
substituted placeholder carries no conditional, no reference between keys, and no
evaluation order.

`root` has no compiled-in default and cannot have one — a default naming a path on
somebody's server is a fact this repo does not own. A machine that declares
nothing has no remote, which is the ordinary state of every box that never
exchanges a bundle.

`mkdir` and `delete` are optional. Without `mkdir`, a push into a directory that
does not exist refuses rather than letting the transport invent a path where no
`list` will ever find the result. Without `delete`, retention is reported and
never performed.

Keys are checked, and an unknown one is named. TOML sections are positional, so a
key written after `[remote.transport]` belongs to *that* table — which is how a
machine comes to have an automatic path silently off with nothing saying so.

## What a bundle is, and what it carries, are two files

`manifest.txt` lists the files. `bundle.json` says what the bundle *is*: when it
was built, which machine for, whether it is full or sparse, and — when sparse —
what it measured and deliberately left out.

They carry disjoint facts on purpose. The created-at and platform headers used to
live in `manifest.txt` and moved, rather than being written in both.

```json
{
  "version": 1,
  "created": "2026-09-01T07:30:00Z",
  "machine": "wsl-work-workstation",
  "platform": "linux/x86_64",
  "completeness": "sparse",
  "built_from": "dotfiles-status-v20260901T0700Z-wsl-work-workstation-4f2a91c3.json",
  "current": { "binary/bat": "v0.26.0", "go-binary/task": "v3.46.0" }
}
```

### An absence means three different things

This is the reason `bundle.json` exists at all. A bundle that carries fewer files
and a bundle that failed to carry more are indistinguishable from the rows alone,
and reading the first as the second reports a working machine as missing most of
itself.

| Entry | In `manifest.txt` | In `current` | What an offline run decides |
| --- | --- | --- | --- |
| carried | yes | no | install it from the staged bundle |
| already current | no | yes | matched, at the version in `current` |
| never measured | no | no | unknown, and it says why |

The third row is the one that has to exist. It means the declaration gained that
tool after the status the bundle was planned from was taken, so nothing has ever
measured it — and calling it current would be a guess.

A full bundle writes `completeness: "full"` and no `current`, so an absence there
keeps the meaning it always had. An absent or unreadable `bundle.json` reads as
full, which is the conservative answer: full reports a gap where sparse would
pass one silently.

**Nothing new decides any of this.** `resources/packages.py` reads the manifest
for what the bundle brought and `current` for what it measured, and both are the
bundle answering the one question an offline run asks: what did upstream publish.
The three verdicts fall out of the comparison that was already there.

## A staged bundle is a stack, not a merge

Each archive unpacks into `$XDG_CACHE_HOME/dotfiles/staged/<archive name>/`, and
`providers.locate` walks them newest first. The newest bundle carrying a file
answers for it; an older one still answers for everything the newer left out.

That is what makes a sparse bundle possible. Staging used to merge every bundle
into one tree, which refreshed the *files* and replaced `manifest.txt` — leaving
everything an earlier bundle carried on disk and unlisted. The manifest is the
only door a provider has in, so those tools became unmeasurable on the one machine
that cannot download them again.

It also means a machine can say which bundle any staged file came from, which is
what the directory name is for.

**The checksums an asset is verified against come from the bundle that staged
it**, not from the newest bundle holding a `checksums.txt`. A digest is published
for one build of one release, so pairing a newer bundle's file with an older
bundle's binary fails verification on a machine where nothing is wrong.

### Why the cache and not state

Losing a staged bundle costs a re-fetch through the transport that delivered it,
which is the test for a cache. It cannot go under `$XDG_STATE_HOME/dotfiles/`,
which is a Syncthing folder — a gigabyte of archives there replicates across the
fleet. `src/dotfiles/paths.py` records this as a sanctioned exception, because the
classification is close enough to be worth writing down rather than defaulting.

## What travels back, and what cannot

`dotfiles status show` composes the same interchange document `plan --json` emits,
narrowed to the resources a bundle builder can act on. `scope` in the document
says which those are, so a consumer never reads "not mentioned" as "this machine
has none".

The narrowing is not a convenience. `check --json` carries the whole machine, and
on the work box that includes an employer git identity — `resources/identity.py`
records that a nonfleet box defaults to it — and the `WINDOWS_DOMAIN` in `~/.env`.

Two independent guards, in `src/dotfiles/publishing.py`:

- The document is composed over an **allowlist** of resources and never filtered
  down to one. A denylist admits whatever is added next; an allowlist excludes it
  until somebody decides otherwise.
- Before any byte moves, the serialized document is read for this machine's
  hostname and account. An allowlist protects against a new resource and not
  against a new field on a row.

Shelves and filenames key on the **manifest**, never on `paths.machine_id()`. That
is the bare hostname, and on the work box it is an employer asset tag. A status
filename additionally carries eight hex characters of a digest of it, because two
Macs share one manifest and the manifest alone would have one overwrite the other.

## The remote layout is dotfiles' to decide

```text
<remote.root>/
  bundles/<manifest>/dotfiles-offline-v<UTC>-<manifest>-<os>-<arch>[-sparse].tar.gz
  bundles/<manifest>/....tar.gz.json          size, digest, and the bundle.json
  status/<manifest>/dotfiles-status-v<UTC>-<manifest>-<digest>.json
```

Both ends of the exchange are this tool and nothing else reads these directories,
so a machine describing the structure in config would be describing a fact it does
not own. What the machine supplies is the root they hang under.

The stamp is UTC to the second. A day could not order two builds in one afternoon,
could not break a tie for `offline_bundle.newest`, and could not answer how long
ago a bundle was built — which is the first question anyone asks of one.

There is no index file. An index is one object several machines write, and it goes
stale against the directory listing that is the actual truth.

## The two automatic paths are off by default

`fetch_bundle_when_none_is_staged` and `publish_status_after_offline_apply` each
close one half of the loop without a command being typed. Both default false.

That is the point rather than caution. The work box sits on an employer network
where the concern is monitoring rather than capability, so a converge that reaches
a server unasked is a change in posture. The loop is worth automating and is not
worth automating quietly.

The fetch is reached only when the run is about to refuse for want of a bundle,
and a failure lets that refusal happen — "the remote would not answer" is a worse
thing to end an apply on than "there is no bundle", which is what the caller can
act on and is true either way.

The publish runs only after a converged offline apply. A document from a failed
one describes a machine part way through being something else.

## Related

- [Restricted Networks](../reference/support/corporate.md) — the runbook, in order
- [Observability](observability.md) — the interchange document this all rides on
- [GitHub Releases](github-releases.md) — how the assets a bundle carries are named
- [Management Interface](management-interface.md) — the verbs and the two front doors
