# ripgrep — common search patterns

```bash
# Basic search (recursive by default, respects .gitignore)
rg foo                            # search current directory
rg foo src/                       # search specific directory
rg foo README.md                  # search specific file

# File type filters
rg -t py foo                      # only Python files
rg -t js -t ts foo                # JavaScript and TypeScript
rg -T test foo                    # exclude test files
rg --type-list                    # show all known file types

# Pattern matching
rg 'fn \w+'                       # regex: function definitions
rg -w foo                         # whole word only
rg -i foo                         # case insensitive
rg -F 'foo(bar)'                  # fixed string (no regex)
rg -v foo                         # invert match (lines NOT matching)

# Output control
rg -l foo                         # list filenames only
rg -c foo                         # count matches per file
rg -n foo                         # show line numbers (default)
rg --no-filename foo              # suppress filenames

# Context
rg -C 3 foo                       # 3 lines before and after
rg -B 2 foo                       # 2 lines before
rg -A 5 foo                       # 5 lines after

# Advanced
rg -U 'struct \{.*\n.*field'      # multiline search
rg --glob '*.go' foo              # glob filter
rg --glob '!vendor/' foo          # exclude directory
rg -g '!*.test.*' foo             # exclude test files by pattern
rg foo --json | jq                # structured output
```
