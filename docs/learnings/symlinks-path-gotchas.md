# Two Path Bugs from the Symlinks Python Rewrite

**Date**: 2025-11-04
**Context**: The symlinks manager was rewritten in Python. Both bugs below shipped
in that rewrite and were found by running it, not by the unit tests.

## Substring matching excluded `.gitconfig`

`.gitconfig` stopped being symlinked to the home directory. The exclusion list
contains `.git/`, and the matcher tested it as a substring:

```python
if pattern.endswith('/') and pattern.rstrip('/') in path_str:
    return True  # ".git" is a substring of ".gitconfig"
```

A directory pattern has to match complete path components. That is what
`should_exclude` in `src/dotfiles/symlinks/core.py` matches on.

The pairs that make a substring matcher fail are the ones where a directory name is
a prefix of a real filename — `.git/` against `.gitconfig`, `.gitignore`,
`.gitattributes` and `.github/`; `node_modules/` against `node_modules.txt`;
`tmux/plugins/` against `tmux/tmux.conf`. Every one of those is a file that must
survive. Both directions are pinned by
`test_a_pattern_matches_a_whole_component_and_never_a_prefix` in
`tests/symlinks/test_core.py`, and again at the deploy level in
`tests/resources/test_symlinks.py`.

## Hand-rolled relative paths broke 122 symlinks

The rewrite computed the link target with its own "common ancestor" logic:

```python
common = Path(*[p for p in target_parent.parts if p in source.parts])
levels_up = len([p for p in target_parent.parts if p not in common.parts])
```

It produced `dotfiles/common/init.lua` where the answer was
`../../dotfiles/common/.config/nvim/init.lua`, and every link it wrote was
broken. `make_relative_symlink` in `src/dotfiles/symlinks/core.py` hands the
arithmetic to `Path.relative_to(..., walk_up=True)`, which has the edge cases
already.

The unit tests passed throughout, because they asserted on the computed string
rather than on a link that resolves. A symlink test has to create the link and
read through it — `target.read_text()` is the assertion that would have caught
this on the first run.

## Key Learnings

- **Match path components, never substrings.** For any path pattern, test a
  similar-named sibling that must *not* match.
- **Reach for the stdlib on path arithmetic.** `relative_to(..., walk_up=True)`
  and `os.path.relpath` have the edge cases already.
- **Assert through the symlink, not on the string.** Reading the file proves the
  link works; comparing paths only proves the function is self-consistent.
