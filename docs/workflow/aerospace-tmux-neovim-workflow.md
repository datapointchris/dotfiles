# Comprehensive Workflow Analysis: AeroSpace + Tmux + Neovim

> Last Updated: 2025-11-01

This document provides a comprehensive analysis of how to efficiently use AeroSpace (window manager), Tmux (terminal multiplexer), and Neovim (editor) together on a single large monitor. It covers the hierarchy, decision-making process, keybindings, and best practices based on research and real-world usage.

## Table of Contents

1. [The Hierarchy & Nesting Model](#1-the-hierarchy--nesting-model)
2. [When to Use Each Layer](#2-when-to-use-each-layer)
3. [The Decision Tree](#3-the-decision-tree-where-should-i-split-next)
4. [Complete Keybinding Reference](#4-complete-keybinding-reference)
5. [Workflow Recommendations for Single Large Monitor](#5-workflow-recommendations-for-single-large-monitor)
6. [Redundancy Analysis](#6-redundancy-analysis-what-not-to-do)
7. [Power User Tips](#7-power-user-tips)
8. [Keybinding Design Analysis](#8-your-current-keybindings-are-well-designed)

---

## 1. The Hierarchy & Nesting Model

```
┌──────────────────────────────────────────────────────────────────────────┐
│ LEVEL 1: AeroSpace (macOS Window Manager)                                │
│ PURPOSE: Project/context isolation, monitor management                   │
│ SCOPE: Entire monitor/desktop                                             │
│ PERSISTENCE: Until logout/reboot                                          │
│                                                                            │
│  Workspace A (Project)    Workspace D (Dotfiles)    Workspace E (Email)  │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ LEVEL 2: Tmux (Terminal Multiplexer)                               │  │
│  │ PURPOSE: Related terminal tasks, session persistence                 │  │
│  │ SCOPE: Per terminal window                                           │  │
│  │ PERSISTENCE: Survives terminal close, SSH disconnect                 │  │
│  │                                                                       │  │
│  │  Session: dotfiles-work                                              │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │  │
│  │  │Window 1: dev │  │Window 2: git │  │Window 3: test│              │  │
│  │  │              │  │              │  │              │              │  │
│  │  │  ┌────┬────┐ │  │              │  │  ┌─────────┐ │              │  │
│  │  │  │Pane│Pane│ │  │    Pane 1    │  │  │  Pane 1 │ │              │  │
│  │  │  │ 1  │ 2  │ │  │              │  │  ├─────────┤ │              │  │
│  │  │  └────┴────┘ │  │              │  │  │  Pane 2 │ │              │  │
│  │  │              │  │              │  │  └─────────┘ │              │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │  │
│  │                                                                       │  │
│  │  ┌──────────────────────────────────────────────────────────────┐   │  │
│  │  │ LEVEL 3: Neovim (Editor)                                      │   │  │
│  │  │ PURPOSE: File editing, code navigation                        │   │  │
│  │  │ SCOPE: Per tmux pane                                          │   │  │
│  │  │ PERSISTENCE: Per session/working directory                    │   │  │
│  │  │                                                                │   │  │
│  │  │  Tab 1: main code    Tab 2: tests                            │   │  │
│  │  │  ┌─────────────────┐  ┌─────────────────┐                    │   │  │
│  │  │  │ Split 1  Split 2│  │    Split 1      │                    │   │  │
│  │  │  │ (file.ts)(def)  │  │   (test.ts)     │                    │   │  │
│  │  │  └─────────────────┘  └─────────────────┘                    │   │  │
│  │  │                                                                │   │  │
│  │  │  Buffers: [file.ts, types.ts, util.ts, test.ts, ...]        │   │  │
│  │  │  (Many files loaded, switch via <leader>fb or :b)             │   │  │
│  │  └──────────────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. When to Use Each Layer

### AeroSpace Workspaces

**Use for:** Complete context separation (different projects, different activities)

**Create new workspace when:**

- Starting a completely different project
- Separating work contexts (dev vs email vs music vs social)
- Need a fresh slate with different application layout
- Working on unrelated codebases

**Current workspaces:**

- A, B, C: Projects (active development)
- D: Dotfiles (system configuration work)
- E: Email (communication)
- M: Music (media)
- S: Social (messaging/chat)
- Q: Quick/Temporary (scratch space)
- X, Y, Z: Miscellaneous

**Switching cost:** Medium (Ctrl+Alt+Shift+; then letter)

---

### Tmux Sessions

**Use for:** Long-running project contexts that need to survive terminal restarts

**Create new session when:**

- Starting work on a distinct project (e.g., "dotfiles-work", "icb-backend", "icb-frontend")
- Need to preserve exact window/pane layout for later
- Working on something you'll SSH into remotely
- Want to detach and reattach

**Use windows within session when:**

- Tasks are related but need separation (dev, git, tests, logs)
- Not enough screen space for more panes
- Prioritizing work (window 1 = critical, window 2 = background tasks)

**Switching cost:**

- Session: Medium-High (prefix + s, then select)
- Window: Very Low (prefix + 0-9, or next/prev)

**Best practice from research:**
> "Sessions = projects, Windows = related tasks within that project"

---

### Tmux Panes

**Use for:** Viewing multiple terminals simultaneously in same context

**Create new pane when:**

- Need to see output side-by-side (editor + running process)
- Comparing logs or files
- Running command while monitoring output
- You have screen real estate

**Avoid panes when:**

- You're just switching between tasks (use windows instead)
- Screen gets too crowded (use windows)
- Different priority levels (critical vs background)

---

### Neovim Tabs

**Use for:** Different "layouts" or working contexts within the same project

**Create new tab when:**

- Working on different features within same project (tab for main code, tab for tests)
- Need a different window layout for different tasks
- Want to preserve a specific split arrangement

**Research consensus:**
> "Tabs are for different layouts/workspaces within a project, NOT for open files. Use buffers for files."

**Avoid tabs for:**

- Just opening files (use buffers instead via `<leader>fb`)
- More than 3-4 tabs (gets hard to track)

---

### Neovim Splits/Windows

**Use for:** Viewing multiple files simultaneously for comparison/reference

**Create new split when:**

- Need to reference code while writing (definition + implementation)
- Comparing files side-by-side
- Following code flow across files
- Writing tests while looking at implementation

**Use buffers instead when:**

- Just jumping between files (use `<leader>fb` Telescope picker)
- Reading/editing one file at a time
- Quick navigation (buffers are faster)

**Research consensus:**
> "Prefer buffers for navigation, use splits only when you need to see multiple files at once"

---

## 3. The Decision Tree: "Where Should I Split Next?"

```
Need to start new work?
│
├─ Is it a completely different project/context?
│  └─ YES → Create new AeroSpace workspace (Ctrl+Alt+Shift+; then letter)
│           Example: Switching from coding to email
│
├─ Is it a different project but same general context?
│  └─ YES → Create new Tmux session (prefix + :new -s name)
│           Example: Starting work on different codebase
│
├─ Is it a related task but different workflow?
│  └─ YES → Create new Tmux window (prefix + c)
│           Example: Running tests in separate window from dev
│
├─ Do you need to SEE two terminals at once?
│  └─ YES → Create new Tmux pane (prefix + | or -)
│           Example: Editing + watching logs
│
├─ Do you need a different code layout/context?
│  └─ YES → Create new Neovim tab (<leader>te)
│           Example: Separate tab for test files
│
├─ Do you need to SEE two files at once?
│  └─ YES → Create Neovim split (:vsp or :sp)
│           Example: Header file + implementation
│
└─ Just need to edit a different file?
   └─ Use Neovim buffers (<leader>fb to find, :b to switch)
      This is the FASTEST and most efficient!
```

---

## 4. Complete Keybinding Reference

### AeroSpace - Window Manager Level

| Action | Keybinding | Notes |
|--------|-----------|-------|
| **Navigation** |
| Focus window | `alt + h/j/k/l` | Directional |
| Move window | `alt + shift + h/j/k/l` | Directional |
| Switch to prev workspace | `alt + tab` | Quick toggle |
| **Creation** |
| New terminal | `alt + enter` | Opens Ghostty |
| **Workspace Switching** |
| Enter cmd mode | `ctrl + alt + shift + ;` | Required first |
| Go to workspace | `[letter]` (a/b/c/d/e/m/q/s/x/y/z) | After cmd mode |
| Move window to workspace | `shift + [letter]` | After cmd mode |
| **Layout** |
| Toggle floating | `alt + f` | Float/tile |
| Fullscreen | `alt + shift + f` | Maximize |
| Toggle layout | `'` or `\` | Tiles/accordion (in cmd mode) |
| **Resize** |
| Resize mode | `ctrl + alt + shift + ;` | Enter cmd mode first |
| Resize smart | `ctrl + alt + j/k` | Shrink/grow (in cmd mode) |
| Resize opposite | `ctrl + alt + h/l` | Adjust perpendicular (in cmd mode) |

### Tmux - Terminal Multiplexer Level

| Action | Keybinding | Notes |
|--------|-----------|-------|
| **Prefix** | `Ctrl + Space` | Required for most commands |
| **Sessions** |
| List sessions | `prefix + s` | sessionx plugin |
| New session | `prefix + :new -s name` | Named session |
| Detach | `prefix + d` | Keeps running |
| **Windows** |
| New window | `prefix + c` | Create |
| Kill window | `prefix + k` | Close |
| Next window | `prefix + n` or `prefix + l` | Cycle forward |
| Previous window | `prefix + p` or `prefix + h` | Cycle backward |
| Select window | `prefix + 0-9` | Direct access |
| Swap window left | `prefix + <` | Repeatable |
| Swap window right | `prefix + >` | Repeatable |
| **Panes** |
| Split vertical | `prefix + \|` | Side-by-side |
| Split horizontal | `prefix + -` | Stacked |
| Navigate panes | `Ctrl + h/j/k/l` | Smart (vim-aware) |
| Resize panes | `Ctrl + Alt + h/j/k/l` | 5 units |
| **Other** |
| Reload config | `prefix + R` | Refresh |
| Command mode | `prefix + :` | Manual commands |
| Copy mode | `prefix + [` | Scroll/copy |
| Paste buffer | `prefix + P` | Paste |

### Neovim - Editor Level

| Action | Keybinding | Notes |
|--------|-----------|-------|
| **Buffers** (Primary file navigation) |
| Find buffer | `<leader>fb` | Telescope picker (FAST!) |
| Switch buffer | `:b [name]` | Type partial name |
| Next buffer | `:bnext` | Cycle forward |
| Prev buffer | `:bprev` | Cycle backward |
| **Tabs** (Layouts/contexts) |
| New tab | `<leader>te` | Tab edit |
| Close tab | `<leader>tw` | Tab close |
| Next tab | `<tab>` | Cycle forward |
| Previous tab | `<shift-tab>` | Cycle backward |
| **Splits/Windows** (Viewing multiple files) |
| Vertical split | `:vsp [file]` | Side-by-side |
| Horizontal split | `:sp [file]` | Stacked |
| Navigate splits | `Ctrl + h/j/k/l` | Smart (tmux-aware) |
| Resize splits | `<leader>r + h/j/k/l` | 10 units |
| Maximize split | `<leader>rm` | Toggle max |
| Close split | `:q` or `<leader>qq` | Close current |

---

## 5. Workflow Recommendations for Single Large Monitor

Based on research and real-world usage, here's the optimal workflow for one large monitor:

### Recommended Structure

```
AeroSpace Workspace (full screen)
├─ 1-2 Tmux terminal windows (tiled side-by-side or stacked)
    ├─ Session: project-name
    ├─ Window 1: Development (2-3 panes)
    │   ├─ Pane 1: Neovim (primary editing)
    │   └─ Pane 2: Command execution / watching tests
    └─ Window 2: Support (1-2 panes)
        ├─ Pane 1: Git operations
        └─ Pane 2: Logs / monitoring
```

### The Optimal Split Strategy

1. **Use AeroSpace workspaces to separate projects** - This is your top-level organization
   - One workspace per major project or activity type
   - Quick switching with `alt+tab` for recent workspace

2. **Use one Tmux session per project** - Long-running contexts
   - Named sessions: "dotfiles-dev", "icb-backend", "icb-frontend"
   - Preserve your exact setup across days
   - Can detach/reattach

3. **Use Tmux windows sparingly** - 2-4 windows max per session
   - Window 1: Main development (editor + runner)
   - Window 2: Git/version control
   - Window 3: Testing/debugging
   - Window 4: Logs/monitoring
   - More than 4 = cognitive overload

4. **Use Tmux panes for simultaneous viewing** - Keep it simple
   - 2-3 panes max per window
   - Vertical split is most common (editor | terminal)
   - Horizontal split for logs beneath editor

5. **Use Neovim buffers as primary file navigation** - This is key!
   - Don't create tabs/splits for every file
   - Use `<leader>fb` to fuzzy-find files
   - Buffers stay loaded, switching is instant

6. **Use Neovim splits only when necessary** - Visual comparison
   - Implementation + tests side-by-side
   - Header + source file
   - Definition + usage
   - Close splits when done comparing

7. **Use Neovim tabs rarely** - Different workflows within project
   - Tab 1: Main development
   - Tab 2: Test file editing
   - Tab 3: Documentation/README
   - More than 3 tabs = probably better as Tmux windows

### Example Workflows

#### Workflow: Dotfiles Development

```
AeroSpace Workspace D (Dotfiles)
│
└─ Ghostty Terminal (fullscreen or large)
   └─ Tmux Session: "dotfiles-dev"
      ├─ Window 1: "edit"
      │  ├─ Pane 1: Neovim (buffers: tmux.conf, keymaps.lua, aerospace.toml)
      │  │          Switch files with <leader>fb
      │  └─ Pane 2: Testing changes (source configs, test keybindings)
      │
      ├─ Window 2: "git"
      │  └─ Pane 1: Git operations (status, add, commit, push)
      │
      └─ Window 3: "docs"
         └─ Pane 1: Running mdbook serve or viewing docs
```

**Why this works:**

- All related dotfiles work in one workspace
- One session preserves your window layout
- Files switch fast via buffers (don't create 10 splits!)
- Git in separate window (switch with prefix + 1/2/3)
- Can see editor + test output simultaneously

#### Workflow: Web Development

```
AeroSpace Workspace A (Project)
│
├─ Ghostty Terminal 1 (left half)
│  └─ Tmux Session: "icb-frontend"
│     ├─ Window 1: "dev"
│     │  ├─ Pane 1: Neovim (React components, switching via buffers)
│     │  └─ Pane 2: npm run dev (watching build)
│     └─ Window 2: "git"
│        └─ Pane 1: Git operations
│
└─ Ghostty Terminal 2 (right half)
   └─ Tmux Session: "icb-backend"
      ├─ Window 1: "dev"
      │  ├─ Pane 1: Neovim (API routes, switching via buffers)
      │  └─ Pane 2: npm run dev (backend server)
      └─ Window 2: "db"
         └─ Pane 1: Database console
```

**Why this works:**

- Two separate terminal windows (AeroSpace manages them)
- Each has its own Tmux session (front/back isolation)
- Both dev servers visible simultaneously
- Within each Neovim, use buffers to jump between files
- Git and DB in background windows (quick switch)

---

## 6. Redundancy Analysis: What NOT to Do

### ❌ DON'T: Create multiple terminal windows for same project

**Instead:** Use Tmux windows within one terminal

- **Why:** Tmux windows are faster to switch, preserve layout, survive terminal crashes

### ❌ DON'T: Use Neovim tabs like browser tabs (one file per tab)

**Instead:** Use buffers and `<leader>fb` to switch files

- **Why:** Buffers are faster, less visual clutter, you can have 20+ files loaded

### ❌ DON'T: Split in both Tmux AND Neovim for same purpose

**Instead:** Choose one layer for splits

- **Split in Tmux when:** Need different terminal contexts (editor + runner)
- **Split in Neovim when:** Comparing/editing files side-by-side
- **Why:** Double nesting is confusing and hard to navigate

### ❌ DON'T: Create tons of AeroSpace workspaces

**Instead:** Use Tmux sessions within fewer workspaces

- **Why:** Workspace switching is slower, workspaces are for major context shifts

### ❌ DON'T: Create new Tmux session for every small task

**Instead:** Use windows within existing session

- **Why:** Sessions are heavy, windows are lightweight

### ❌ DON'T: Fight the nesting

**Instead:** Embrace the hierarchy

- **Why:** vim-tmux-navigator makes Ctrl+hjkl seamless across ALL levels

---

## 7. Power User Tips

### Tip 1: The "Two Terminal" Layout

For complex projects, use AeroSpace to tile two Ghostty terminals side-by-side:

- Left: Frontend development (Tmux session + Neovim)
- Right: Backend development (Tmux session + Neovim)

### Tip 2: The "Context Preservation" Pattern

Use Tmux session resurrection:

- End of day: Just close terminal (sessions preserved!)
- Next day: `tmux attach` - everything exactly as you left it
- Even windows, panes, and running processes intact

### Tip 3: The "Buffer Master" Approach

Aggressively use Neovim buffers:

- Open project root in Neovim
- `<leader>fb` becomes muscle memory
- Type 2-3 letters of filename
- Instant jump
- Way faster than creating splits/tabs

### Tip 4: The "Workspace Specialization" Pattern

Dedicate workspaces to activities:

- A/B/C: Active coding projects
- D: Dotfiles/system config
- E: Communication
- Q: Scratch/temporary work that you'll blow away
- This matches your cognitive zones

### Tip 5: Leverage vim-tmux-navigator

Your `Ctrl+hjkl` navigates EVERYTHING seamlessly:

- Navigate Neovim splits → hits edge → jumps to Tmux pane
- You can even resize Tmux panes with `Ctrl+Alt+hjkl` from within Neovim!
- One keybinding set rules them all

---

## 8. Your Current Keybindings Are Well-Designed

Your setup is already ergonomic:

- ✅ No conflicts between layers
- ✅ Consistent directional navigation (`hjkl` everywhere)
- ✅ Modifier keys separate concerns (alt=AeroSpace, Ctrl=Tmux/Neovim, leader=Neovim)
- ✅ vim-tmux-navigator provides seamless experience
- ✅ Split keys are mnemonic (`|` = vertical, `-` = horizontal)
- ✅ Directional window switching (`prefix + h/l` for previous/next window)

---

## Research Sources

This analysis was informed by community best practices from:

- [Using tmux Sessions, Windows, Panes and Vim Buffers Together - Nick Janetakis](https://nickjanetakis.com/blog/using-tmux-sessions-windows-panes-and-vim-buffers-together)
- [Why do Vim experts prefer buffers over tabs? - Stack Overflow](https://stackoverflow.com/questions/26708822/why-do-vim-experts-prefer-buffers-over-tabs)
- [Vim Tab Madness. Buffers vs Tabs - Josh Davis](https://joshldavis.com/2014/04/05/vim-tab-madness-buffers-vs-tabs/)
- [Does a terminal multiplexer have any benefit when used with a tiling window manager? - Unix & Linux Stack Exchange](https://unix.stackexchange.com/questions/38751/does-a-terminal-multiplexer-have-any-benefit-when-used-with-a-tiling-window-mana)
- Community discussions on tmux vs tiling window managers
- Real-world usage patterns and workflows

---

## Key Takeaway

**The Optimal Pattern:**

- **AeroSpace workspaces** = Projects/major contexts (11 workspaces)
- **Tmux sessions** = Long-running project environments (1 per codebase)
- **Tmux windows** = Related tasks (dev, git, test, logs) - keep to 2-4
- **Tmux panes** = Simultaneous viewing (editor + runner) - keep to 2-3
- **Neovim buffers** = PRIMARY file navigation (use `<leader>fb`!)
- **Neovim splits** = Only when comparing files side-by-side
- **Neovim tabs** = Different layouts within project - rare use

**Your biggest efficiency gain:** Embrace buffers over splits/tabs in Neovim!
