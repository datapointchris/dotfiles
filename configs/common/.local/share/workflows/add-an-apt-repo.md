---
tags: [gpg, apt, keyring, repository, debian, ubuntu, wsl, recipe]
---

# add a third-party APT repo (gpg --dearmor + signed-by, the modern way)

```bash
# GOAL: install a package from a vendor's own APT repo (Docker, InfluxData, ...)
# on Debian/Ubuntu/WSL — fetch its signing key, store it as a keyring, and pin
# the repo to THAT key. This is the modern `signed-by` flow that replaces the
# deprecated `apt-key`. gpg's only job here is --dearmor: ASCII key → binary
# keyring. (This is the actual gpg you use — your secrets are sops/age, not gpg.)

# 1. KEYRING DIR — where per-repo keys live (not the old global trusted.gpg.d)
sudo install -m 0755 -d /etc/apt/keyrings

# 2. FETCH + CONVERT the signing key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
#   --dearmor turns the ASCII-armored key (.asc/.key) into the binary form apt
#   wants. curl -fsSL = fail on error, silent, follow redirects.
sudo chmod a+r /etc/apt/keyrings/docker.gpg      # apt runs as _apt; make readable

# 3. ADD the repo, PINNED to that one key via signed-by
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 4. INSTALL
sudo apt-get update && sudo apt-get install -y docker-ce
```

## The whole thing (template)

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL <KEY_URL> | sudo gpg --dearmor -o /etc/apt/keyrings/<name>.gpg
echo "deb [signed-by=/etc/apt/keyrings/<name>.gpg] <REPO_URL> <suite> <component>" \
  | sudo tee /etc/apt/sources.list.d/<name>.list > /dev/null
sudo apt-get update
```

## Gotchas

```bash
# - `signed-by=` PINS the repo to that key only — a compromised unrelated repo
#   can't sign packages for this one. That's why apt-key (global trust) is dead.
# - --dearmor is for ASCII-armored keys. If the URL already serves a BINARY key,
#   drop the dearmor and `curl -o` it straight to the keyring, or you'll write
#   garbage. (Armored = starts with -----BEGIN PGP PUBLIC KEY BLOCK-----.)
# - Keys go in /etc/apt/keyrings (or /usr/share/keyrings) — NOT trusted.gpg.d.
# - Add `arch=amd64` in the deb line for arch-specific repos, or apt tries to
#   pull the repo for every foreign arch and errors.
# - apt/Debian only — this is not pacman or brew. Relevant on WSL Ubuntu.
```
