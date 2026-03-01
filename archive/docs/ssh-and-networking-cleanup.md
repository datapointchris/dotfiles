# SSH Config & Networking Cleanup

---

## Current State

**SSH aliases in shell aliases (hardcoded user@ip):**

```bash
alias sshicb='ssh chris@10.0.20.11'
alias sshlearn='ssh chris@10.0.20.12'
alias sshops='ssh chris@10.0.20.15'
alias sshrss='ssh chris@10.0.20.17'
alias pp='ssh chris@10.0.20.15 -t "nvim ~/todo.md"'
```

**`~/.ssh/config`:** Does not exist yet.
**SSH keys:** Arch has none yet. Macs use RSA keys at default path.

---

## Name Resolution: /etc/hosts

Hostname → IP mapping is handled by `/etc/hosts` on each machine, managed in dotfiles.

- `platforms/common/etc.hosts` — shared hosts file for all platforms (not WSL)
- Manually copied to `/etc/hosts` with `sudo cp`

---

## Steps

### 1. Copy hosts file to /etc/hosts

```bash
sudo cp ~/dotfiles/platforms/common/etc.hosts /etc/hosts
```

### 2. Generate SSH key on arch

```bash
ssh-keygen -t ed25519 -C "chris@archlinux"
```

Macs already have RSA keys at `~/.ssh/id_rsa` which SSH finds automatically.

### 3. Copy public keys to servers

```bash
ssh-copy-id chris@ops
ssh-copy-id chris@learning
ssh-copy-id chris@icb
ssh-copy-id chris@rss
```

### 4. Create minimal `~/.ssh/config`

```text
Host *
    AddKeysToAgent yes
    User chris
```

Then `ssh ops` expands to `ssh chris@ops`, /etc/hosts resolves the IP.

### 5. Symlink SSH config from dotfiles

Add to dotfiles symlink management like any other config file.

### 6. Remove SSH aliases

Delete `sshicb`, `sshlearn`, `sshops`, `sshrss` from aliases. Update `pp`:

```bash
alias pp='ssh ops -t "nvim ~/todo.md"'
```

---

## Quick Reference

### SSH key auto-discovery

SSH checks these default paths automatically (no IdentityFile config needed):

- `~/.ssh/id_ed25519`
- `~/.ssh/id_ecdsa`
- `~/.ssh/id_rsa`

### AddKeysToAgent

First SSH in a session prompts for key passphrase, then caches it in ssh-agent for the rest
of the session. No `.zshrc` hacks or manual `ssh-add` needed. Requires ssh-agent running
(standard on desktop Linux and macOS).
