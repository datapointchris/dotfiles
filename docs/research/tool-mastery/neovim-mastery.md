---
icon: material/language-lua
---

# Neovim Mastery

The editor-side of all three jobs: discovering your own keymaps, recording which motions you
actually use, and drilling the efficient ones into muscle memory. You already have a "nvim
skill" that helps *find* commands (Job 1); this covers the recording and retention gaps.

The one structural finding to hold onto: **no plugin does command-level composition analysis.**
`vim.on_key` sees raw keys (`c`, `i`, `(`) — not composed commands (`ci(`). So "you used `dd`
400× but never `ci(`" — the report you'd most want — is a build-your-own. Everything else has
good off-the-shelf answers.

Research date: 2026-07-07.

## Discovery — find and remember your own mappings

- **[which-key.nvim](https://github.com/folke/which-key.nvim)** — popup of available
  continuations as you type a prefix; built-in helpers for marks, registers, operators,
  text-objects. Pure discoverability, no analytics. Descriptions come from your keymap `desc`
  fields — so *writing good `desc` strings is the single-source-of-truth move* (it feeds
  which-key, telescope, and any generated cheatsheet).
- **[legendary.nvim](https://github.com/mrjones2014/legendary.nvim)** — command-palette over
  keymaps/commands/autocmds, **sorted by frecency** (frequency + recency of what you pick
  *through legendary*). Good if you want a searchable "what can I do" palette that floats your
  actual habits to the top. Caveat: frecency reflects picks through the palette, not raw
  keystrokes.
- **`:Telescope keymaps` / `:Telescope commands`** — zero-setup live fuzzy list of all active
  mappings. Always in sync (reads Neovim's live tables), but ephemeral — no export, no
  frequency.
- **[mini.clue](https://github.com/nvim-mini/mini.clue)** / **[hydra.nvim](https://github.com/nvimtools/hydra.nvim)**
  — next-key clues and repeatable submodes (window resize, etc.). Efficiency-of-repetition more
  than discovery.

## The always-in-sync cheatsheet — keymaps.nvim ⭐

[github.com/abdul-hamid-achik/keymaps.nvim](https://github.com/abdul-hamid-achik/keymaps.nvim).
This is the best single answer to "a self-generated cheatsheet that never drifts" **and** "which
of my mappings do I actually use":

- Scans **all** keymaps via `nvim_get_keymap()` across modes, uses `debug.getinfo()` to attribute
  each mapping to the plugin/file that defined it, and auto-groups into categories (LSP, Git,
  Navigation, Telescope…).
- Searchable via telescope or a floating window — and because it reads live keymaps, **the
  cheatsheet is always in sync with your config** (the drift fix, editor-side).
- `:KeymapsExport` → **markdown / HTML / JSON** — generate a committed cheatsheet from your
  actual config.
- `track_usage = true` → `:KeymapsStats` shows which mappings you actually invoke and how often.

**Caveat:** it tracks *mapped keymaps*, so it catches your custom `<leader>` mappings but not
built-in motions like `ci(`. That's the composition-analysis gap again.

A dependency-free alternative that fits the dotfiles ethos: a ~30-line Lua script that dumps
`nvim_get_keymap(mode)` per mode to a markdown table on a user command — a committed,
regenerated-on-demand cheatsheet living in the repo. This mirrors what `workflows` does for the
shell.

## Recording — which keys/motions you actually press

- **[keylog.nvim](https://github.com/glottologist/keylog.nvim)** — logs keystrokes to a flat
  file `~/.local/share/nvim/keystroke.log` (for heatmaps). Simplest "log to a file I analyze
  myself." `:Keylog enable|disable|clear`.
- **[keystats.nvim](https://github.com/OscarCreator/keystats.nvim)** — `vim.on_key` counts to a
  DB, but requires a Cargo/Rust build step. Higher effort, early-stage.
- **[usage-tracker.nvim](https://github.com/gaborvecsei/usage-tracker.nvim)** — time per
  file/project/filetype + keystroke *count* per file, with built-in in-nvim reports
  (`:UsageTrackerShowAgg`, bar charts). More "where do I spend time" than "which motions."
- **DIY `vim.on_key`** — `vim.on_key(function(key, typed) … end)` fires on every key; append to a
  file (buffered, flush every N strokes) or to SQLite via
  [sqlite.nvim](https://github.com/3rd/sqlite.nvim). Then analyze offline. **Known gotchas:** can
  stick at "Press ENTER" prompts ([#30752](https://github.com/neovim/neovim/issues/30752)),
  `<Nop>` mappings suppress the callback ([#30311](https://github.com/neovim/neovim/issues/30311)),
  and it sees individual keys — so getting `ci(`-level stats means writing an operator+motion
  state machine yourself. That state machine is the missing capability no plugin provides, and
  the highest-value editor-side build if you want the "motions you never use" report.

## Coaching — break the inefficient habits

- **[hardtime.nvim](https://github.com/m4xshen/hardtime.nvim)** ⭐ — counts repeated presses of
  the same key; past a threshold it either **blocks** the keystroke (forcing `5j`, `f`,
  text-objects) or shows a **hint** ("use `ci(` instead"). Tunable: `restriction_mode`
  block↔hint, `disabled_keys` (many long-time users say *disabling arrow keys* was the single
  biggest improvement — elimination beats reminding), `max_count`/`max_time` for leniency.
  **`:Hardtime report`** shows your most-triggered bad habits, logged to
  `~/.local/state/nvim/hardtime.nvim.log` — directly analyzable, and it tells you exactly which
  motions to put in your drill deck. The HN consensus: *configurability is what makes forced
  approaches tolerable* — you choose which habits to break.
- **[precognition.nvim](https://github.com/tris203/precognition.nvim)** — virtual text + gutter
  signs showing available motions *from the cursor* (`w e b $ ^`, `gg G { }`, targeted
  `f`/`t`). Pure ambient hinting; `:Precognition peek` shows until the next move. Pairs
  explicitly with hardtime: precognition shows what's possible, hardtime blocks the lazy
  fallback — the hint enables the recall, the block forces it.

## Drilling — checked practice

- **[vimhjkl](https://github.com/S-Sigdel/vimhjkl)** — shows a target state, checks your
  keystrokes against optimal, Leitner-scheduled, efficiency-graded. The active-recall drill for
  motions (also in the retention doc).
- **[vim-be-good](https://github.com/ThePrimeagen/vim-be-good)** — motion mini-games.
- **`vimtutor` daily for a week** — the [Peter Jang plan](https://peterxjang.com/blog/how-to-learn-vim-a-four-week-plan.html)'s
  week 1; run to fluency before reaching for plugins-as-crutch.

## Recommended nvim stack

Mapped to the three jobs:

- **Discovery / always-in-sync cheatsheet:** `keymaps.nvim` (`:KeymapsExport` to markdown,
  committed to the repo) — or the ~30-line `nvim_get_keymap` dump. Plus disciplined `desc`
  strings so which-key/telescope stay useful. This likely *replaces or feeds* your current "nvim
  skill" so the reference is generated, not hand-maintained.
- **Recording:** `keylog.nvim` (log-only, cheap) now; a `vim.on_key` → sqlite tracker with a
  composition pass later if you want the `dd`-vs-`ci(` report.
- **Coaching:** `hardtime.nvim` in **hint** mode → **block** mode as habits form; mine
  `:Hardtime report` to pick drill targets. `precognition.nvim` in peek mode as the paired hint
  layer.
- **Drilling:** `vimhjkl` for the motions hardtime keeps flagging.

The pipeline mirrors the shell side: `hardtime` report (data) → `vimhjkl`/deck (drill) →
`keymaps.nvim` export (reference). Same three jobs, editor edition.

## Sources

- which-key <https://github.com/folke/which-key.nvim> · legendary <https://github.com/mrjones2014/legendary.nvim> · mini.clue <https://github.com/nvim-mini/mini.clue> · hydra <https://github.com/nvimtools/hydra.nvim>
- keymaps.nvim <https://github.com/abdul-hamid-achik/keymaps.nvim> · sqlite.nvim <https://github.com/3rd/sqlite.nvim>
- keylog.nvim <https://github.com/glottologist/keylog.nvim> · keystats.nvim <https://github.com/OscarCreator/keystats.nvim> · usage-tracker.nvim <https://github.com/gaborvecsei/usage-tracker.nvim>
- hardtime.nvim <https://github.com/m4xshen/hardtime.nvim> · HN <https://news.ycombinator.com/item?id=44020734> · precognition.nvim <https://github.com/tris203/precognition.nvim>
- vimhjkl <https://github.com/S-Sigdel/vimhjkl> · vim-be-good <https://github.com/ThePrimeagen/vim-be-good>
- `vim.on_key` docs <https://neovim.io/doc/user/lua.html> · keyfreq reference (emacs) <https://github.com/dacap/keyfreq>
