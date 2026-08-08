# Rebuilding a Machine from Scratch

How to wipe a machine and rebuild it from this repository. The shape is the same
on every platform; only three things differ — how the machine gets erased, what
has to exist before `install.sh` can run, and which bookends the automation
deliberately refuses because they need a secret, an interactive sign-in, or a
freshly generated identity.

Every tool and config here is reproducible from this repo plus a package
manager. What is genuinely at risk is the machine-local state that no repo
holds, which is why the capture step comes first.

## The shape

1. Capture the machine-local state, while the old system is still alive.
2. Wipe and reinstall the OS.
3. Install `git` with the system package manager — the one bootstrap dependency.
4. Clone this repo over HTTPS. No SSH key exists yet on a fresh machine.
5. Restore the captured state.
6. `./install.sh --machine NAME`.
7. Verify, then do the manual steps.

## Capture what no git repo holds

`safekeep` takes dated, tagged snapshots of exactly this; `safekeep --help`
covers the verbs and `safekeep tags` says what a given tag would bring back.

Getting the capture *set* right is the hard part, because what dies in a wipe is
unobvious. `~/.env` holds the machine's identity, and everything below its
`# OVERRIDES` marker is hand-written and exists nowhere else. The machine-local
overlay at `~/.local/shell/local.sh` sits outside this repo on purpose, so
employer shell code stays off a synced clone — which also means nothing
redeploys it. The generated part of `~/.env` names the path for that reason.
`syncer`'s config is machine-local for the same reason, and without it a rebuilt
box has no registry of repos to clone. Add credentials, SSH keys, and anything
under `~/.config` that was authored rather than deployed.

Confirm the destination survives the wipe: a snapshot inside the machine you are
about to erase is not a backup. On WSL that means a Windows or network path, not
somewhere under the distro's own filesystem.

Seed phrases are the exception to all of this. Record them offline, restore-test
each wallet on a *different* machine before wiping, and never let a seed pass
through a networked tool.

## Restore before the install, not after

`install.sh` regenerates `~/.env` from the manifest **before** it runs any phase,
preserving everything below the `# OVERRIDES` marker. Restore first and the
managed half is rebuilt against the current manifest while the hand-edits and
secrets survive intact.

Restore afterwards and you reinstate the *old* machine's generated half — stale
flags, possibly a stale platform — by which point every phase has already run on
defaults. The comment at `install.sh:521` records what that costs: a run that
fell back to `detect_platform`'s guess deployed the linux shell overlay to a
machine whose manifest said wsl, and ignored every flag override for the whole
install.

## macOS

Apple Silicon and T2 Intel Macs reset cleanly without a Recovery reinstall:
*System Settings → General → Transfer or Reset → Erase All Content and
Settings*. Have the Apple ID password ready; the reset clears Activation Lock as
part of the flow.

Xcode Command Line Tools is the bootstrap dependency, being where `git` comes
from. `install.sh` self-bootstraps Homebrew and everything after it.

```bash
xcode-select --install
```

## Arch Linux

Do a base install, ensure `git` and `sudo` are present, and run `install.sh`.
The installer owns everything above the base system, including the AUR helper.

## WSL — the work machine

Measure the firewall and build the offline bundle *before* the wipe. Both need
the old box alive and networked, and neither is recoverable afterwards
([Restricted Networks](support/corporate.md) covers the machinery). Re-measure
rather than trusting an old reading — the blocked set has twice been wrong in
the direction of carrying tools that were never actually blocked.

Rebuild by registering the new Ubuntu rootfs as the distro. Get the bundle onto
the new WSL filesystem and install from there rather than across a mounted
drive; `--offline` extracts it to `~/installers/` itself, so nothing needs
unpacking by hand.

```bash
./install.sh --machine wsl-work-workstation --offline
```

This box has no Syncthing, so anything the fleet replicates that way — `~/dev`,
`~/notes`, the `indy` index — is simply absent. Tools depending on those paths
are either off the manifest or configured differently, which is a property of
the machine rather than something the install detects.

## Verify

```bash
dotfiles check       # symlink, package and flag drift in one place
packages missing     # declared but not installed
syncer check         # repos the registry expects, against what is on disk
```

Open the editor and confirm plugins loaded without errors. `install.sh` is
idempotent, so anything that failed can be fixed and the whole thing re-run.

## After the install

Generate a new SSH key rather than carrying the old one forward, and
re-authorize it — a fresh key forces the pruning of dead authorizations. Restore
wallets from their seeds, and sign into the applications holding their own
credentials.

File sync needs *peering*, not just installation: each side has to add the other
and agree to share each folder, so configure both ends.
