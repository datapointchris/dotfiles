# WSL disk and speed

One app, `wsl-tools`, deployed only where `host: wsl`. It does not exist on Arch
or macOS, because the questions it answers do not. `wsl-tools --help` lists the
verbs. The reasoning behind each one sits in the comments above its function in
`apps/host/wsl/wsl-tools`, and the refusal to offer sparse mode is pinned by
`tests/shell/test_wsl_tools.py` rather than left to a comment.

## Rebuild the disk for a routine reclaim; reinstall to prove the machine is reproducible

A distro's filesystem is one file on the Windows side and it never contracts on
its own. Shrinking it in place needs a Windows administrator, which a managed
machine does not hand out. `wsl-tools rebuild` is the route that needs none,
because export, unregister and import are all user-scope operations.

There is a third option that is not in this tool. Back up with safekeep, delete
the distro, install a fresh one, run `dotfiles apply`, restore, and carry on. It
reclaims the same space and needs no administrator either.

The two are not competing, because they answer different questions.
`wsl-tools rebuild` preserves the filesystem exactly and takes about as long as
copying the data twice. Deleting and reinstalling preserves only what safekeep
covers and takes as long as a full machine setup. In exchange it **proves the
machine is reproducible**, which is the entire premise of this repo and of
safekeep. It also drops the accumulated drift that a byte-exact rebuild carries
across faithfully.

So reach for `rebuild` when the disk is the only problem. Delete and reinstall
when it is worth finding out — deliberately, with time in hand — whether the
rebuild path still works. A reproducibility claim that is never exercised is only
a claim. Discovering it is false is otherwise an emergency rather than an
afternoon.

One asymmetry settles the choice when the disk is already full. safekeep writes
to the network drive, while `rebuild` writes its archive to a local disk it has
to fit on. The backup that leaves the machine is the safer of the two at exactly
the moment space is what you are short of.

## `.wslconfig` is the one config this repo copies rather than symlinks

`.wslconfig` configures the VM that hosts every distro, so it sits in
`%UserProfile%` on the Windows side. The symlink manager deploys below `$HOME`,
and `$HOME` here is inside the guest. The mechanism this repo uses for everything
else therefore cannot reach it. `install/wsl/install-wslconfig.sh` — `task
wsl:tune` — copies the file instead, and its header comment carries why an
existing one is backed up rather than overwritten.

Its `--check` mode prints drift on stdout and nothing else, so an empty answer
reads as converged. That matches the shape of every other check in this repo,
which is what lets a copied file take part in convergence at all.
