---
tags: [eza, ls, listing, tree, git, files]
cadence: 1mo
---

# List and explore directories with eza

> `eza` is the `ls` your muscle memory should reach for. This Lab drills the
> views you actually want day to day — long + git, tree, sorting, filtering — on
> a small tree.

## Setup

Copy this into your other pane to stage a git repo with a modified file:

```bash
LAB=$(mktemp -d) && cd "$LAB"
git init -q
mkdir -p src docs
printf 'a\n' > src/main.rs
touch src/lib.rs docs/readme.md .env
git add src/main.rs && git commit -qm init
printf 'b\n' >> src/main.rs            # now modified vs HEAD
touch -d '10 days ago' docs/readme.md
```

## Steps

1. **Long view with git status.** `eza -l --git`
   - Expect: a long listing with a git column; `src/main.rs` flagged modified.
   - Why: `--git` surfaces per-file status inline, so you see what changed without
     a separate `git status`. `-l` is the long format.

2. **Show hidden.** `eza -la`
   - Expect: `.env` and `.git` now appear.
   - Why: `-a` includes dotfiles. Combine flags freely: `eza -la --git`.

3. **Tree view.** `eza --tree --level=2`
   - Expect: an indented tree, two levels deep.
   - Why: `--tree` replaces the `tree` command; `--level` bounds depth. Add
     `--git-ignore` to skip ignored paths.

4. **Sort by recency.** `eza -l --sort=modified --reverse`
   - Expect: newest first, so the 10-day-old `docs/readme.md` sinks.
   - Why: `--sort` takes name / size / modified / type; `--reverse` flips it.

5. **Directories first, with icons.** `eza -la --group-directories-first --icons`
   - Expect: dirs grouped above files, each with a type glyph (Nerd Font).
   - Why: `--group-directories-first` is the everyday-listing tweak worth making a
     default; `--icons` adds file-type glyphs.

## The whole thing in one breath

```bash
eza -la --git --group-directories-first    # your everyday listing
eza --tree --level=2 --git-ignore          # a quick project map
```
