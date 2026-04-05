# neovim marks and jumps

```sql
# Setting marks
ma                set mark 'a' at cursor position (local to buffer)
mA                set mark 'A' at cursor position (global, across files)

# Jumping to marks
'a                jump to line of mark a
`a                jump to exact position of mark a (line + column)
''                jump to last jump position (line)
``                jump to last jump position (exact)

# Special marks (automatic)
'.                last change position
'"                position when last exiting buffer
'[  /  ']         start / end of last yank or change
'<  /  '>         start / end of last visual selection

# View marks
:marks            show all marks
:marks aB         show specific marks
:delmarks a       delete mark a
:delmarks!        delete all lowercase marks

# Jumplist (Ctrl+o / Ctrl+i)
Ctrl+o            go back (older position)
Ctrl+i            go forward (newer position)
:jumps            show jumplist

# Changelist (g; / g,)
g;                go to previous change position
g,                go to next change position
:changes          show changelist

# Common patterns
# Bookmark important locations:  ma at definition, mb at usage
# Return after a search:         Ctrl+o back to where you were
# Hop between two files:         mA in file1, mB in file2, then 'A / 'B
```
