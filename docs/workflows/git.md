# Git Workflows

Git operations happen dozens of times per day during development. The dotfiles include several tools that make git operations faster, more visual, and less error-prone. LazyGit provides a complete terminal UI for git operations. Forgit adds interactive fzf-powered git commands. Delta enhances diff viewing with syntax highlighting. The GitHub CLI enables repository operations without leaving the terminal.

## Interactive Staging with LazyGit

LazyGit transforms git from a command-line tool into a visual interface. Launch it from any repository to see status, stage changes, create commits, and manage branches through an intuitive UI.

```bash
lazygit
```

The interface shows files on the left, diff on the right. Navigate files with j/k, stage individual files with space, stage hunks with enter on a selected file. This granular control makes it easy to stage exactly what belongs in each commit.

Create commits without typing git commands. Stage the right changes, press c to commit, type the message, save. The commit happens immediately. No remembering command syntax, no accidentally committing unstaged changes.

Branch management becomes visual. See all branches in one view, switch with enter, create new branches with n, delete merged branches with d. The operations feel natural because the UI provides context for each action.

## Interactive Git Operations with Forgit

Forgit adds fzf-powered interactive selection to common git operations. Each forgit command presents choices with previews, making git operations safer and faster.

### Browsing History

Explore git history interactively instead of reading raw git log output.

```bash
git forgit log              # Interactive commit history browser
# Alias: glo
```

The log browser shows commits with full context. Navigate with arrow keys, preview each commit's changes, search by commit message or content. Find specific changes without remembering exact commit hashes or crafting complex git log filters.

View the reflog interactively to understand history changes or recover lost commits.

```bash
git forgit reflog
# Alias: grl
```

### Interactive Staging and Unstaging

Select files to stage or unstage with visual previews of changes.

```bash
git forgit add              # Interactive file staging
# Alias: ga
```

The file selector shows all modified files with previews of what changed. Select files to stage using tab, press enter to stage them. This prevents staging unintended files and makes it easy to create focused commits.

Unstage files with the same interactive interface:

```bash
git forgit reset_head       # Interactive unstaging
# Alias: grh
```

### Viewing Diffs

Select files to view diffs interactively instead of manually specifying paths.

```bash
git forgit diff             # Interactive diff file selector
# Alias: gd
```

This shows all modified files in a picker with diff previews. Select a file to see its full diff with syntax highlighting via delta. Perfect for reviewing changes before committing or understanding what changed since last commit.

### Branch Management

Switch branches, checkout commits, or manage tags through interactive selectors.

```bash
git forgit checkout_branch  # Interactive branch switching
# Alias: gcb

git forgit checkout_commit  # Interactive commit checkout
# Alias: gco

git forgit checkout_tag     # Interactive tag checkout
# Alias: gct
```

Branch selection with fuzzy search beats typing branch names. Search for part of the branch name, see matches, select with enter. The preview shows branch information like last commit and author.

Delete branches safely with visual confirmation:

```bash
git forgit branch_delete    # Interactive branch deletion
# Alias: gbd
```

### Stash Management

Browse stashes interactively and selectively stash files.

```bash
git forgit stash_show       # Browse stash entries
# Alias: gss

git forgit stash_push       # Selectively stash files
# Alias: gsp
```

Stash show presents each stash entry with a preview of what's stashed. No more running git stash list and git stash show stash@{N} repeatedly. See everything in one interface.

Selective stashing lets you choose exactly which files to stash instead of stashing everything. Keep some changes in working directory while stashing others.

### Advanced Operations

Cherry-pick, rebase, and fixup commits through interactive selection.

```bash
git forgit cherry_pick      # Interactive cherry-pick
# Alias: gcp

git forgit rebase           # Interactive rebase selector
# Alias: grb

git forgit fixup            # Interactive fixup commits
# Alias: gfu
```

Fixup commits become trivial. Select the commit to fix, create the fixup, autosquash it during next rebase. This workflow encourages small, focused commits with corrections applied cleanly.

## Viewing Diffs with Delta

Delta provides syntax-highlighted git diffs with line numbers and side-by-side viewing. It's configured as the default pager for git diff and git log, so it activates automatically.

```bash
git diff                    # Shows diff with delta
git log -p                  # Shows commit patches with delta
git show HEAD               # Shows last commit with delta
```

Delta highlights syntax in diffs, making it easier to understand code changes. Line numbers appear in the gutter. Changed sections get highlighted distinctly. Side-by-side mode shows old and new versions together for complex changes.

The configuration lives in `.gitconfig` where delta is set as the pager with specific options for line numbers, syntax highlighting, and themes.

## GitHub Operations with gh CLI

The GitHub CLI brings GitHub operations to the terminal. Create pull requests, review issues, trigger workflows, and manage repositories without opening a browser.

### Pull Request Workflows

Create pull requests directly from the terminal with full context from the current branch.

```bash
gh pr create                # Create PR interactively
gh pr list                  # List pull requests
gh pr status                # Show PR status
```

The create command prompts for title and body, shows diff for review, submits the PR. The interactive prompts guide through the process while showing relevant context.

Review pull requests without leaving the terminal:

```bash
gh pr checkout 123          # Checkout PR #123 locally
gh pr view 123              # View PR details
gh pr diff 123              # View PR diff
```

Checkout PRs locally to test changes or review code with full development environment. View PR metadata inline. Check diff to understand changes.

### Issue Management

Browse and create issues from the terminal.

```bash
gh issue list               # List issues
gh issue create             # Create new issue
gh issue view 42            # View issue details
```

This workflow enables quick issue triage without context switching to browser. List issues, read details, create follow-ups, all from the same environment used for development.

### Repository Operations

View repository details and trigger workflows.

```bash
gh repo view                # View repository details
gh workflow run             # Trigger GitHub Actions workflow
gh run list                 # List workflow runs
```

Trigger CI/CD workflows manually when needed. Check workflow status. View repository information. These operations integrate git work with repository management.

## Common Git Patterns

### Creating Focused Commits

Use LazyGit or forgit to stage specific files and hunks for each commit. Stage related changes together, leave unrelated changes unstaged. Create multiple small commits instead of one large commit.

Small commits make git history readable. Each commit represents one logical change. Code review becomes easier. Bisecting to find bugs works better. Reverting problematic changes doesn't remove unrelated improvements.

```bash
lazygit                     # Stage hunks visually
# Or
git forgit add              # Select files interactively
```

### Reviewing Changes Before Committing

Always review what will be committed before creating the commit. Check staged changes with delta to catch unintended modifications.

```bash
git diff --staged           # Review staged changes with delta
```

LazyGit shows the diff continuously while staging changes, providing immediate feedback. Forgit shows previews during file selection. These visual confirmations prevent committing debug statements, temporary changes, or broken code.

### Branch Workflow

Create feature branches for all changes. Keep main branch clean. Use descriptive branch names that explain the purpose.

```bash
git forgit checkout_branch  # Switch branches interactively
# Or create new branch
git checkout -b feature/descriptive-name
```

Work on the feature branch. Commit often. Push regularly. Create PR when ready. This workflow isolates changes, enables parallel work on multiple features, and makes code review straightforward.

### Cleaning Up History

Use interactive rebase to clean up commits before creating pull requests. Squash small fixups, reword unclear messages, reorder commits logically.

```bash
git forgit rebase           # Select base commit interactively
```

Fixup commits during development get squashed during final rebase. This keeps commit history clean without slowing down development. Create rough commits while working, polish them before sharing.

### Recovering from Mistakes

Browse reflog interactively to recover from git mistakes. Accidentally reset too far? Check reflog. Lost commits during rebase? Check reflog.

```bash
git forgit reflog           # Find the commit before the mistake
```

Reflog tracks all HEAD movements, making it possible to recover from almost any git operation. The interactive browser makes finding the right commit easier than parsing raw reflog output.

## Composition Patterns

Combine git tools with other command-line tools for powerful workflows.

Search commit messages and diff content:

```bash
git log --all --oneline | fzf
git log -p | grep -i "search term"
```

Find commits that modified specific files:

```bash
git log --oneline -- path/to/file | fzf
```

Stage files matching a pattern:

```bash
git status --short | grep "pattern" | awk '{print $2}' | xargs git add
```

These compositions leverage standard Unix tools with git to create custom workflows beyond what individual tools provide.

## Troubleshooting Common Issues

### LazyGit Not Showing Changes

If LazyGit opens but shows no files, verify working in a git repository. Check git status shows changes. LazyGit requires an initialized repository.

```bash
git status                  # Verify repo status
```

### Forgit Commands Not Found

Forgit installs as git aliases. Use `git forgit <command>` not `forgit <command>`. The aliases provide shorter versions like `glo` for `git forgit log`.

```bash
git forgit log              # Full command
glo                         # Alias
```

### Delta Not Showing Colors

Delta requires proper terminal color support. Check TERM variable is set correctly.

```bash
echo $TERM                  # Should show something like xterm-256color
```

Verify git pager is configured for delta:

```bash
git config --get core.pager # Should show delta
```

## See Also

- [GitHub CLI Documentation](https://cli.github.com/manual/)
- [LazyGit Documentation](https://github.com/jesseduffield/lazygit)
- [Forgit Documentation](https://github.com/wfxr/forgit)
- [Delta Documentation](https://github.com/dandavison/delta)
