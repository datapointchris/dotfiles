# neovim registers — clipboard and yank history

```text
# Using registers: "{register}{action}
"ayy              yank line into register a
"ap               paste from register a
"Ayy              append line to register a (uppercase = append)

# Special registers
""                default register (last delete/yank)
"0                last yank (not affected by deletes)
"1-"9             delete history (1 = most recent)
"+                system clipboard
"*                system selection (X11) / clipboard (macOS)
"/                last search pattern
":                last command
".                last inserted text
"%                current filename
"#                alternate filename

# View registers
:reg              show all registers
:reg a            show register a
:reg +0           show clipboard and yank register

# Common patterns
# Yank to clipboard:            "+yy  or  "+yiw
# Paste from clipboard:         "+p
# Delete without clobbering:    "_dd  (black hole register)
# Paste last yank after delete:  "0p

# In insert mode
Ctrl+r a          insert contents of register a
Ctrl+r +          insert from clipboard
Ctrl+r /          insert last search pattern
Ctrl+r =          insert expression result (calculator)
```
