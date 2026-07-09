---
icon: material/brain
---

# Active Review & Retention

**Job 3 of 3.** The question: *"How do I actually memorize the efficient commands so they become
muscle memory — instead of forgetting them again?"* This is the gap you named directly: your
random-workflow-on-startup is nice, but there is "no active way to review and drill."

The organizing principle, cited across every source: **look up the long tail, drill the hot
set.** Point-of-need lookup (Job 1) is right for the command you use monthly. *Active recall on a
schedule* is right for the ~20 things you keep fumbling. Your current setup does neither well —
it is recognition (you *see* a card) without scheduling (it's random) and without recall (it
never checks whether you learned it).

Research date: 2026-07-07.

!!! note "Superseded (2026-07-08)"
    Acted on: the `workflows motd` random startup card was **removed**, not upgraded. Its slot is
    now the `menu review` cadence register plus a first-shell-of-each-half-day nudge — the
    scheduled-return mechanism this document argues for. Read the "keep the motd, improve it"
    advice below as the analysis that led there, not current guidance. See `docs/apps/menu.md`.

## Why the random startup tip is only half the answer

Your `workflows motd` shows a random card on shell startup. That is the **fortune / motd
pattern**, and it is genuinely good for *discovery and exposure* — it keeps your own material in
ambient awareness. But the retention literature is blunt about its limits:

- It is **random**, not scheduled by your forgetting curve — you re-see things you already know
  and may not re-see the thing you're about to forget.
- It is **recognition, not recall** — reading "here's how `ci(` works" is not the same as
  *producing* `ci(` when you need it. Recognition fades; recall builds muscle memory.
- It has **no feedback loop** — it never learns which cards you've mastered and which you keep
  missing.
- **Banner blindness** sets in fast — people stop reading motd within days.

None of this means kill it. It means it's the *discovery* layer, and you're missing the
*recall* layer beneath it. The academic backing is the spaced-repetition scheduling literature
([arXiv 1602.07032](https://arxiv.org/pdf/1602.07032)): retention is maximized by scheduling
review against memory strength — precisely what random rotation lacks.

### Cheap upgrades to the motd itself (keep it, improve it)

- **Weekly "tool of the week," not per-shell random.** Index into your tool/workflow list by ISO
  week number so you get *sustained* exposure to one tool for seven days. Sustained exposure
  builds mastery; novelty every shell builds banner blindness. (Terminal Trove's "Tool of the
  Week" is the public analog.)
- **First-shell-of-the-day gating.** You run tmux with many panes; showing the tip on *every*
  pane is what breeds blindness. Touch a datestamp file and only show on the day's first shell
  ([hexmen.com/blog/motd](https://hexmen.com/blog/motd/)).
- **Make it actionable** — show the runnable command so you can do it immediately, not just read
  it.

## The nudge layer (turn existing aliases into habits)

You have 35 aliases but type the long form anyway (`git push` 393×). Nudge tools close that gap
at the moment you commit the inefficiency — the highest-leverage, lowest-effort retention tool
because it needs no new content.

### zsh-you-should-use ⭐ (already-in-shell, graduated enforcement)

[github.com/MichaelAquilina/zsh-you-should-use](https://github.com/MichaelAquilina/zsh-you-should-use).
Hooks `preexec`; when you type a command that has an alias, it reminds you. The design is built
for "nudge without nagging":

- `YSU_MESSAGE_POSITION="after"` — show *after* the command runs, non-disruptive.
- `YSU_HARDCORE_ALIASES=("gp" "gst")` — *selective* hard mode: these specific aliases **block
  execution** until you use them, everything else just nudges. This is the muscle-memory forcing
  lever, applied only to the handful you're actively drilling.
- `YSU_IGNORED_ALIASES` — silence the ones you don't care about (kills notification fatigue).
- `check_alias_usage [N]` — **audits history** to rank which aliases you actually use vs. which
  are dead. A pull-on-demand review report, not a nag.

The reported pattern: use gentle "after" nudges broadly, graduate a specific alias to
`HARDCORE` when you want to *force* it, disable once it sticks ("within a week the behavior is
reinforced and the reminders stop" — it self-extinguishes). Alternatives:
[alias-tips](https://github.com/djui/alias-tips) (oh-my-zsh, less configurable),
[zsh-fast-alias-tips](https://github.com/decayofmind/zsh-fast-alias-tips) (Go, faster).

### Global alias expansion (learn-while-you-type)

Bind Space to expand the alias inline (`zle _expand_alias`), so the *real command* appears in
front of you every time you use a shortcut. Counters the "aliases cause command-knowledge
atrophy" failure mode — you never forget what `gp` stands for because you watch it become
`git push`. From [mastering-zsh](https://github.com/rothgar/mastering-zsh/blob/master/docs/helpers/aliases.md).

## The recall layer (spaced repetition — the missing piece)

This is what your setup entirely lacks: a system that *prompts you to produce* the command and
*schedules by forgetting*. Terminal-native, plaintext, no-GUI options that fit "no more apps":

- **[repeater](https://github.com/shaankhosla/repeater)** ⭐ — cards live in plain `.md` files
  (`Q:`/`A:`/cloze), progress in SQLite, uses **FSRS** (state-of-the-art scheduling). `repeater
  drill <dir>` runs a TUI session. Optional LLM card-gen. The cleanest "true spaced repetition in
  the terminal" — and crucially, **your notes/workflows can *be* the deck**, so it consolidates
  rather than adds a silo.
- **[fla.sh](https://github.com/tallguyjenks/fla.sh)** — pure shell, plaintext, Anki-style. Even
  lighter; fewer features.
- **org-drill / org-fc** — if any of this lived in org/emacs (it doesn't for you).

The seminal writeup is [Alf Mikula, "Using SRS to Master Vim"](http://alfmikula.blogspot.com/2010/11/using-spaced-repetition-software-to.html),
whose problem statement is verbatim yours: *"I knew many Vim commands existed but couldn't retain
them."* His method: a deck ordered simple→advanced, **≤5 new cards/day, a few minutes daily**,
and the critical note — *"even commands that became muscle memory required initial spaced
repetition before automaticity developed."* [Atomic Object](https://spin.atomicobject.com/vim-with-spaced-repetition/)
adds the essential refinement: **execute the motion in a real buffer as you review the card** —
pair recall with doing, don't just flip cards.

## The drill layer (checked, gamified practice)

Beyond flashcards: tools that *prompt an outcome, check your keystrokes, and grade efficiency.*

- **[vimhjkl](https://github.com/S-Sigdel/vimhjkl)** ⭐ — the single closest match to "an active
  way to drill." Runs in real vim: shows a target end-state, captures your keystrokes (`vim -W`),
  scores them against verified-optimal solutions. **Leitner box 1–5 scheduling**, 25 reps →
  mastery, harder skills unlock as easier ones are mastered, passing requires ≤ 2× par
  keystrokes (efficiency-graded). Modes: Learn / Blind / Practice-your-weakest / Grind. This is
  exactly "how would you do X? — checked and scheduled."
- **[vim-be-good](https://github.com/ThePrimeagen/vim-be-good)** — nvim mini-games (relative
  jumps, `ci{`, whack-a-mole). Drills basic motions through play.
- **KeyCombiner / ShortcutFoo** (web) — interactive shortcut drills with per-combo confidence
  scores and SR. Not terminal-native, but the *method* (60-second sessions, per-shortcut
  confidence, drill the low-confidence ones) is the model. [tkainrad's writeup](https://tkainrad.dev/posts/why-i-built-a-new-app-for-practicing-keyboard-shortcuts/)
  has the sharpest cadence advice: **10 new shortcuts/week, 60-second sessions**, and the
  insight that stats-driven drilling catches *embodied* errors (wrong finger on Ctrl+C) that
  recognition never surfaces.

## Point-of-need vs. scheduled review — the tradeoff, resolved

| | Point-of-need (which-key, precognition, navi, tldr, your `workflows`) | Scheduled review (repeater, vimhjkl, YSU hardcore) |
| --- | --- | --- |
| Memory mode | Recognition | Recall |
| Best for | Rare / low-value commands, discovery | Frequent / high-value commands you keep fumbling |
| Cost | Near zero | Deliberate time + friction |
| Failure mode | Becomes a permanent crutch — you look it up forever, never internalize | Effort; needs card authoring |

The reconciling pattern everyone converges on: **look up the long tail, drill the hot set.** Use
`workflows` / precognition / tldr as ambient scaffolding for the rare stuff; put the ~20
commands you keep missing into an active-recall deck or a vimhjkl-style checked drill. The two
layers are complements, and your data (Job 2's failure/frequency queries, hardtime's report)
tells you *which* commands graduate from long-tail to hot-set.

## Recommendation shape

- **Keep** `workflows motd` as the discovery layer — but upgrade it to **weekly rotation +
  first-shell-of-day gating**.
- **Add the nudge layer** — `zsh-you-should-use` in `"after"` position, with a small
  `YSU_HARDCORE_ALIASES` set for the aliases you're actively forcing (start with the git ones
  your history shows you type long). Consider global-alias Space expansion.
- **Add the recall layer** — `repeater` with a deck **auto-generated from your workflow cards /
  tool `--help`**, so authoring is nearly free and it consolidates rather than adds a silo.
  Feed the deck from Job 2's "what I keep fumbling" data.
- **Optionally add the drill layer** — `vimhjkl` for vim motions specifically (see the neovim
  doc).

The through-line: your motd is exposure; the missing mechanism is *scheduled active recall of
the hot set*, and the hot set should be *chosen by the usage data*, not guessed.

## Sources

- zsh-you-should-use — <https://github.com/MichaelAquilina/zsh-you-should-use> · alias-tips <https://github.com/djui/alias-tips>
- repeater — <https://github.com/shaankhosla/repeater> · fla.sh <https://github.com/tallguyjenks/fla.sh>
- Mikula "SRS to Master Vim" — <http://alfmikula.blogspot.com/2010/11/using-spaced-repetition-software-to.html> · Atomic Object <https://spin.atomicobject.com/vim-with-spaced-repetition/>
- vimhjkl — <https://github.com/S-Sigdel/vimhjkl> · vim-be-good <https://github.com/ThePrimeagen/vim-be-good>
- cadence — tkainrad <https://tkainrad.dev/posts/why-i-built-a-new-app-for-practicing-keyboard-shortcuts/> · Peter Jang 4-week plan <https://peterxjang.com/blog/how-to-learn-vim-a-four-week-plan.html>
- motd variants — fortune <https://wiki.archlinux.org/title/Fortune> · first-shell gating <https://hexmen.com/blog/motd/> · tool of the week <https://terminaltrove.com/tool-of-the-week/>
- SR scheduling theory — <https://arxiv.org/pdf/1602.07032> · lookup-vs-recall essay <https://b-nova.com/en/home/content/memorize-less-know-more-with-state-of-the-art-cheatsheets/>
