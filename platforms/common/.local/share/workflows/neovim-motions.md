# neovim motions — movement and scrolling

```css
# Character / word movement
h/j/k/l    left/down/up/right
w          start of next word          W    start of next WORD
e          end of current word         E    end of current WORD
b          start of previous word      B    start of previous WORD
0          start of line               $    end of line
^          first non-blank character

# Line jumping
gg         top of file                 G    bottom of file
5G         go to line 5                :42  go to line 42
{          previous blank line         }    next blank line
%          matching bracket

# Screen-relative
H          top of screen
M          middle of screen
L          bottom of screen

# Scrolling
Ctrl+u     half page up                Ctrl+d    half page down
Ctrl+b     full page up                Ctrl+f    full page down
zz         center cursor on screen
zt         cursor to top               zb        cursor to bottom

# Character search (current line)
f{char}    jump to next {char}         F{char}   jump to previous
t{char}    jump before next {char}     T{char}   jump after previous
;          repeat last f/t forward     ,          repeat backward
```

**Jumplist:** `Ctrl+o` back, `Ctrl+i` forward
**Changelist:** `g;` previous change, `g,` next change
