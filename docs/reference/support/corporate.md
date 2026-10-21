# Restricted Networks

One machine sits behind a firewall that blocks most of what an install reaches
for. Everything here is built for that machine, and none of it is proxy or
registry-mirror configuration.

## Find out what is actually blocked

`dotfiles network check` walks every URL the install touches and reports a
pass/fail line per host. Run it on the restricted machine first. The answer is
rarely "the internet is blocked" and usually "GitHub release assets are blocked
but the API is not", which changes what you have to carry in.

The check then reads the machine's `[network] blocked` list and says where the two
disagree. A `declared` row names each listed host and the items whose version
check or download reaches it. An `undeclared` row is a host that refused but is
not listed, so an apply would ask it and fail. An `answered` row is a listed host
that answered, so an apply takes from the bundle what the network would serve.

Pass `--output <path>` to render the run somewhere outside the repo. Keep it
under `$XDG_STATE_HOME` to diff two runs after the firewall rules change.
`src/dotfiles/commands/network.py` holds why that flag has no default, and
`tests/install/test_network.py` fails the suite if a rendered run is ever
tracked.

Note what the check looks like from the other side. It is a burst of requests to
distinct external hosts and it classifies TLS interception, so it reads as egress
mapping to anything watching. Run it when you need the answer, not on a schedule.

## Build the bundle where the network is

`dotfiles bundle create` writes one tarball for a machine that is not the one
running it. `src/dotfiles/create_bundle.py` says what goes into it, and
`dotfiles bundle create --help` says why neither `--machine` nor `--arch` has a
default.

The bundle carries the bootstrap as well as the tools: `uv` for the target
platform, and a wheelhouse holding the CLI's own dependency closure. Without
those the blocked machine unpacks an archive it has no way to install from, which
is the one failure the whole arrangement exists to prevent.
`create_bundle.add_wheels` says why every wheel for every supported interpreter
goes in rather than one chosen here.

An archive's name carries a UTC stamp, so handing it on means retyping something
that changes every build. `dotfiles bundle upload` finds the newest itself, which
is why the handoff is two commands rather than a substitution:

```bash
dotfiles bundle create --machine wsl-work-workstation --arch x86_64
dotfiles bundle upload
```

`--print-path` puts the finished path on stdout for a pipeline, after the cache
prune, so nothing downstream reads an archive still being written.

The builder is Python rather than shell because of that name. A bash function has
no return value, so "produce a tarball and tell the caller what it is called" has
no direct expression there. `tests/install/test_create_bundle.py` covers the
logic and needs neither a network nor a container.

## Install it on the restricted box

`dotfiles remote check` says whether this machine can exchange anything at all.
Run it before the first transfer rather than after a failed one.
`src/dotfiles/commands/remote.py` says why a declared transport and a usable one
are two separate questions.

Then, from the restricted box:

```bash
dotfiles bundle download
dotfiles apply --machine wsl-work-workstation --offline
dotfiles status upload
```

`bundle download` takes the newest archive built for this machine. It describes
what it found and asks before the transfer. The apply unpacks that archive
itself, and skips the unpacking only when it is already staged — so there is no
staging step to remember and a bundle fetched to replace an old one takes effect
on the next run. `status upload` publishes what the box now has, so the next
bundle can be built against it.

`dotfiles bundle stage PATH` is still there for unpacking without installing,
which is what `bundle check` and `bundle show` read, and for a tarball carried
across by hand from somewhere the search does not look.

To read back what an apply did, `dotfiles report upload` from the restricted box and
`dotfiles report download --machine wsl-work-workstation` where the network is.
The record says what the run decided and the log beside it says what it ran,
which is the pair that answers a converge nobody was watching.

On a machine with no CLI yet the bootstrap comes first.
`./install.sh --machine NAME --offline` finds the newest archive in the download
cache, beside the checkout or in `$HOME`, unpacks it under
`$XDG_CACHE_HOME/dotfiles/staged/`, installs uv and the CLI from it with no index
at all, and prints the apply line above. The flag means a different thing on
each. The bootstrap takes uv and the wheels from the bundle. The apply takes only
blocked items from it and contacts no remote.

## The config names what this network blocks, and one apply routes around it

This box is only partly blocked. Its config, deployed from
`configs/trust/nonfleet/.config/dotfiles/config.toml`, lists the hosts it refuses
under `[network] blocked`. `dotfiles network check` probes the hosts the plan
reaches. It names a refused host the list leaves out, and a listed host that
answers.

Each item reaches two hosts, and the apply routes them apart. An item whose
download reaches a listed host installs from the staged bundle. Everything else
installs from the network, as it would anywhere. A release tool's assets are
blocked, but its version check goes to `api.github.com`. So it is measured against
the newest release while its bytes come from the bundle.

That makes the whole box one command, after the checkout is current:

```bash
dotfiles update
dotfiles apply --machine wsl-work-workstation
```

apt is asked what is behind, plugin checkouts are pulled, and TPM and lazy sync
over git. rustup, Go and node install from their own hosts, and uv comes from the
bundle. The run opens with a `network` line counting the blocked hosts and saying
how many items go to the bundle and how many to the network. An item routed to
the bundle that is missing or behind, with no staged bundle carrying it, is asked
of a builder in the same run, as the section below describes.

`--offline` keeps the list, installs blocked items only from what is staged, and
contacts no remote. Such an item then gets a row naming the blocked host and the
bundle it needs. Where the list is empty or absent, `--offline` counts every host
as blocked and asks no network.

## Carry only what changed

Each round is planned against the last. `dotfiles status upload` publishes what
the restricted box already has, scoped to packages and toolchains and to nothing else.
Then, where the network is:

```bash
dotfiles bundle create --machine wsl-work-workstation --arch x86_64 --against latest
dotfiles bundle upload
```

`dotfiles bundle create --help` says how `--against` decides what to leave out
and why an omission is recorded rather than silent. Each bundle keeps its own
directory instead of merging into one, which is what lets a sparse build carry a
difference alone. `dotfiles bundle prune --help` says which archives that pins
against the retention limit.

Two `[remote]` keys close the loop with nothing typed:
`fetch_bundle_when_none_is_staged` and `publish_status_after_offline_apply`. Both
default off. `docs/architecture/offline-bundles.md` says why the defaults are one
decision rather than several.

## The apply asks a builder for what no staged bundle carries

This box's config turns on `request_bundle_when_blocked_items_are_behind`. When
the apply finds blocked items missing or behind and no staged bundle carrying
them, it publishes this box's status and leaves a request on the remote naming
those items. Then it waits for a builder running `dotfiles bundle serve`. Each
step is a log line: sent, acknowledged by the builder, still waiting, bundle
listed, downloading, verified, staged. The apply measures those items
again against the new bundle and installs them in the same run.

`dotfiles apply --request-bundle` asks on a box whose config leaves the key off,
and asks under `--offline` too. `dotfiles bundle request` asks without applying:

```bash
dotfiles bundle request              # everything the status shows behind
dotfiles bundle request --entry glow # or only what is named
```

When no builder acknowledges the request in time, the apply names the
`dotfiles-bundle-serve` unit to check on the builder, stops waiting and installs
the rest. A build that started gets a longer deadline. Either way the request
stays in place, so `dotfiles bundle download` collects the bundle once the
builder answers. A failed build prints the builder's error and the end of its
log.
`docs/architecture/offline-bundles.md` holds the protocol.

**Nothing but packages and versions leaves that machine.**
`src/dotfiles/publishing.py` is the account of both guards standing in front of
the status document — why an allowlist, why a second gate behind it, and why one
row is withheld rather than the whole document refused.

The offline install is rehearsed end to end by
`uv run pytest tests/e2e --docker -k offline`, which builds a bundle, blackholes
the hosts this box's config lists in a container, and asserts the install
converges. `tests/e2e/harness.py` reads the list from that config rather than
keeping its own. Change the bundle format and that is what catches it.

## Windows tools when winget is blocked

The bundle carries them, the same way it carries every other category.

Each `winget_packages` row in `install/packages.yml` names a GitHub repo and
asset alongside the Store id, so one declaration is installable two ways.
`bundle create --machine windows-work-workstation` stages the `.exe` from the
release and verifies it against the published checksum.
`src/dotfiles/providers/winget.py` says which source a run prefers and why that
is decided by what arrived rather than by a mode.

Several of those projects publish no Windows checksum at all. That is stated per
tool rather than passed over, so what was and was not verified stays visible in
the build output.

**Bootstrapping that box runs from the bundle too.** `install.sh` reads
`uname -s`, answers `uv.exe` under Git Bash, and copies `$BUNDLE/bin/uv.exe` onto
PATH, which is the name a Windows bundle stages. With a network but no bundle it
runs astral's PowerShell installer; the sh one is not a fallback there, because it
fetches a Linux binary Git Bash will copy into place and then fail to run. See
`docs/reference/rebuilding-a-machine.md` for what a first install needs.

## Why the Neovim setup does not need any of this

Neovim uses native LSP rather than Mason, so opening an editor does not reach
`raw.githubusercontent.com` at all. Language servers arrive through
`npm_globals` and `uv_tools` in `install/packages.yml` like every other tool,
which means the bundle above already carries them. There is nothing
Neovim-specific to arrange.
