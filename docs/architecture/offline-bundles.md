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

## The transport is a program this repo never names

A machine declares one in `~/.config/dotfiles/config.toml` and dotfiles builds an
argv from the templates beside it. The credential, the protocol and the retry
behaviour stay owned by the CLI that owns them.

```toml
[remote]
root = "/dotfiles"
keep_bundles = 5
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

They carry disjoint facts on purpose. The created-at and platform headers live
only in `bundle.json`, never in both.

```json
{
  "version": 1,
  "created": "2026-09-01T07:30:00Z",
  "machine": "wsl-work-workstation",
  "platform": "linux/x86_64",
  "completeness": "sparse",
  "built_from": "dotfiles-status-v20260901T070000Z-wsl-work-workstation-4f2a91c3.json",
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

That is what makes a sparse bundle possible. Merging every bundle into one tree
would refresh the *files* and replace `manifest.txt`, leaving everything an
earlier bundle carried on disk and unlisted. The manifest is the only door a
provider has in, so those tools would be unmeasurable on the one machine that
cannot download them again.

It also means a machine can say which bundle any staged file came from, which is
what the directory name is for.

**A bundle built for another machine is refused before it is moved into place.**
`bundle download --machine X` writes into the same cache `newest` ranks, so
fetching another box's bundle to look at it is one command away from
`apply --offline` staging it — a hazard that did not exist while a bundle could
only be carried in by hand. A bundle that names no machine still stages, and so
does any bundle on a box that cannot name itself: that is the state part way
through a rebuild, and it is the one that most needs to unpack something.

**The checksums an asset is verified against come from the bundle that staged
it**, not from the newest bundle holding a `checksums.txt`. A digest is published
for one build of one release, so pairing a newer bundle's file with an older
bundle's binary fails verification on a machine where nothing is wrong. A
companion is resolved the same way and for the same reason: `fzf-tmux` carries no
version in its name, so an unpinned lookup hands an older `fzf` a newer bundle's
script.

**Retention pins the newest full bundle per machine.** The stack only works while
the base is there — everything a sparse bundle omitted is read through it — and a
name sorts as its stamp does, so the base is always the oldest and was always the
first thing a sweep took. At the default limit of five that lands after five
sparse builds rather than only at `--keep 1`. A newer full build unpins the older
one, which bounds a machine's stack at the limit plus one.

One function decides all of it — `offline_bundle.retention` — and the local sweep,
the remote sweep and the post-upload nudge all ask it. Composed by hand at each of
the three, they had already stopped agreeing about whether the limit was floored.
`--keep 0` is a usage error rather than a silent clamp to one, and `bundle prune
--json` carries what was removed, kept and pinned so nothing has to read it out of
the closing sentence.

**Which version a tool is measured against comes from the newest bundle that
answers, not from the newest answer of a given kind.** A bundle says what upstream
published two ways — a manifest row for what it carried, `current` for what it
measured and left out — and asking every bundle for a row before any for its
`current` lets a stale row from the base beat a fresh measurement above it. That
reported the machine as ahead of the newest release, and an offline apply repaired
it by installing the older binary.

### Why the cache and not state

Losing a staged bundle costs a re-fetch through the transport that delivered it,
which is the test for a cache. It cannot go under `$XDG_STATE_HOME/dotfiles/`,
which is a Syncthing folder — a gigabyte of archives there replicates across the
fleet. `src/dotfiles/paths.py` records the reasoning, because the classification is
close enough to be worth writing down rather than defaulting.

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

**The second guard has three answers, because a row can carry a name the machine
did not write.** A row's `observed` is whatever a tool printed about itself, and
`syncthing --version` reports the host that built the Arch package — so on a box
named `archlinux` the string `syncthing@archlinux` reached the scan and refused a
document that identified nothing. Refusing the whole thing took the return leg off
a working machine for one row out of a hundred. A row carrying one of the names is
now **withheld** and named on screen; a name with no row to drop still refuses the
document. Nothing carrying an identity leaves under either rule, and a withheld row
lands in the state the format already means by absence — unmeasured, so the builder
carries the tool rather than assuming it current.

Loosening the match itself was rejected. Word boundaries still match
`syncthing@archlinux`, a minimum length stops protecting `mbp`, and an escape hatch
is a hole in the one boundary that must not have one.

Shelves key on the **manifest**, never on `paths.machine_id()`. Two Macs share one
manifest, so a status filename carries a discriminator after it or the second
upload overwrites the first.

**The discriminator is in the document as well as in the name.** A filename can be
renamed and `bundle create --against` takes any path, so `written_by` carries it in
the bytes and `status.published_by` prefers that over parsing the name. The builder
records it into `bundle.json` as `built_for`, and the target — the only end that
knows which box it is — refuses a sparse bundle planned against its twin. Without
that, one Mac's bundle omitted every tool the *other* Mac had current and reported
the omissions as measured.

**Which discriminator depends on the trust coordinate.** On a fleet machine it is
the bare hostname — not a secret there, and a shelf listing that says `macmini`
answers "which box published this" without opening anything. Off the fleet the
hostname is an employer asset tag, so it is eight hex characters of a blake2b
digest instead: enough to tell two boxes apart, not enough to name either.
Anything that is not `FLEET` gets the digest, and so does a hostname carrying a
hyphen, since `status.wrote` recovers the segment by splitting on the last one.

## The remote layout is dotfiles' to decide

```text
<remote.root>/
  bundles/<manifest>/dotfiles-offline-v<UTC>-<manifest>-<os>-<arch>[-sparse].tar.gz
  bundles/<manifest>/....tar.gz.json          size, digest, and the bundle.json
  status/<manifest>/dotfiles-status-v<UTC>-<manifest>-<hostname|digest>.json
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
