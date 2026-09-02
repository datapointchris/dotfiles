# GitHub Releases

A tool declared under `github_releases` in `install/packages.yml` installs from a
prebuilt binary its project published on a release. Three modules carry it, and
their docstrings are the account of the mechanism:
`src/dotfiles/providers/releases.py` names what each release publishes,
`src/dotfiles/providers/ghrelease.py` installs one, and
`src/dotfiles/github_release.py` holds the asset and checksum rules the offline
bundler shares. This page holds the decisions those docstrings do not.

## Why asset naming is code, not `packages.yml`

**Rejected twice:** a `url_pattern` field with a placeholder vocabulary.

```yaml
# Rejected
github_releases:
  - name: <tool>
    url_pattern: "{repo}/releases/download/{version}/{name}_{version}_{platform}_{arch}.tar.gz"
```

Measure the proposal against every entry before believing it. Most asset names do
fit a vocabulary, and two more placeholders would take all but a handful. Those
few defeat it outright — an architecture spelled one way per OS, a capitalization
nothing else uses, an archive format nothing else uses. Read them side by side in
`providers/releases.py`.

The half-measure is what was actually paid for. `binary_pattern` and `install_dir`
rode along on nearly every entry in this section while no reader gated on either,
and both drifted into naming assets that did not exist. `dotfiles machines check`
rejects them here for that reason: a field that only looks like configuration
reads as authoritative to whoever edits the file next.

## Pinning exists for a machine upstream has broken

Latest is the default, and almost every entry wants it.

A `version:` earns its complexity operationally rather than theoretically. A
machine has to be able to hold a known-good release while upstream is broken. An
older distro has to be able to run an older build than the rest of the fleet.

**Rejected:** always latest, with a pin spelled by editing the installer. The cost
showed up in the data — constraint fields sat on four entries no code read, one of
them eight versions stale.

## One install path per binary takes two independent measurements

A tool declared here while a package manager also ships it is not one install
path. It is two, and a version check then agrees with whichever copy answers
first. That was syncthing until 2026-08-16.

Closing it needs two mechanisms, and no single module pairs them up because each
knows only its own end. **Provenance** narrows the question from "is a syncthing
installed" to "is the one this declaration asks for installed", in
`evidence.by_release`. **Displacement** declares the package name a release took
over from, in `catalog.GithubRelease.supersedes`, and refuses to install beside
it. Provenance alone reports the machine honestly and converges nothing.
Displacement alone has no measurement to fire on.

## Verification defends the transfer, not the publisher

Every download is checked against the SHA-256 the release published, before
extraction. An entry whose upstream cannot supply one declares that in
`packages.yml`; `catalog.CHECKSUM_STATES` says why the exceptions are separate
values.

Whether a declared exception is still true is measured against live releases
rather than written down here:

```bash
uv run pytest tests/install/test_release_urls.py --e2e -k verifies
```

**What this defends against.** A corrupted, truncated or intercepted download,
given that the digests arrive over TLS from the same release. Not a compromised
publishing account, which can rewrite the checksums file alongside the asset. That
needs a signature verified against a key distributed out of band.

## What is deliberately not here

- **Signature verification** for the releases that publish one. Worth having; not
  done.
- **Rollback.** Idempotency plus a pin covers the need.
- **Per-tool install scripts.** A new tool adds a function to `releases.py`.

## Related

- [Package Management](package-management.md)
- [Shell Libraries](shell-libraries.md)
