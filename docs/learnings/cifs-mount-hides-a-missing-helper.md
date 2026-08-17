# A CIFS Mount Hides a Missing Helper

## Problem

A freshly installed WSL Ubuntu distro could not mount the work network drive.
`mount-h`, a wrapper around `mount-cifs` in the work box's machine-local
`~/.local/shell/local.sh`, failed with:

```text
mount error(113): No route to host
```

Every signal pointed at the network, and all of it was wrong. The older distro on
the same Windows host mounted the identical share, `getent hosts` returned the same
address on both, and `/etc/resolv.conf`, `/etc/wsl.conf` and `/etc/hosts` matched
line for line. The real cause was that `cifs-utils` had never been installed on the
new distro — it had been installed by hand on the old one, years earlier, and
nothing in this repo declared it.

The error misleads because of what `mount` does when the helper is absent. With
`/sbin/mount.cifs` present, mount(8) hands the share to it and the helper resolves
the hostname in userspace. Without it, mount(8) issues the mount syscall directly,
and the kernel's cifs module has to resolve the name itself through the
`dns_resolver` upcall — which invokes `cifs.upcall`, also shipped by cifs-utils.
The upcall fails, the module never obtains an address, and it surfaces that as an
unreachable host rather than as a missing helper.

## Solution

Declare the dependency where the machine build reads it, so a rebuilt distro gets
it without anyone remembering. `install/packages.yml` carries an apt-only entry. An
entry without a key for the running package manager is skipped, so Arch and macOS
ignore this one with no placeholder values:

```yaml
- name: cifs-utils
  apt: cifs-utils
  description: CIFS/SMB mount helper (required by the WSL mount-* functions)
```

It is untagged, so it lands in the workstation tier that
`wsl-work-workstation.yml` requests, and stays off the LXC servers that ask for
`core`.

## Key Learnings

- A shell function that shells out to a binary is an undeclared dependency until
  that binary is in `packages.yml`. It looks permanently fixed on the machine where
  it was installed by hand, and the debt comes due on the next rebuild — here,
  after enough time that the original fix had been forgotten entirely.
- All WSL2 distros share one utility VM, one kernel, and one `eth0`. Anything a
  working distro can reach, a new one can too, which eliminates routing, DNS and
  `.wslconfig` in a single step and leaves only per-distro userspace.
- An errno is the last handler's opinion, not a diagnosis. `EHOSTUNREACH` came from
  a module that had no address to try, not from a network that refused one.
