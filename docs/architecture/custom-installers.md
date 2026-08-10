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
| `bats`, `terraform-ls` | clone or download at the tag upstream reports |
| `mount-s3` | the bucket serves `latest/`, so fetch it |
| `claude-code` | self-updates in the background → presence is enough |
| `awscli` | no release to compare against → presence is enough |

**Whether a tool is behind is not decided here.** It was, briefly: `bats`,
`terraform-ls` and `mount-s3` each carried a version comparison inside the
installer, and those comparisons only ever ran because the install phase called
every installer on every `apply`. That is an unconditional re-run standing in for
a measurement, and it stops working the moment these rows converge through the
engine, which only ever acts on a verdict. `resources/packages.CURRENCY` measures
it now, off the `repo:` each entry already declares — so an installer that is
called is one the machine needs, and `dotfiles check` can say a custom installer
is behind for the first time.

That is also why the entries declare `repo:` for tools whose bytes never come
from GitHub. The repo is where the *version* lives, which is a declarative fact
even when the distribution is not — `mount-s3` adds `release_tag_prefix:` beside
it, because its tags are `mountpoint-s3-1.23.0` in a repo that tags other things.

**`awscli` is measured against tags, because it has no releases.** AWS publishes
no GitHub release for `aws/aws-cli` — `/releases/latest` 404s, rechecked
2026-08-10 — but it tags every build, so the entry declares `repo:` beside
`version_source: tags` and the lookup goes to `/tags`. That matters because the
vendor's own `aws/install --update` converges by itself and costs 73MB every time
(measured 2026-08-08): before this, presence was the whole verdict and the only
way to move an installed awscli was a `--reinstall` flag that measured nothing.
Reaching the installer now means the machine is missing it or behind.

`claude-code` is the one entry left that nothing can answer for, and correctly so
— it updates itself in the background, so presence really is the whole question
and re-running the installer would fight the thing it is converging.

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
blocks for the wrapper to collect. Each function returns a `Result`
instead, and the phase writes the log.
