---
icon: material/backup-restore
---

# Backup Incremental

Create space-efficient incremental backups using rsync hard links. Each backup appears as a complete snapshot, but unchanged files are hard-linked to previous backups, consuming zero additional disk space.

## Quick Start

```bash
# Basic incremental backup - just backup everything
backup-incremental --name learning ~/learning

# Run it again - unchanged files (like books) are automatically hard-linked
backup-incremental --name learning ~/learning

# Backup to network storage (when you have homelab)
backup-incremental --name learning --network homelab:/mnt/backups ~/learning

# Optional: Exclude specific directories if you want
backup-incremental --name learning --exclude books ~/learning
```

**Key point**: You don't need to exclude anything. Unchanged files (like your books) are automatically hard-linked and consume zero additional space.

## Why Use This Instead of backup-dirs?

**backup-dirs** creates full compressed archives every time - great for one-off backups:

- 5GB backup → 5GB archive
- Another 5GB backup → another 5GB archive
- Total: 10GB stored

**backup-incremental** uses hard links for unchanged files:

- First backup: 5GB (full copy)
- Second backup: 100MB (only changes, rest is hard-linked)
- Third backup: 50MB (only changes)
- Total: 5.15GB stored, appears as 15GB of browsable snapshots

## Commands

**Basic Usage**:

```bash
backup-incremental --name <backup-name> <source-dir>
```

**Options**:

- `-n, --name <name>` - Backup name (required, e.g., "learning")
- `-d, --dest <path>` - Backup destination (default: ~/Documents/backups)
- `--exclude <pattern>` - Exclude pattern (can be used multiple times)
- `--network <host:path>` - Network destination via SSH (e.g., homelab:/mnt/backups)
- `-v, --verbose` - Show detailed rsync output
- `-h, --help` - Show help message

**Examples**:

```bash
# Basic incremental backup
backup-incremental --name learning ~/learning

# Exclude multiple patterns
backup-incremental --name learning \
  --exclude books \
  --exclude temp \
  --exclude .cache \
  ~/learning

# Custom destination
backup-incremental --name dotfiles \
  --dest ~/Backups \
  ~/dotfiles

# Network storage via SSH
backup-incremental --name learning \
  --network homelab:/mnt/backups \
  ~/learning

# Mounted network share
backup-incremental --name learning \
  --dest ~/mnt/homelab/backups \
  ~/learning
```

## How It Works

**First Backup** (Full):

```text
~/Documents/backups/learning/
└── learning_2025-12-11_100000/     (5.0 GB)
    ├── books/                       (3.0 GB)
    ├── docs/                        (2.0 GB)
    └── latest → learning_2025-12-11_100000
```

**Second Backup** (Incremental):

You modify some documents but books are unchanged.

```text
~/Documents/backups/learning/
├── learning_2025-12-11_100000/     (5.0 GB)
│   ├── books/                       (3.0 GB)
│   └── docs/                        (2.0 GB)
├── learning_2025-12-11_140000/     (100 MB new data)
│   ├── books/                       (hard links to previous backup)
│   └── docs/                        (modified files + hard links to unchanged)
└── latest → learning_2025-12-11_140000
```

**Actual disk usage**: 5.1 GB
**Apparent size**: 10 GB (two complete snapshots)

The `books/` directory in the second backup doesn't consume any extra space - the files are hard-linked to the first backup's books directory.

## Storage Example

Real-world scenario for `~/learning` with large static books:

| Backup | Changes | New Data | Disk Used | Appears As |
|--------|---------|----------|-----------|------------|
| #1 | Full backup | 5.0 GB | 5.0 GB | 5.0 GB |
| #2 | Modified 100MB of docs | 100 MB | 5.1 GB | 10 GB |
| #3 | Modified 50MB of docs | 50 MB | 5.15 GB | 15 GB |
| #4 | Modified 200MB of docs | 200 MB | 5.35 GB | 20 GB |

After 4 backups: **5.35 GB actual storage**, **20 GB browsable snapshots**

## Network Storage Setup

### Option 1: SSH Direct (Easiest)

No mounting required - rsync uses SSH to transfer files directly:

```bash
# One-time setup: Configure SSH key auth to your homelab
ssh-copy-id homelab

# Backup to homelab over network
backup-incremental --name learning --network homelab:/mnt/backups ~/learning
```

**Pros**: No mounting, works anywhere with SSH access
**Cons**: Slower than local/mounted storage

### Option 2: Mount Network Share

Mount homelab storage locally, then use as local destination:

**NFS Mount**:

```bash
# One-time setup: Mount homelab NFS share
mkdir -p ~/mnt/homelab
sudo mount -t nfs homelab:/mnt/backups ~/mnt/homelab

# Or add to /etc/fstab for automatic mounting
echo "homelab:/mnt/backups /Users/chris/mnt/homelab nfs rw,soft,intr 0 0" | sudo tee -a /etc/fstab

# Backup to mounted share
backup-incremental --name learning --dest ~/mnt/homelab ~/learning
```

**SMB/CIFS Mount**:

```bash
# One-time setup: Mount homelab SMB share
mkdir -p ~/mnt/homelab
sudo mount -t smbfs //homelab/backups ~/mnt/homelab

# Backup to mounted share
backup-incremental --name learning --dest ~/mnt/homelab ~/learning
```

**Pros**: Fast as local storage, works offline if cached
**Cons**: Requires mounting, may disconnect

### Homelab Recommendations

For a dedicated backup server/homelab:

1. **Dedicated disk for backups**: Separate physical disk reduces failure risk
2. **RAID 1 or ZFS mirror**: Protect against single disk failure
3. **Regular disk checks**: Set up SMART monitoring
4. **Offsite copy**: Periodically copy critical backups to cloud/external drive

**Example homelab setup**:

```text
Homelab server:
├── /dev/sda (OS disk)
│   └── Main system
└── /dev/sdb (Backup disk - dedicated)
    └── /mnt/backups
        ├── learning/
        ├── dotfiles/
        └── projects/
```

## Workflow

**Daily/frequent backups**:

```bash
# Just backup everything - unchanged files are automatically hard-linked
backup-incremental --name learning ~/learning

# Optional: Exclude specific directories if you want
backup-incremental --name learning --exclude books ~/learning
```

**Weekly/monthly backups of static content**:

```bash
# Full backup including books (less frequent)
backup-incremental --name learning-full ~/learning
```

**When setting up homelab**:

```bash
# Test connection
ssh homelab

# Create backup directory on homelab
ssh homelab "mkdir -p /mnt/backups"

# Run backup to homelab via SSH
backup-incremental --name learning --network homelab:/mnt/backups ~/learning

# Or mount homelab storage and use as local destination
mkdir -p ~/mnt/homelab
sudo mount -t nfs homelab:/mnt/backups ~/mnt/homelab
backup-incremental --name learning --dest ~/mnt/homelab ~/learning
```

**Browse previous backups**:

```bash
# List all learning backups
ls -lh ~/Documents/backups/learning/

# Browse a specific backup
cd ~/Documents/backups/learning/learning_2025-12-11_140000
ls -lh

# Restore a specific file
cp ~/Documents/backups/learning/learning_2025-12-11_140000/docs/important.md ~/learning/docs/
```

## Comparison with backup-dirs

| Feature | backup-dirs | backup-incremental |
|---------|-------------|-------------------|
| **Storage** | Full compressed archive each time | Only stores changes |
| **Speed** | Slower (compression) | Faster (rsync) |
| **Portability** | Single file, easy to move | Directory structure |
| **Browse** | Must extract first | Instantly browsable |
| **Network** | Manual copy after creation | Built-in SSH support |
| **Best for** | One-off backups, archival | Frequent backups, large datasets |

**Use backup-dirs when**:

- Creating archives to share or move
- One-off backups before risky operations
- Archival storage (compressed)

**Use backup-incremental when**:

- Backing up frequently (daily/weekly)
- Large directories with small changes
- Network backup to homelab
- Need to browse/restore without extracting

## See Also

- [backup-dirs](backup-dirs.md) - Compressed full backups
- [Tool Composition](../architecture/tool-composition.md) - How tools work together
