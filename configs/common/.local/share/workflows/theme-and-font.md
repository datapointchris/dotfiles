---
tags: [theme, font, ghostty, tmux, nvim, restyle, personal-tools]
---

# theme + font — restyle the whole terminal (parallel command sets)

Two personal tools with the **same verb structure**. `theme` restyles every app
at once (ghostty, tmux, btop, nvim, waybar, rofi, dunst, browsers); `font`
swaps the typeface in ghostty + nvim. Both auto-log every change and rank by
your like/dislike history, so the picker learns. Your churn loop is usually
`theme change → font change → btop` to see it land.

## The shared verbs (identical on both)

```bash
theme change        font change        # interactive picker WITH live preview — the default
theme current       font current       # what's active right now
theme apply <name>  font apply <name>  # apply by exact name (auto-logs)
theme random        font random        # surprise me (respects rejections)
theme like [msg]    font like [msg]    # ↑ rank the current one, optional reason
theme dislike [msg] font dislike [msg] # ↓ rank it
theme note <msg>    font note <msg>    # attach a note (msg required)
theme rank          font rank          # leaderboard by likes/usage
theme log           font log           # full history
theme list          font list          # plain names (theme list / font families)
theme info [name]   font info [name]   # browse + detailed per-item history
```

Reach for `change` (fzf + preview), not `apply`, unless you already know the
exact name. `apply` is for scripts and "put back the one I know."

## Reject vs dislike (the distinction that matters)

```bash
theme dislike "too low contrast"   # down-ranks, but it still SHOWS in pickers
theme reject  "unreadable"         # hides it so random/change never resurface it
theme rejected                     # list what you've banished
theme unreject                     # fzf-restore a rejected one (shows why you rejected)
```

`dislike` = "meh, rank it down." `reject` = "never show me this again." Same
pair exists on `font`. Use `reject` to stop re-discovering the same dud.

## font-only

```bash
font last            # toggle back to the previous font (A/B two candidates)
font size-up         # +1  (also size-down)
font size-down       # -1
font install --check # which curated fonts are missing
```

## theme-only subcommands (run each bare for usage)

```bash
theme background rotate   # new wallpaper, SAME theme
theme opacity set 90      # terminal opacity 0–100
theme preview [name]      # preview in tmux (fzf picker if no name given)
theme verify              # sanity-check the theme system is wired up
theme browsers            # browser-theme status + setup
```

## Cross-machine sync (both tools, via GitHub Gist)

```bash
theme sync status    font sync status    # is auto-sync on, are we behind?
theme sync push      font sync push      # force your state up
theme sync pull      font sync pull      # force remote state down
```

Auto-sync is on by default — `sync push/pull` are the manual overrides when a
machine drifted. `sync init` first-time only.

## Keeping the tools current

```bash
theme upgrade        font upgrade        # pull latest release of the tool itself
```

These are the personal CLIs (git-clone + symlink install pattern). `upgrade`
updates the tool; it does **not** touch your theme/font choices.
