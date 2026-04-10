# broot — interactive directory tree navigation

Note: use `br` (shell function) instead of `broot` so that cd-on-exit works

## Opening

| Command             | Behavior                              |
| ------------------- | ------------------------------------- |
| `br`                | Open tree in current directory        |
| `br ~/projects`     | Open tree at specific path            |
| `br -h`             | Include hidden files                  |
| `br -s`             | Show file sizes                       |
| `br -d`             | Show last-modified dates              |
| `br -hs`            | Hidden files + sizes (flags combine)  |

## Navigation inside broot

| Key / Command       | Behavior                              |
| ------------------- | ------------------------------------- |
| Type anything       | Fuzzy filter the tree                 |
| `↑` / `↓`           | Move selection                        |
| `Enter`             | Descend into directory / open file    |
| `Alt+Enter`         | cd to directory and exit              |
| `Esc`               | Clear filter / go up one level        |
| `Backspace`         | Go to parent directory                |
| `:e`                | Open selected file in `$EDITOR`       |
| `:q`                | Quit without changing directory       |
| `?`                 | Show all verbs (keybinding help)      |

## Filtering patterns

| Pattern             | Matches                               |
| ------------------- | ------------------------------------- |
| `foo`               | Fuzzy: any path containing f, o, o    |
| `/foo`              | Regex search                          |
| `foo/`              | Only directories named foo            |
| `!foo`              | Exclude paths matching foo            |

## Common workflows

```bash
# Find and edit a file deep in a tree
br src
# type partial filename → Alt+Enter or :e

# Check sizes of subdirectories
br -s

# Explore dotfiles without gitignored noise
br ~/dotfiles
```
