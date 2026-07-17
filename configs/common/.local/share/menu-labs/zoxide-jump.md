---
tags: [zoxide, cd, navigation, jump]
cadence: 1mo
---

# Jump around with zoxide

> `z` is `cd` that remembers where you've been. This Lab drills jumping by
> substring, frecency ranking, multiple keywords, and the interactive picker —
> against an isolated database so your real one stays untouched.

## Setup

Copy this into your other pane. The `_ZO_DATA_DIR` export points `z` at a
throwaway database for this session; `zoxide add` seeds it, visiting `webapp`
twice so it out-ranks its sibling:

```bash
LAB=$(mktemp -d) && cd "$LAB"
export _ZO_DATA_DIR="$LAB/.zoxide"        # isolate — your real db is untouched
mkdir -p projects/webapp archive/oldapp notes/2026
zoxide add "$LAB"/projects/webapp "$LAB"/archive/oldapp "$LAB"/notes/2026
zoxide add "$LAB"/projects/webapp         # visit webapp again → higher rank
```

## Steps

`z` is the shell function zoxide installs; it works in your interactive pane.

1. **Jump by the last path component.** `z 2026`
   - Expect: your cwd becomes `.../notes/2026`.
   - Why: the final keyword matches the *basename* of a directory zoxide has seen.
     No full path, no tab-completion — just enough of the leaf name.

2. **Substrings count.** `z old`
   - Expect: `.../archive/oldapp` (basename `oldapp` contains `old`).
   - Why: the keyword need only be a substring of the basename, so short fragments
     work.

3. **Frecency breaks ties.** `z app`
   - Expect: `.../projects/webapp`, even though `oldapp` also matches `app`.
   - Why: both basenames contain `app`, but you visited `webapp` twice — ranking
     is by *frecency* (frequency + recency), so the more-used one wins.

4. **Disambiguate with a leading keyword.** `z arch app` then `z pro app`
   - Expect: `archive/oldapp`, then `projects/webapp`.
   - Why: earlier keywords match anywhere *before* the basename. `arch app` pins
     the parent (`archive`) plus the leaf (`app`) — the clean way to pick between
     two similar leaves.

5. **Pick interactively.** `zi`
   - Expect: an fzf list of tracked directories; choose one to jump.
   - Why: `zi` is the fallback when you can't recall the keyword — the same fzf
     picker, over your zoxide database. `zoxide query -l` prints that list plainly.

## Notes

- Back in a normal pane (no `_ZO_DATA_DIR`), `z` uses your real database again, so
  closing this pane is all the cleanup needed. Every `cd` you make is tracked
  automatically — the more you navigate, the smarter the ranking gets.
