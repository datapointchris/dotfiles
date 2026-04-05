# fzf search syntax

fzf starts in extended-search mode. Multiple terms are delimited by spaces.
Example: `^music .mp3$ sbtrkt !fire`

| Token    | Match type                    | Description                   |
| -------- | ----------------------------- | ----------------------------- |
| sbtrkt   | fuzzy match                   | match sbtrkt                  |
| 'wild    | exact match (quoted)          | include wild                  |
| 'wild'   | exact boundary match          | include wild at word boundary |
| ^music   | prefix exact match            | start with music              |
| .mp3$    | suffix exact match            | end with .mp3                 |
| !fire    | inverse exact match           | do not include fire           |
| !^music  | inverse prefix exact match    | do not start with music       |
| !.mp3$   | inverse suffix exact match    | do not end with .mp3          |

```bash
# Shell integration
Ctrl+r            search command history
Ctrl+t            search files, insert path
Alt+c             cd into selected directory

# Pipe anything into fzf
cat file | fzf                    # pick a line
git branch | fzf                  # pick a branch
ps aux | fzf                      # pick a process

# Open files in editor
nvim -o $(fzf)                    # open selected files in neovim
nvim $(fzf -m)                    # -m for multi-select (tab to mark)
```
