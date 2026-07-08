---
icon: material/book-search
---

# Discovery & the Terminal Docs Browser

**Job 1 of 3.** The question: *"What do I have and how do I use it — right now, in the
terminal, without a browser?"* This is recognition-mode, point-of-need lookup, and it is where
your "a terminal docs browser for only my shit" instinct belongs.

The problem is not that you lack lookup tools — you have `workflows`, `cheat`, `tldr`,
`toolbox`, `menu`, and the mkdocs site. The problem is there are **five or six front doors**,
none unified, and the richest one (mkdocs) needs a browser and drifts out of sync. This
document surveys the prior art and the design options for collapsing them.

Research date: 2026-07-07.

## The design tension: view vs. execute vs. derive

Every tool in this space sits somewhere on two axes. Naming them makes the choice legible:

- **View ↔ Execute** — does the tool *show you a reference page* (read it, remember, type it
  yourself) or *run the command for you* (prompting for arguments)? Your `workflows` cards are
  View. navi is Execute.
- **Hand-authored ↔ Auto-derived** — is the content written and maintained by you (drifts
  unless disciplined) or generated from the tool's own `--help` / arg parser (cannot drift)?

Your "goes out of sync" pain is the second axis. Your "quick in the terminal" pain is a
front-door / speed problem, not a content problem.

## Option A — navi (execute-oriented, parameterized)

[github.com/denisidoro/navi](https://github.com/denisidoro/navi). Rust. Interactive cheatsheet
tool that **runs** the selected command, prompting for argument values via fzf.

- **Format** (`.cheat` files): `%` tags a file, `#` describes a command, plain lines are the
  command with `<placeholders>`, and `$ var: <shell command>` generates fzf-suggestion lists
  for a placeholder. So a cheat is an *executable, parameterized* snippet, not static text.
- **Shell widget:** `source <(navi widget zsh)` binds **Ctrl-G** to open the fuzzy cheatsheet
  and drop the assembled command onto your prompt (it enters history — reinforcing muscle
  memory). `navi --print` prints instead of running.
- **Personal cheats** live in `~/.local/share/navi/cheats/` and are just a git repo you
  `navi repo add`. Fits the dotfiles-via-git model exactly.
- **Bridges:** `navi --tldr <q>` and `navi --cheatsh <q>` pull from those sources on demand.

**Strengths:** the `<var>` + `$` generator mechanism is unique — it teaches *usage* (fill in
real branch names, real files) not just existence, and one keystroke turns "I vaguely remember
this tool" into a run command. **Weaknesses:** execution-oriented, so it is heavier than needed
if you only want to *read* how a tool works; content is hand-authored (drifts).

**Best when:** you want to *run* your own tools with varying arguments fast — e.g. `backmeup`,
`safekeep`, `syncer` incantations you can never remember the flags for.

## Option B — cheat (view-oriented, one page per command)

[github.com/cheat/cheat](https://github.com/cheat/cheat). Go. Already installed and configured
in this repo (`~/.config/cheat/conf.yml` symlinked from dotfiles; community sheets present).
Viewer-first.

- **Format:** plain text, one file per command, optional YAML front matter (`syntax:` drives
  Chroma highlighting, `tags:`).
- **Cheatpaths:** multiple directories, each `readonly` or writable. Ships a **community**
  (readonly) path + your **personal** path. Editing a readonly sheet transparently copies it to
  your writable path first — so you override community docs without touching them.
- **Directory-scoped sheets:** auto-discovers `.cheat/` dirs in the cwd and ancestors (like
  `.git`), enabling per-project cheatsheets.
- **fzf** is not built in but `cheat -l | fzf` is the standard wrapper.

**Strengths:** cleanest model for *reading* "how do I use this tool" as a real page, with the
readonly-community / writable-personal split you already have set up. **Weaknesses:** static
(no argument prompting); fzf is DIY; you are already under-using it.

**Best when:** you want a per-command reference page you read, not run.

## Option C — um (your own man pages) ⭐ closest to the stated intent

[github.com/sinclairtarget/um](https://github.com/sinclairtarget/um). Ruby. Purpose-built for
"maintain my own man pages." Its pitch is verbatim your problem: *"Man pages are written to be
comprehensive, but what humans really need are the bullet points."*

- `um edit <topic>` creates/edits a markdown page in `$EDITOR`; `um <topic>` views it in the
  pager; `um list`; `um rm`. Storage is `~/.um` — a plain directory of markdown, trivially
  git-tracked and fzf-browsable.
- Renders markdown *as actual man pages* (via Kramdown), so your notes look and page like
  `man`. Templates with `$name`/`$date`/etc. for new pages.

**Strengths:** the single tool most aligned with "create and maintain terminal docs for exactly
my own tools." Plain markdown in a dir = fits dotfiles, offline, no service. **Weaknesses:** no
native fzf or git sync (both trivial to add); Ruby dependency; content hand-authored.

**Best when:** you want a curated, prose-lite reference for *your* tools that reads like `man`
and lives in git. This is the strongest literal answer to "a terminal docs browser for only my
shit" — though your `workflows` app already occupies most of this niche (see "the honest
question" below).

## Option D — DIY fzf + bat over a markdown directory (lightest, most dotfiles-native)

The "build it from a folder of text + fzf + bat" category. This is essentially what `workflows`
already is, so these are references for *extending* it rather than adopting something new.

- **[james-w/fzf-cheatsheets](https://github.com/james-w/fzf-cheatsheets)** — one file per
  command, one command per line, `# inline comment` descriptions. Ctrl-x Ctrl-p picks a sheet
  then a command; **Enter places it on your prompt**; Ctrl-e edits first. Pure shell.
- **[Xav-Deb/zsh-cheatsheet](https://github.com/Xav-Deb/zsh-cheatsheet)** — a ZLE widget that
  inserts the chosen command *under the cursor* without clearing your line. **Context-aware:**
  type `git`, hit the hotkey → opens `git.md`; unknown command → global search. Markdown
  contract: one `# <cmd>` header, `## <Category>` sections, `` - `command` — description ``
  entries.
- **The fzf inline-comment alias picker** ([fzf discussion #2982](https://github.com/junegunn/fzf/discussions/2982))
  — aliases carry `# description` comments; `rg` extracts and colorizes them; fzf preview uses
  `bat` to show the alias in-file; Enter drops the real command on the prompt. This is the
  cleanest "descriptions are free, the picker is the review surface" implementation found.

**Strengths:** zero external service, offline by definition, lives in the git-tracked repo, and
you already own the pattern. **Weaknesses:** you maintain the parser; content hand-authored
unless fed from `--help`.

**Best when:** you want to *unify* the existing doors (see the consolidation doc) rather than
add a tool. The context-aware ZLE insert is the ergonomic upgrade `workflows` is missing.

## Option E — tldr / tealdeer custom pages (augment what you already type)

[tealdeer custom pages](https://tealdeer-rs.github.io/tealdeer/usage_custom_pages.html). You
already run `tldr`.

- Drop `<tool>.page.md` in the custom-pages dir (run `tldr --show-paths`) to show *your* page
  instead of the upstream one. Or `<tool>.patch.md` to **append** personal examples to an
  official page.
- Offline after `tldr --update`.

**Strengths:** cheapest way to slot your own tools into a lookup surface you already use — `tldr
backmeup` just works. **Weaknesses:** not a browser (you must know the command name); no tag/
fuzzy browse of only your pages; a bolt-on to a community-repo model.

## Option F — cheat.sh (broad third-party reference, weak for private tools)

[github.com/chubin/cheat.sh](https://github.com/chubin/cheat.sh). Aggregates tldr-pages, "Learn
X in Y", StackOverflow. `cht.sh tar~extract`, `cht.sh --shell` REPL. Great as a broad *external*
reference, but personal sheets require running the local server or upstreaming — heavier than
tealdeer's drop-a-file model and not aimed at private in-house tools. Keep for the long tail of
third-party questions; not a home for your own CLIs.

## The drift problem: auto-derive docs from `--help`

This is the direct fix for "it goes out of sync." Instead of hand-writing option references,
**generate them from the tool's own definition** so they cannot lie:

- **[help2man](https://www.gnu.org/software/help2man/)** — generates a man page from any
  program's `--help`/`--version`. In a build, make the man page depend on the *source* that
  defines `--help`, so it regenerates on change. Augment with hand-written EXAMPLES via
  `--include` while OPTIONS stays auto-derived.
- **Framework generators** — since your `~/tools` are mostly Go (Cobra): `cmd.GenManTree()` and
  `cmd.GenMarkdownTree()` emit man/markdown straight from the command definitions. Python Click
  (`click-man`), argparse (`argparse-manpage`), Rust clap (`clap_mangen`) do the same.

The pattern: **auto-derive the *option reference* from `--help`; hand-write only the *"how I
actually use it"* examples** (in `workflows` / `um` / `cheat`). The mechanical part can't drift;
the curated part is small enough to maintain.

## Comparison

| Tool | Axis | Personal-tool fit | fzf | Drops cmd on prompt | Content drifts? | Already have it |
| --- | --- | --- | --- | --- | --- | --- |
| **navi** | Execute | High (parameterized) | Built-in | Yes (Ctrl-G) | Yes (authored) | No |
| **cheat** | View | High (page/command) | DIY | No | Yes (authored) | **Yes, underused** |
| **um** | View | Highest (your man pages) | DIY | No | Yes (authored) | No |
| **DIY fzf+bat** | View→insert | High | Native | Yes | Yes (authored) | **Yes (`workflows`)** |
| **tldr custom** | View | Medium (must know name) | No | No | Yes (authored) | **Yes** |
| **cheat.sh** | View | Low (external) | Wrapper | No | N/A (external) | Maybe |
| **help2man / Cobra gen** | Derive | High (option ref) | N/A | No | **No — derived** | No |

## The honest question this raises

You already have `workflows` (a DIY fzf+bat markdown browser), `cheat` (installed, underused),
`tldr`, `toolbox`, and `menu`. Adopting navi or um would be a **sixth** door — the exact
fragmentation that makes everything "feel forgotten."

So the discovery-side decision is probably *not* "which new tool," but:

1. **Unify the front doors** — one keystroke / one command (`ref`? extend `workflows`?) that
   fuzzy-searches across workflows + your tool catalog + cheat + tldr and drops the real command
   on the prompt. Borrow the context-aware ZLE insert from `zsh-cheatsheet` and the
   inline-comment descriptions from fzf #2982.
2. **Kill the drift** — generate the *option reference* for your `~/tools` from Cobra
   `GenMarkdownTree`, so the mkdocs "tools" pages and any terminal view derive from `--help`.
   Keep hand-written `workflows` cards only for the *combinations and idioms* that `--help`
   can't express (the fzf tricks you always forget).
3. **Fix `menu`** — point it at `~/dev/tools.yml` so the catalog view works again.

The single biggest ergonomic win found: **selecting a cheat should drop the real command onto
your prompt** (navi, fzf-cheatsheets, zsh-cheatsheet all do this). Your `workflows search`
currently shows a card to *read*; it doesn't hand you the command to *run*. That one change
turns lookup into a habit-builder.

## Sources

- navi — <https://github.com/denisidoro/navi> · syntax <https://github.com/denisidoro/navi/blob/master/docs/cheatsheet/syntax/README.md>
- cheat — <https://github.com/cheat/cheat>
- um — <https://github.com/sinclairtarget/um> · example pages <https://github.com/ChillerData/um-pages>
- fzf-cheatsheets — <https://github.com/james-w/fzf-cheatsheets> · zsh-cheatsheet <https://github.com/Xav-Deb/zsh-cheatsheet> · alias picker <https://github.com/junegunn/fzf/discussions/2982>
- tealdeer custom pages — <https://tealdeer-rs.github.io/tealdeer/usage_custom_pages.html>
- cheat.sh — <https://github.com/chubin/cheat.sh>
- help2man — <https://www.gnu.org/software/help2man/>
- kb (note-manager-shaped, likely against the "no new app" preference) — <https://github.com/gnebbia/kb>
