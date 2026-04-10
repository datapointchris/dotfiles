# neovim search and replace

```bash
# Search
/pattern          search forward
?pattern          search backward
n                 next match (same direction)
N                 next match (opposite direction)
*                 search forward for word under cursor
#                 search backward for word under cursor
:noh              clear search highlight

# Search settings
:set ic           ignore case in search
:set smartcase    ignore case unless uppercase used
:set is           incremental search (highlight as you type)
:set hls          highlight all matches

# Replace in current line
:s/foo/bar/       replace first foo with bar
:s/foo/bar/g      replace all foo with bar on line
:s/foo/bar/gc     replace all with confirmation

# Replace in entire file
:%s/foo/bar/g     replace all in file
:%s/foo/bar/gc    replace all in file with confirmation
:%s/foo/bar/gi    replace all, case insensitive

# Replace in range
:5,10s/foo/bar/g  lines 5-10
:'<,'>s/foo/bar/g visual selection (auto-filled)

# Replace with regex
:%s/\v(\w+)/\U\1/g       uppercase all words
:%s/\vfoo(bar)/baz\1/g   capture groups with \v (very magic)

# Useful patterns
:%s/\s\+$//       remove trailing whitespace
:%s/^\n//         remove empty lines
```
