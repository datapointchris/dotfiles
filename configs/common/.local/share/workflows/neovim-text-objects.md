# neovim text objects — verb + modifier + noun

Grammar: `{verb}{modifier}{noun}`

**Verbs:** `d` delete, `c` change, `y` yank, `v` visual select
**Modifiers:** `i` inner (contents only), `a` around (contents + delimiters)

| Noun   | Object             | Noun   | Object           |
| ------ | ------------------ | ------ | ---------------- |
| w      | word               | s      | sentence         |
| p      | paragraph          | t      | HTML/XML tag     |
| b or ( | parentheses        | B or { | curly braces     |
| [      | square brackets    | <      | angle brackets   |
| "      | double quotes      | '      | single quotes    |
| `      | backticks          |        |                  |

```sql
# Examples
ciw        change inner word (replace current word)
di(        delete inside parentheses
da"        delete around double quotes (including the quotes)
yip        yank inner paragraph
vat        select around HTML tag (including <tag></tag>)
ci{        change inside curly braces
da[        delete around square brackets

# f/t targeting (on current line)
f;         jump to next ;         F;         jump to previous ;
t;         jump to before next ;  T;         jump to after previous ;
df;        delete through next ;
ct)        change up to (not including) next )
```
