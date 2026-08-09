# Custom Installers

Nine tools do not come from a GitHub release, a language registry, or a system
package manager. They come from a vendor's own install script, an S3 bucket, a
HashiCorp mirror, or three git repos and a build. This is how, and why the shape
is deliberately the opposite of the release installers next door.

Read the code alongside it: `src/dotfiles/providers/custom.py` is all nine
functions and the two tables that route to them.

## Why there is no engine

`github_releases` is twenty-three spellings of one sequence, so
`providers/ghrelease.py` is an engine and the variation lives in a data class.
Trying that here would produce an engine with nine branches and no shared body.
The nine differ in what they fetch, how they verify it, where it lands, and —
most of all — in how to tell whether anything needs doing at all.

So this is nine functions and a dispatch table. `custom_installers` is not a
category of tool; it is the name for *no shared mechanism*, and the file's shape
should say so.

## One verb, and what asking costs

Each of the nine scripts this replaced had an install mode and an `--update`
mode, and which one ran decided whether a tool that was present but behind got
upgraded. `apply` means "make this machine match what it declares", so every
function converges instead. What differs between them is only the price of the
question:

| tool | how it converges |
| --- | --- |
| `theme`, `font`, `zmk-build` | the checkout exists → delegate to the tool's own `update` |
| `bashselfupdate` | the install script *is* the update, so run it every time |
| `bats`, `terraform-ls` | upstream publishes releases → compare, then skip |
| `mount-s3` | the same, from `awslabs/mountpoint-s3` |
| `claude-code` | self-updates in the background → presence is enough |
| `awscli` | nothing cheap to ask → presence is enough |

Two of those deserve their reasoning stated, because they look like corners cut.

**`awscli` is skipped when present.** AWS publishes no GitHub release for
`aws/aws-cli` — `/releases/latest` 404s — so there is nothing to compare an
installed version against, and the installer zip is 73MB (measured 2026-08-08).
The vendor's `aws/install --update` converges by itself, but running it on every
`apply` spends 73MB to answer a question with no cheaper form. `--reinstall` is
the update path.

**`mount-s3` was the same shape and is not any more.** AWS's bucket serves only
`latest/{arch}/`, so the download URL carries no version and the old script
fetched the whole tarball on every update run just to find out what was in it.
But `awslabs/mountpoint-s3` publishes the same builds as GitHub releases and
`mount-s3 --version` reports that tag's number, so currency costs one API call.
That is why the entry declares `repo:` for a tool whose bytes never come from
GitHub — the repo is where the *version* lives, which is a declarative fact even
when the distribution is not.

**Offline leaves an installed tool alone rather than failing.** Every one of
these updates over the network — a clone, a vendor script, a release API — so an
offline run has nothing to compare against and nothing to fetch. Failing the
phase would report a machine as broken for being exactly what its bundle made it.

## What stays in `packages.yml`

Only what is declarative: the host (`url`), the repo a version or a clone comes
from (`repo`, `support_repo`, `assert_repo`), the install script's URL
(`install_url`), where a tool that puts nothing on PATH lands
(`installed_path`), and whether the offline bundler should stage its script
(`bundle_install_script`).

`source_type` used to sit alongside them — one of `github_clone`,
`hashicorp_release`, `official_installer`, `aws_release` — and it existed for
exactly one reader: `test-connectivity.sh` switching on it to decide what to
probe. Once the probe could ask the installer directly, nothing read it, which is
the drift `catalog.py`'s `UNREAD_KEYS` exists to prevent. It is in that map now,
with the reason attached.

## Sources, and what a connectivity probe is told

`sources(entry, target)` returns every host installing a tool depends on, as
`Source(url, reach)` where reach is a download or a clone. It replaced the
`case "$source_type"` in `install/offline/test-connectivity.sh`, which could say
"a github_clone needs github.com" and nothing beyond it — not that `theme` also
fetches its install script from `raw.githubusercontent.com`, not that `bats`
needs three separate repos, not that `awscli` names a different zip per
architecture. Each of those was unprobed or approximated.

An empty tuple means this platform installs the tool from somewhere else or not
at all: `awscli` comes from Homebrew on a Mac, `mount-s3` has no macOS build.
That is not a failure to look, and probing anyway would report a block against a
host the machine was never going to contact.

`terraform-ls` deliberately names the project directory rather than the asset:
the filename carries a version that has not been resolved yet, and a probe that
had to resolve one first would fail for the wrong reason.

Read them for any tool with:

```bash
packages_query --sources theme     # python -m dotfiles.parse_packages --sources
```

## Verification

Three of the nine verify what they downloaded, and each verifies differently
because each vendor publishes differently.

`mount-s3` has a detached GPG signature checked against **pinned fingerprints**,
not against whatever `KEYS` holds. The key is served from the same bucket as the
tarball it signs, so importing that file and verifying against it proves only
that the bucket agrees with itself. An unpinned key or a bad signature refuses
the install. A machine with no `gpg` warns instead: it has not been shown a bad
signature, it has been unable to look.

`terraform-ls` is checked against HashiCorp's `SHA256SUMS` for the release, named
directly rather than discovered — the file is not among the GitHub release's
assets, which is the whole reason this is not a `github_releases` entry. A
checksums file that cannot be fetched refuses rather than warns: HashiCorp
publishes one for every release, so failing to get it means something is wrong
with the download path, which is exactly when a checksum matters.

`awscli` runs AWS's own installer, which does its own integrity checking, and
`bats` is a git clone at a signed tag.

## Adding one

Write the function, add it to `INSTALLERS` and `SOURCES`, and add the entry to
`packages.yml`. `dotfiles machines check` fails a declared entry with no function, and
`tests/install/test_custom_installers.py` fails a function naming a tool nothing
declares, plus a tool absent from `SOURCES` — which would probe nothing and be
indistinguishable from a reachable host.

Before writing one, check that it really is custom. A tool with a GitHub release
is `github_releases` and gets checksum verification, offline bundling and
currency for free.

## What is deliberately absent

**No `--print-url` protocol.** The offline bundler used to ask each script for a
`name|version|url` line over a pipe. It reads `install_url` from the declaration
now; the pipe was a second place for the bundler and the installer to disagree
about which file to stage.

**No shared "run a vendor script" abstraction beyond staging it.** Five of the
nine run one, and the only thing they share is where the script comes from —
the offline bundle if it holds one, the network otherwise. What each does with
the result is different enough that a common wrapper would be branches.

**No failure-log protocol.** The scripts emitted structured `FAILURE_MANUAL`
blocks for `run-installer.sh` to collect. Each function returns a `Result`
instead, and the phase writes the log.
