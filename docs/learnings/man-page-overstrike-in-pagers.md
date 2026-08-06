# Man Page Overstrike in Pagers

## Problem

`aws s3 rm help` printed control characters through the whole page:

```text
N^HNA^HAM^HME^HE
       rm -

D^HDE^HES^HSC^HCR^HRI^HIP^HPT^HTI^HIO^HON^HN
```

This is not corruption and not an AWS bug. `N^HN` is nroff **overstrike**: print
the character, backspace, print it again, which bolded text on a printer that had
no escape sequences. `_^Hx` is the underline form. `man` output is encoded the
same way — `MANPAGER=cat man ls` yields 183 lines containing `\x08` and zero ANSI.

Nothing decodes overstrike except `less`, `col -b`, and `ul`. bat passes it
through untouched, even with `--language=man`, so it surfaced anywhere less was
not in the chain: piping `aws … help` into another command, or redirecting it.

Two settings made it worse:

- `GROFF_NO_SGR=1`, half of a colored-man-pages block, told groff to keep using
  the legacy overstrike output instead of the ANSI SGR it emits by default, so
  `LESS_TERMCAP_*` could paint it. That only works when less is the pager.
- awscli reads `MANPAGER` **before** `PAGER` (`awscli/help.py:135`), renders help
  with `groff -m man -T ascii`, and falls back to `mandoc -T ascii` when groff is
  absent — which it is on macOS, since Ventura replaced groff with mandoc.

## Solution

Filter the overstrike out before bat ever sees it:

```sh
export MANPAGER="sh -c 'col -bx | bat --language=man'"
```

`col -b` drops the backspace pairs, `-x` expands tabs. bat then colors the page
from the active theme, and the same variable fixes `aws <cmd> help` because aws
prefers `MANPAGER`. `LESS_TERMCAP_*` and `GROFF_NO_SGR` were removed with it.

## Key Learnings

- Overstrike is the formatter's output, not a broken tool. Search for `^H`, not
  for the command that printed it.
- **mandoc ignores `GROFF_NO_SGR`** — it has no SGR mode. On macOS that variable
  never did anything; the overstrike is unconditional. It only affects Linux,
  where man-db drives real groff. `col -bx` is immune to the difference.
- A pager that is not `less` inherits none of less's roff handling. Anything
  setting `PAGER`/`MANPAGER` to bat, delta, or moar needs `col -b` in front.
- `col` lives in `bsdextrautils` on Debian/Ubuntu, `util-linux` on Arch, and
  `/usr/bin/col` on macOS — see the entry in `install/packages.yml`.

## Testing

```bash
man ls | rg -c $'\x08'                       # 183 — raw formatter output
man ls | col -bx | rg -c $'\x08' || echo 0   # 0 — after filtering
MANPAGER="sh -c 'col -bx | bat -l man'" aws s3 rm help
```
