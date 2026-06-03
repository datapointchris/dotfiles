# Rebuilding a Machine from Scratch

How to wipe a personal workstation and rebuild it from this repository. The
install system does the heavy lifting — this guide covers the manual bookends it
cannot: what to rescue before erasing, and what to set up by hand afterward.

The guiding principle is that almost nothing on a workstation is truly
irreplaceable. The operating system and every tool are reproducible from this
repo plus the system package manager, and most documents already live in cloud
sync. What remains at risk is a small set of local-only secrets — and those are
exactly the things automation deliberately cannot restore for you.

## Before the wipe — rescue the irreplaceable

Work through this list while the machine is still alive. Everything here is
either local-only or destructive to lose.

- **Crypto wallets — back up the seed, not the files.** The mnemonic seed phrase
  *is* the wallet; the application data files are conveniences that the seed
  regenerates on any machine. So record each seed offline in two separate
  physical places, and optionally as an encrypted note in a password manager.
  Restore-test each wallet from its seed on a *different* machine and confirm the
  addresses match **before** wiping. Never let a seed pass through a networked
  tool, a screenshot, or a printer queue.
- **Cloud-synced data.** Confirm Photos, Desktop, and Documents have finished
  uploading to iCloud (or your sync provider) before erasing — "syncing" is not
  "synced."
- **SSH keys — treat as disposable.** Do not carry stale keys forward. Plan to
  generate a fresh key after the rebuild and re-authorize it; this is cleaner
  than migrating old key material and forces you to prune dead authorizations.
- **Uncommitted git work.** Commit and push anything you want to keep, or accept
  that it is gone. Check every active repo.
- **GPG keys**, if you use them. Confirm the secret keys are mirrored on another
  machine; export them securely if not.

## The wipe

Modern Macs — Apple Silicon, or Intel with a T2 security chip — support a clean
factory reset that does not require a Recovery reinstall:

*System Settings → General → Transfer or Reset → Erase All Content and Settings.*

Have your Apple ID password ready; the reset signs out of iCloud and clears
Activation Lock as part of the flow.

## Rebuild — automated

The rebuild is one command after a couple of prerequisites.

1. **Setup Assistant.** Create your user, sign into iCloud, and join the network.
2. **Xcode Command Line Tools** — the only manual prerequisite, since it provides
   `git` and a compiler:

   ```bash
   xcode-select --install
   ```

3. **Clone this repo over HTTPS** (no SSH key exists yet on a fresh machine):

   ```bash
   git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
   ```

4. **Run the installer** with the manifest for this machine:

   ```bash
   cd ~/dotfiles && bash install.sh --machine macos-personal-workstation
   ```

   See [Platform Differences](platforms/differences.md) for the manifest name of
   each platform.

`install.sh` self-bootstraps in order — Homebrew, system packages, OS
preferences, language toolchains, release-tool and custom installers, symlinks,
then editor and terminal plugins. It is idempotent and "fail loud but keep
going": a failed step produces a report rather than a wedged install, so it is
safe to re-run after fixing an issue. The architecture is documented under
[Architecture](../architecture/index.md); the installation-pattern learnings in
[Learnings](../learnings/idempotent-installation-patterns.md) explain the design
choices behind it.

## After the install — manual steps

These are the steps automation cannot do because they require a secret, an
interactive sign-in, or a fresh identity.

- **SSH.** Generate a new key (`ssh-keygen -t ed25519`) and add the public key to
  GitHub and any servers you reach. Authentication that already uses a token
  (for example the GitHub CLI) needs nothing here.
- **Wallets.** Install the wallet apps and restore each from its seed.
- **File sync.** Installing the sync client is not enough — you must *peer* the
  new machine with your existing devices so folders replicate down. Peering is a
  mutual handshake: each side has to add the other and agree to share each
  folder, so configure both ends. On a LAN the connection prefers a direct link
  and falls back to an encrypted relay off-network; keep relay and discovery
  enabled so a laptop still syncs when it travels.
- **Application sign-ins.** iCloud re-downloads Desktop, Documents, and Photos on
  its own; sign into the remaining apps manually.
- **Verify.** Confirm the toolchain came up clean: `task --list`, `toolbox`, and
  open your editor to check plugins loaded without errors.

## Why the split

The installer handles the reproducible 95% — packages, configs, preferences, and
tooling that are identical on every rebuild. The manual steps are precisely the
remainder that *should not* be automated: secrets (keys, seeds), interactive
account authorization, and freshly generated identities. Keeping that line sharp
is what lets the automated half stay fully hands-off and safe to re-run.
