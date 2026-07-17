---
tags: [eza, ls, listing, tree, git, files]
---

# eza — the `ls` you already run (flags hidden behind the alias)

Your `ls` alias is not `ls`. It expands to:

```bash
eza -l --all --git --git-repos --icons=always \
    --group-directories-first --no-permissions --no-user --no-time
```

So every bare `ls` already gives you: long view, hidden files, a Git-status
column, per-repo status for nested repos, dir-first grouping — with
permissions/owner/time *suppressed* for a clean look. `lsd` is the same minus
contents, `--only-dirs`. The flags below are the ones you reach **past** the
alias for.

## See the fields the alias hides

```bash
eza -l                 # plain long view WITH permissions/owner/time back
eza -lh                # add a header row (-h/--header) labelling each column
eza -l --total-size    # dir sizes = sum of everything inside (unix only)
eza -l -@              # show extended attributes (xattrs) per file
eza -lo                # octal permissions instead of rwx (-o)
eza -l --time-style=iso    # or full-iso / relative / '+%Y-%m-%d %H:%M'
```

The alias drops permissions/user/time on purpose. When you actually need to
audit them, call `eza -l` directly — the alias won't give them back.

## Tree view (the big one the alias can't do)

```bash
eza -T                 # recurse as a tree
eza -T -L 2            # ...cap depth at 2 levels (-L/--level)
eza -T -L 2 --git-ignore   # tree, but skip .gitignored files
eza -Tl --git          # long tree with a Git column per entry
eza -Ta                # include hidden files in the tree
```

`-L` is what keeps a tree from vomiting `node_modules`. Reach for `--git-ignore`
to prune build junk without a manual `-I`.

## Sort — the field is a value, not a flag

```bash
eza -l -s size         # -s/--sort FIELD: size, name, extension, type,
                       #   modified, created, accessed, changed, inode, none
eza -l -s modified -r  # newest last? -r reverses. (date/time/new/old = modified)
eza -l -s size -r      # biggest first
```

Mnemonic: `-s newest` doesn't exist — sort by `modified` (aliased as
`date`/`time`/`new`/`old`) then `-r` to flip which end is on top.

## Narrow what's listed

```bash
eza -D                 # only directories   (--only-dirs; this is `lsd`)
eza -f                 # only files         (--only-files)
eza -d *               # list dirs AS entries, don't descend (-d/--treat-dirs-as-files)
eza -I 'node_modules|*.log'   # ignore glob(s), pipe-separated
eza --git-repos-no-status     # nested-repo BRANCH names only — much faster
                              #   than the alias's full --git-repos scan
```

## Pipe-friendly

```bash
eza -1              # one entry per line — the form to pipe into fzf/xargs
eza -1 -f | fzf     # files only, one per line, into a picker
```

`-1` drops the grid/table so downstream tools get clean lines. The default
`ls` (long+icons) is for *reading*, `-1` is for *feeding*.
