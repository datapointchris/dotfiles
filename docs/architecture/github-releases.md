# GitHub Releases

Twenty-three tools install from a prebuilt binary a project published on a GitHub
release. This is how, and — more usefully — why the parts that look like they
should be configuration are not.

Read the code alongside it: `src/dotfiles/providers/releases.py` names what each
release publishes, `src/dotfiles/providers/ghrelease.py` is the install engine,
and `src/dotfiles/github_release.py` holds the checksum and asset-resolution
rules the offline bundler shares.

## The split

One function per tool answers *what does this release publish and where is the
binary inside it*, and one engine answers *how does a published asset become a
binary on PATH*. Every tool goes through the same engine; only the naming varies,
because only the naming does vary.

The engine is one sequence — resolve a tag, name the asset, fetch it, verify it,
unpack it, place what came out, confirm it answers on PATH — and it reads three
fields to cover every shape upstream ships in:

- `Archive.RAW` — the download is the binary (hadolint, terraformer, yq)
- `Archive.GZIP` — a gzipped binary rather than an archive (tree-sitter alone)
- `Archive.TARBALL` / `Archive.ZIP` — unpack, take `path`, plus any `extras`
- `Asset.tree` — unpack under `~/.local` and symlink `path` out of it (neovim)

That last one exists because `nvim` will not start without the runtime files
packaged beside it, so the thing being installed is a directory, not a file.

`extras` are other binaries in the same archive, placed under their own names:
tenv's proxy shims (`terraform`, `tofu`, `terragrunt`, …), yazi's `ya`. Each is
placed if present and passed over if not, because tenv's set has grown release by
release — an install demanding all of them would break on the release before the
one that added a name.

`companions` are files fetched at the release's tag that the release does not
publish. `fzf-tmux` is the only one: a shell script in fzf's repo tree, and the
reason `prefix+s` opens a popup. It is fetched again whenever fzf installs, and
restored on its own when fzf is already current — a companion is a separate file
under `~/.local/bin`, and nothing about the binary being current says it is still
there.

## Why asset naming is code, not `packages.yml`

**Rejected:** a `url_pattern` field with a placeholder vocabulary.

```yaml
# Rejected
github_releases:
  - name: lazygit
    url_pattern: "{repo}/releases/download/{version}/lazygit_{version}_{platform}_{arch}.tar.gz"
```

Measured against every installer rather than assumed, twice. Most asset names do
fit a placeholder vocabulary, and the ones that miss cluster tightly enough that
two new placeholders would cover all but three. Those three are the answer:

- `shellcheck` — `darwin.aarch64`, dots where everything else uses dashes, and
  the only `.tar.xz` in the set
- `trivy` — `macOS-ARM64` against `Linux-64bit`: capitalisation and a bit-width
- `zk` — spells the same CPU two ways depending on the OS, `x86_64` on macOS
  against `amd64` on Linux, which no flat placeholder can express at all

The original rationale was "URL patterns vary enough that YAML templates become
complex; inline keeps it explicit and traceable", and it holds unchanged in
Python. What changed is that the alternative to a template is now a small typed
function rather than a whole script.

This is enforced rather than restated. `packages verify` rejects `binary_pattern`
and `install_dir` on a `github_releases` entry: both were carried on nearly every
entry while every reader gated on a key this section does not use, so neither was
read, neither was validated, and both drifted into naming assets that no longer
existed. A field that only looks like configuration is worse than none, because
it reads as authoritative to whoever edits the file next.

The parity in the other direction is checked: `packages verify` fails an entry
with no asset function, and `tests/install/test_release_urls.py` fails a function
naming a tool nothing declares.

## Version pinning

**Latest is the default.** An entry that declares nothing installs whatever the
release API calls newest, which is what almost every entry wants.

**A `version:` in `packages.yml` is honoured, exactly.** The capability is
operational rather than theoretical: a machine has to be able to hold a
known-good release while upstream is broken, and an older distro has to be able
to run an older build than the rest of the fleet.

The constraint is a **bare version, never a tag**, because the same release is
spelled `v0.56.0` by lazygit, `0.8.30` by terraformer and `cli/v0.9.0` by the
personal CLIs. Matching it against published tags is what lets one spelling work
everywhere, and `catalog.py` refuses a constraint written as a tag.

Two failure modes are deliberate and both are loud: a pin no release matches
aborts rather than falling through to latest, and a `packages.yml` that cannot be
read raises rather than resolving as though nothing were pinned. Falling through
is the exact outcome a pin exists to prevent.

The earlier answer here was "always latest, pin by editing the script", and the
cost showed up in the data: `version:` and `min_version:` sat on four entries no
code read, one of them eight versions stale.

## Prefixed release tags

Four entries are CLIs living in a monorepo that also releases an API and a web
app, so they are tagged `cli/v0.9.0` and `releases/latest` there answers with
whichever component shipped most recently. `release_tag_prefix` narrows the
lookup to releases carrying it. Without that, asking for `icb` reports the CLI
outdated every time the API releases, and current every time the API releases
after it.

## Private repositories

The browser URL (`github.com/…/releases/download/…`) **404s on a private repo
whatever token is presented**. Only the REST asset endpoint serves those, and
only with `Accept: application/octet-stream`, so the asset id is resolved first
and the browser URL is the fallback a public repo needs.

This is also why the asset *spelling* has to be exact rather than merely
downloadable. GitHub resolves release asset paths case-insensitively, so a
misspelled asset downloads fine from a public repo and then silently misses both
the asset-id lookup and the checksum entry recorded under the real name. lazygit
was fetched as `Linux_x86_64` against a published `linux_x86_64` for exactly that
reason, invisibly, because the download succeeded anyway.

## Checksum verification

Every download is checked against the SHA-256 the release published, **before
extraction** — so no unverified bytes are ever handed to a tar or zip reader.
This brings releases level with `goselfupdate`, which each tool's own `update`
command already uses.

The rules live in `src/dotfiles/github_release.py` rather than in the engine,
because the offline bundler needs the same ones: one verifies a download, the
other records a digest the first will later trust. They were separate
implementations, awk and Python, until the bundler was rewritten — and two
implementations of rules this fiddly can disagree without anything saying so, the
symptom being a bundle that verifies differently from a live install.
`tests/install/test_github_release.py` covers every case named here.

**Finding the checksum file.** Discovered from the release's asset list rather
than guessed, because the naming is not consistent: `checksums.txt` (goreleaser),
`SHA256SUMS` (just), `<tool>_<version>_checksums.txt` (fzf, trivy), or a per-asset
`<asset>.sha256` sidecar (atuin, hadolint). A sidecar wins outright, since it
names exactly one file and cannot be ambiguous. Detached signatures and
certificates sit beside the checksums file and match a naive `*checksum*` search
— tflint publishes `checksums.txt` next to `checksums.txt.keyless.sig` and
`checksums.txt.pem` — so those are excluded by suffix, or the asset would be
compared against a signature.

**Reading it.** The `sha256sum` format both GNU and goreleaser emit: digest,
whitespace, an optional `*` binary marker, then the name. A CI step written as
`sha256sum ./*.tar.gz` records `./tool.tar.gz` while the asset is named
`tool.tar.gz`, so an exact match is tried first and the base name only consulted
when nothing matched exactly. A case-insensitive match is the last resort, for
the lazygit case above.

**Verification is required by default**, and an entry that cannot satisfy it says
so in `packages.yml`:

| `checksum:` | Meaning |
| --- | --- |
| `required` (default) | Must verify. An install that cannot stops. |
| `unpublished` | The release publishes no checksum file at all. |
| `unlisted` | It publishes one that does not name this asset. |

The two exceptions are separate values because they are separate upstream facts,
and one is one upstream fix away from being verifiable while the other is not.
`yq` is the whole of `unlisted`: an rhash table with the name in column 0, which
is not the `<digest>  <name>` shape every other publisher uses.

Which entries declare which, and whether the declaration is still true, is
measured against live releases rather than written down here:

```bash
uv run pytest tests/install/test_release_urls.py --e2e -k verifies
```

That test fails in **both** directions — a project that starts publishing
checksums must stop being an exception, and one that stops must be caught before
an install refuses it. Defaulting to required is what makes the first automatic.

Before this default existed, seven installers bypassed the shared library
entirely because their archive shape did not fit it, and every one of those
bypasses skipped verification silently — `hadolint` and `tenv` were installing
unverified from releases that publish perfectly good checksums.

**On failure.** A mismatch deletes the download and aborts, never negotiable, and
deleting matters because a retry would otherwise verify or extract bytes that
already failed. An unlisted asset is *not* deleted: nothing was compared, so
nothing was proven wrong.

**What this defends against.** A corrupted, truncated or intercepted download,
given that the checksums file itself arrives over TLS from the same release. Not
a compromised publishing account, which can rewrite the checksums file alongside
the asset — that needs a signature verified against a key distributed out of band.

## Offline

A bundle staged under `~/installers/` is preferred over the network whenever it
holds the asset, not only when offline: those bytes were verified against their
release when the bundle was built, and re-downloading them spends a request to
arrive at the same file.

Offline resolves the version from the bundle's `manifest.txt` rather than the
release API — the network that makes a bundle necessary is the same one that
blocks the API, and the asset filename is built from the version, so a version
fetched live names a file the bundle does not contain the moment upstream ships.

An offline install verifies against `installers/checksums.txt` and **never falls
through to the network**, which would spend a timeout arriving at "upstream
publishes nothing" — a statement about upstream that is really a statement about
the bundle. `create_bundle.py` records only digests it verified against upstream
while building, so an asset whose release publishes nothing usable is simply
absent from that file.

## What is deliberately not here

- **Signature verification** for the releases that publish one (sigstore bundles:
  glow, tflint, trivy). Worth having; not done.
- **Rollback.** Idempotency plus a pin covers the need.
- **Per-tool install scripts.** There were twenty-three, and deleting them is
  what this page describes. A new tool is a function next to the one above it.

## Related

- [Package Management](package-management.md)
- [Shell Libraries](shell-libraries.md)
