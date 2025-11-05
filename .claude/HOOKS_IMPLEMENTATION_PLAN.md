# Claude Code Hooks Implementation Plan

**Created**: 2025-11-04
**Status**: Ready for Implementation
**Estimated Timeline**: 4 weeks (phased approach)

## 📋 Overview

Comprehensive hooks system for dotfiles automation based on:

- Showcase repository patterns (datapointchris/claude-code-infrastructure-showcase)
- Official Claude Code documentation
- Community best practices (pre-commit, conventional commits)
- Custom dotfiles-specific requirements

**Core Goals**:

1. Automatic project context loading on session start
2. Build verification and error catching
3. Conventional commits automation via pre-commit (NO git push)
4. Skill-based auto-activation
5. Session state management

---

## 🎯 PHASE 1: Essential Foundation (Week 1)

**Goal**: Establish core hooks that provide immediate value

**Note**: All formatting is handled by pre-commit in Phase 2, not by hooks during development.

### 1.1 SessionStart Hook - Context Awareness

**Purpose**: Give Claude immediate awareness of repo state when session starts

**File**: `.claude/hooks/session-start`

```python
#!/usr/bin/env python3
"""
Provides Claude with immediate project context on session start.
Runs: git status, recent commits, directory structure snapshot
"""
import json
import os
import subprocess
import sys
from pathlib import Path

def get_git_status():
    """Get current git status"""
    result = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True,
        text=True
    )
    return result.stdout

def get_recent_commits():
    """Get last 5 commits in oneline format"""
    result = subprocess.run(
        ["git", "log", "--oneline", "-5"],
        capture_output=True,
        text=True
    )
    return result.stdout

def get_key_directories():
    """Snapshot of key directories"""
    project_root = Path(os.getenv("CLAUDE_PROJECT_DIR", "."))

    dirs_to_check = [
        "install/",
        "tools/",
        "docs/",
        "taskfiles/",
        "common/",
        "macos/",
        "wsl/",
        "arch/"
    ]

    structure = {}
    for dir_path in dirs_to_check:
        full_path = project_root / dir_path
        if full_path.exists():
            structure[dir_path] = len(list(full_path.rglob("*")))  # file count

    return structure

def main():
    hook_input = json.loads(sys.stdin.read())

    context = {
        "git_status": get_git_status(),
        "recent_commits": get_recent_commits(),
        "directory_counts": get_key_directories(),
        "cwd": hook_input["cwd"]
    }

    # Format as markdown for Claude
    output = f"""
## 📁 Project Context (Auto-loaded)

**Git Status:**
```

{context['git_status']}

```

**Recent Commits:**
```

{context['recent_commits']}

```

**Directory Structure:**
{json.dumps(context['directory_counts'], indent=2)}
"""

    # Return as system message
    print(json.dumps({
        "continue": True,
        "systemMessage": output.strip()
    }))

if __name__ == "__main__":
    main()
```

**Make executable**:

```bash
chmod +x .claude/hooks/session-start
```

### 1.2 Stop Hook - Build Verification

**Purpose**: Run builds and catch errors before moving on

**File**: `.claude/hooks/stop-build-check`

```bash
#!/usr/bin/env bash
# Run builds on modified tools to catch TypeScript/Python errors

set -euo pipefail

# Check if symlinks tool was modified
if git diff --name-only HEAD | grep -q "tools/symlinks"; then
    echo "🔨 Running pytest for tools/symlinks..."

    cd tools/symlinks
    if ! pytest -q 2>&1 | tee /tmp/build-errors.txt; then
        ERROR_COUNT=$(grep -c "FAILED\|ERROR" /tmp/build-errors.txt || echo "0")

        if [[ $ERROR_COUNT -lt 5 ]]; then
            echo "Found $ERROR_COUNT test failures - showing to Claude for fixing"
            cat /tmp/build-errors.txt
            exit 2  # Block and send to Claude
        else
            echo "⚠️  Found $ERROR_COUNT errors - consider launching auto-error-resolver"
            exit 0  # Non-blocking warning
        fi
    fi
    echo "✅ All tests passed"
fi

exit 0
```

**Make executable**:

```bash
chmod +x .claude/hooks/stop-build-check
```

### 1.3 Configuration

**File**: `.claude/settings.json`

```json
{
  "hooks": {
    "SessionStart": [
      {
        "command": "python .claude/hooks/session-start",
        "description": "Load project context (git status, structure)"
      }
    ],
    "Stop": [
      {
        "command": "bash .claude/hooks/stop-build-check",
        "description": "Run builds and catch errors"
      }
    ]
  }
}
```

### Week 1 Checklist

- [ ] Create `.claude/hooks/` directory
- [ ] Implement `session-start` hook
- [ ] Implement `stop-build-check` hook
- [ ] Make all hooks executable (`chmod +x`)
- [ ] Create `.claude/settings.json`
- [ ] Test each hook individually
- [ ] Verify hooks run on appropriate events

---

## 📋 PHASE 2: Git Automation (Week 2)

**Goal**: Automated conventional commits with pre-commit validation

### 2.1 Pre-commit Framework Setup

**Install pre-commit**:

```bash
# Via uv (follows your package management philosophy)
uv tool install pre-commit
```

**File**: `.pre-commit-config.yaml`

```yaml
repos:
  # Conventional commits enforcement
  - repo: https://github.com/compilerla/conventional-pre-commit
    rev: v3.6.0
    hooks:
      - id: conventional-pre-commit
        stages: [commit-msg]
        args: [--strict, --force-scope]

  # Code formatting
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: check-toml

  # Python formatting (for hooks and scripts)
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  # Markdown formatting
  - repo: https://github.com/executablebooks/mdformat
    rev: 0.7.21
    hooks:
      - id: mdformat
        additional_dependencies:
          - mdformat-gfm
          - mdformat-frontmatter

  # Shell script validation
  - repo: https://github.com/shellcheck-py/shellcheck-py
    rev: v0.10.0.1
    hooks:
      - id: shellcheck
```

**Install git hooks**:

```bash
cd ~/dotfiles
pre-commit install              # commit hooks
pre-commit install --hook-type commit-msg  # message validation
```

### 2.2 Stop Hook - Automated Commits

**Purpose**: After approved changes, create atomic conventional commits automatically

**File**: `.claude/hooks/stop-auto-commit`

```python
#!/usr/bin/env python3
"""
Automatically create conventional commits after changes.
Only runs when changes are staged and ready.

SAFETY: NEVER runs git push - only commits locally.
"""
import json
import subprocess
import sys
from pathlib import Path

def get_changed_files():
    """Get list of modified/new files"""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True
    )
    return [line[3:] for line in result.stdout.strip().split('\n') if line]

def infer_commit_type(files):
    """Infer conventional commit type from changed files"""
    # Check file patterns
    if any('docs/' in f for f in files):
        return 'docs'
    if any('test' in f.lower() for f in files):
        return 'test'
    if any(f.endswith(('.yml', '.yaml', '.json', '.toml')) for f in files):
        return 'chore'
    if any('fix' in f.lower() or 'bug' in f.lower() for f in files):
        return 'fix'

    # Default to feat for new functionality
    return 'feat'

def infer_scope(files):
    """Determine scope from files"""
    if any('tools/symlinks' in f for f in files):
        return 'symlinks'
    elif any('install/' in f for f in files):
        return 'install'
    elif any('.claude/hooks' in f for f in files):
        return 'hooks'
    elif any('docs/' in f for f in files):
        return 'docs'
    elif any('taskfiles/' in f for f in files):
        return 'taskfiles'
    return None

def create_commit_message(files, commit_type, scope):
    """Generate conventional commit message"""
    # Simple description based on files
    if len(files) == 1:
        desc = f"update {Path(files[0]).name}"
    elif len(files) <= 3:
        desc = "update " + ", ".join(Path(f).name for f in files[:3])
    else:
        desc = f"update {len(files)} files"

    # Build message
    if scope:
        return f"{commit_type}({scope}): {desc}"
    else:
        return f"{commit_type}: {desc}"

def main():
    hook_input = json.loads(sys.stdin.read())

    # Check if there are changes
    changed_files = get_changed_files()
    if not changed_files:
        exit(0)  # No changes, skip

    # Stage all changes
    subprocess.run(["git", "add", "-A"], check=True)

    # Generate commit message
    commit_type = infer_commit_type(changed_files)
    scope = infer_scope(changed_files)
    message = create_commit_message(changed_files, commit_type, scope)

    # Create commit
    try:
        result = subprocess.run(
            ["git", "commit", "-m", message],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 0:
            print(f"✅ Committed: {message}")
        else:
            # Pre-commit hook may have made changes
            if "files were modified by this hook" in result.stdout:
                # Amend commit with hook changes
                subprocess.run(["git", "add", "-A"], check=True)
                subprocess.run(["git", "commit", "--amend", "--no-edit"], check=True)
                print(f"✅ Committed (with pre-commit fixes): {message}")
            else:
                print(f"⚠️  Commit failed: {result.stderr}", file=sys.stderr)
                exit(1)

    except Exception as e:
        print(f"❌ Commit error: {e}", file=sys.stderr)
        exit(1)

if __name__ == "__main__":
    main()
```

**Make executable**:

```bash
chmod +x .claude/hooks/stop-auto-commit
```

**Add to settings** (initially disabled):

```json
{
  "hooks": {
    "Stop": [
      {
        "command": "bash .claude/hooks/stop-build-check",
        "description": "Run builds and catch errors"
      },
      {
        "command": "python .claude/hooks/stop-auto-commit",
        "description": "Auto-commit changes (conventional commits)",
        "enabled": false
      }
    ]
  }
}
```

### Week 2 Checklist

- [ ] Install pre-commit framework via uv
- [ ] Create `.pre-commit-config.yaml`
- [ ] Run `pre-commit install` and `pre-commit install --hook-type commit-msg`
- [ ] Test conventional commits enforcement manually
- [ ] Implement `stop-auto-commit` hook
- [ ] Test auto-commit workflow (keep disabled initially)
- [ ] Practice manual commits following conventional format
- [ ] Document commit message format in docs

---

## 📋 PHASE 3: Skills & Skill Activation (Week 3)

**Goal**: Automatic skill loading based on file context

### 3.1 Create skill-rules.json

**File**: `.claude/skill-rules.json`

```json
{
  "symlinks-developer": {
    "type": "domain",
    "enforcement": "suggest",
    "priority": "high",
    "promptTriggers": {
      "keywords": ["symlink", "symlinks", "relink"],
      "intentPatterns": [
        "(fix|debug|update).*symlink",
        "symlink.*(broken|missing|error)"
      ]
    },
    "fileTriggers": {
      "pathPatterns": ["tools/symlinks/**/*.py"],
      "contentPatterns": ["from pathlib import Path", "symlink_to"]
    }
  },

  "dotfiles-install": {
    "type": "domain",
    "enforcement": "suggest",
    "priority": "high",
    "promptTriggers": {
      "keywords": ["install", "bootstrap", "setup", "taskfile"],
      "intentPatterns": [
        "(create|update|fix).*install",
        "(macos|wsl|arch).*(setup|install)"
      ]
    },
    "fileTriggers": {
      "pathPatterns": [
        "install/*.sh",
        "Taskfile.yml",
        "taskfiles/*.yml"
      ]
    }
  },

  "documentation": {
    "type": "cross-cutting",
    "enforcement": "suggest",
    "priority": "medium",
    "promptTriggers": {
      "keywords": ["docs", "documentation", "readme", "changelog"],
      "intentPatterns": [
        "(write|update|create).*docs",
        "document.*"
      ]
    },
    "fileTriggers": {
      "pathPatterns": ["docs/**/*.md"],
      "contentPatterns": ["^# ", "^## "]
    }
  }
}
```

### 3.2 UserPromptSubmit Hook - Skill Activation

**File**: `.claude/hooks/user-prompt-submit-skill-activation`

```python
#!/usr/bin/env python3
"""
Analyzes user prompts and file context to suggest relevant skills.
Based on showcase repo's skill activation pattern.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

def load_skill_rules():
    """Load skill-rules.json"""
    rules_path = Path(".claude/skill-rules.json")
    if not rules_path.exists():
        return {}

    with open(rules_path) as f:
        return json.load(f)

def check_prompt_triggers(prompt, skill_config):
    """Check if prompt matches skill keywords or patterns"""
    prompt_lower = prompt.lower()

    # Check keywords
    keywords = skill_config.get("promptTriggers", {}).get("keywords", [])
    if any(kw in prompt_lower for kw in keywords):
        return True

    # Check intent patterns
    patterns = skill_config.get("promptTriggers", {}).get("intentPatterns", [])
    for pattern in patterns:
        if re.search(pattern, prompt_lower):
            return True

    return False

def check_file_triggers(files, skill_config):
    """Check if any files match skill path patterns"""
    path_patterns = skill_config.get("fileTriggers", {}).get("pathPatterns", [])

    for file_path in files:
        for pattern in path_patterns:
            # Simple glob-like matching
            pattern_regex = pattern.replace("**", ".*").replace("*", "[^/]*")
            if re.search(pattern_regex, file_path):
                return True

    return False

def main():
    hook_input = json.loads(sys.stdin.read())
    prompt = hook_input.get("prompt", "")

    # Get recently modified files from git
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True,
        text=True
    )
    modified_files = result.stdout.strip().split('\n') if result.stdout else []

    # Load skills and check triggers
    skill_rules = load_skill_rules()
    activated_skills = []

    for skill_name, skill_config in skill_rules.items():
        if check_prompt_triggers(prompt, skill_config):
            activated_skills.append((skill_name, "prompt"))
        elif check_file_triggers(modified_files, skill_config):
            activated_skills.append((skill_name, "file"))

    if not activated_skills:
        exit(0)  # No skills activated

    # Generate skill activation message
    activation_msg = "\n🎯 **Skill Activation Check**\n\n"
    for skill_name, trigger_type in activated_skills:
        activation_msg += f"- Use `{skill_name}` skill (triggered by {trigger_type})\n"

    # Return as system message
    print(json.dumps({
        "continue": True,
        "systemMessage": activation_msg
    }))

if __name__ == "__main__":
    main()
```

**Make executable**:

```bash
chmod +x .claude/hooks/user-prompt-submit-skill-activation
```

**Add to settings**:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "command": "python .claude/hooks/user-prompt-submit-skill-activation",
        "description": "Auto-suggest relevant skills"
      }
    ]
  }
}
```

### 3.3 Create First Skill - Symlinks Developer

**File**: `.claude/skills/symlinks-developer/SKILL.md`

```markdown
---
description: "Managing dotfiles symlink system"
tags: ["symlinks", "dotfiles", "cross-platform"]
---

# Symlinks Developer

Expertise in the dotfiles symlink management system.

## Core Principles

- Symlinks deploy configs from repo to $HOME
- Layer pattern: common base + platform overlay
- Exclusion patterns must check complete path components (not substrings)

## Common Patterns

### Running Symlinks

```bash
# After adding/removing files
symlinks relink macos
symlinks relink wsl
symlinks relink arch

# Check current symlinks
symlinks check macos
```

### Testing

```bash
cd tools/symlinks
pytest -v
pytest tests/test_utils.py  # Unit tests
pytest tests/test_integration.py  # Integration tests
```

## Critical Bugs to Avoid

See [Common Errors](resources/common-errors.md) for detailed examples:

1. **Substring matching** - `.git/` excluding `.gitconfig`
2. **Relative path calculation** - Use stdlib, not manual logic
3. **Platform differences** - Binary names, case sensitivity

## Resources

- [Common Errors](resources/common-errors.md) - Pattern matching bugs
- [Testing Guide](resources/testing-guide.md) - Pytest coverage
- [Platform Differences](resources/platform-differences.md) - macOS vs Linux

## Quick Reference

**Location**: `tools/symlinks/`

**Main file**: `symlinks/manager.py`

**Tests**: `tests/` directory (25 tests total)

```

**Create resources directory**:
```bash
mkdir -p .claude/skills/symlinks-developer/resources
```

**File**: `.claude/skills/symlinks-developer/resources/common-errors.md`

```markdown
# Common Symlinks Errors

## 1. Pattern Matching Bug - .gitconfig Excluded

**Problem**: Directory pattern `.git/` incorrectly excluded `.gitconfig` file.

**Cause**: Substring matching instead of complete path component checking.

**Fix**: Check for `/.git/` or starts with `.git/`, not just `.git` substring.

See: `docs/learnings/directory-pattern-matching.md`

## 2. Relative Path Calculation

**Problem**: Manual path calculation broke 122 symlinks.

**Cause**: Flawed "common ancestor" logic.

**Fix**: Use Python stdlib `Path.relative_to(walk_up=True)` (Python 3.12+).

See: `docs/learnings/relative-path-calculation.md`

## 3. Cross-Platform Files

**Problem**: Some files needed on all platforms weren't symlinked.

**Cause**: Exclusion patterns not considering cross-platform usage.

**Fix**: Test edge cases - `.gitconfig`, `.gitignore`, `.gitattributes` should NEVER be excluded.

See: `docs/learnings/cross-platform-symlink-considerations.md`
```

### Week 3 Checklist

- [ ] Create `.claude/skill-rules.json`
- [ ] Create `.claude/skills/` directory
- [ ] Create first skill: `symlinks-developer`
- [ ] Add resources for symlinks skill
- [ ] Implement `user-prompt-submit-skill-activation` hook
- [ ] Test skill activation with relevant prompts
- [ ] Create second skill: `dotfiles-install`
- [ ] Create third skill: `documentation-writer`

---

## 📋 PHASE 4: Advanced Automation (Week 4)

**Goal**: Polish and advanced features

### 4.1 Notification Hook - Long-Running Operations

**Purpose**: Desktop notifications when waiting for input or completion

**File**: `.claude/hooks/notification-desktop`

```bash
#!/usr/bin/env bash
# Desktop notifications for Claude Code events

INPUT=$(cat)
MESSAGE=$(echo "$INPUT" | jq -r '.message // "Claude Code Notification"')

# macOS
if [[ "$(uname)" == "Darwin" ]]; then
    osascript -e "display notification \"$MESSAGE\" with title \"Claude Code\""
# Linux
elif command -v notify-send &>/dev/null; then
    notify-send "Claude Code" "$MESSAGE"
fi

exit 0
```

**Make executable**:

```bash
chmod +x .claude/hooks/notification-desktop
```

**Add to settings**:

```json
{
  "hooks": {
    "Notification": [
      {
        "command": "bash .claude/hooks/notification-desktop",
        "description": "Desktop notifications"
      }
    ]
  }
}
```

### 4.2 PreCompact Hook - Save Session State

**Purpose**: Preserve work context before memory compression

**File**: `.claude/hooks/pre-compact-save-state`

```python
#!/usr/bin/env python3
"""
Saves session state before compaction.
Creates a session summary with key context to restore after compact.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

def main():
    hook_input = json.loads(sys.stdin.read())

    # Create session archive
    session_dir = Path(".claude/sessions")
    session_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    session_file = session_dir / f"session-{timestamp}.json"

    # Save session metadata
    with open(session_file, 'w') as f:
        json.dump({
            "timestamp": timestamp,
            "cwd": hook_input["cwd"],
            "session_id": hook_input["session_id"],
            "transcript_path": hook_input.get("transcript_path")
        }, f, indent=2)

    print(f"💾 Session state saved to {session_file}")

if __name__ == "__main__":
    main()
```

**Make executable**:

```bash
chmod +x .claude/hooks/pre-compact-save-state
```

**Add to settings**:

```json
{
  "hooks": {
    "PreCompact": [
      {
        "command": "python .claude/hooks/pre-compact-save-state",
        "description": "Save session state"
      }
    ]
  }
}
```

### Week 4 Checklist

- [ ] Implement notification hook
- [ ] Implement pre-compact state saving
- [ ] Create `.claude/sessions/` directory
- [ ] Create `.claude/README.md` documenting all hooks
- [ ] Test notification on macOS/Linux
- [ ] Test session state saving
- [ ] Review and enable auto-commit hook (if ready)
- [ ] Document learnings from hook implementation

---

## 🔒 SAFETY GUARDRAILS

### Forbidden Commands

**NEVER run these** (add to hook safety checks):

```python
FORBIDDEN = [
    "git push",           # ❌ NEVER - you want to review first
    "rm -rf /",           # ❌ Obviously dangerous
    "sudo rm",            # ❌ Dangerous deletions
    "git reset --hard",   # ❌ Destructive, ask first
    "git push --force"    # ❌ Especially on main
]
```

### Hook Safety Best Practices

1. **Exit codes**:
   - `exit 0` - Success or non-critical failure (don't block)
   - `exit 2` - Critical error that Claude MUST fix
   - Other codes - Non-blocking errors with stderr shown

2. **Timeouts**: Keep hooks under 10 seconds for responsive UX

3. **Defensive scripting**:
   - Check file existence before operations
   - Quote all variables to prevent injection
   - Use `set -euo pipefail` in bash scripts

4. **Error handling**:
   - Catch exceptions in Python hooks
   - Provide helpful error messages
   - Log to stderr for debugging

---

## 📚 REFERENCES

1. **Showcase Repository**: <https://github.com/datapointchris/claude-code-infrastructure-showcase>
2. **Claude Hooks Docs**: <https://docs.claude.com/en/docs/claude-code/hooks-guide>
3. **Claude Hooks Reference**: <https://docs.claude.com/en/docs/claude-code/hooks>
4. **Pre-commit Framework**: <https://pre-commit.com>
5. **Conventional Commits**: <https://conventionalcommits.org>
6. **Hooks Mastery Repo**: <https://github.com/disler/claude-code-hooks-mastery>
7. **Awesome Claude Code**: <https://github.com/hesreallyhim/awesome-claude-code>

---

## 🎯 SUCCESS METRICS

### Phase 1 Success

- ✅ Session context loads automatically
- ✅ Files auto-format after edits
- ✅ Build errors caught immediately

### Phase 2 Success

- ✅ Pre-commit enforces conventional commits
- ✅ Auto-commit creates proper commit messages
- ✅ No commits with broken tests

### Phase 3 Success

- ✅ Skills activate based on prompt keywords
- ✅ Skills activate based on file context
- ✅ Relevant skills load without manual invocation

### Phase 4 Success

- ✅ Desktop notifications work
- ✅ Session state preserved across compactions
- ✅ Complete hooks system documented

---

## 📝 NOTES FOR IMPLEMENTATION

- Start with Phase 1 hooks disabled, enable one at a time
- Test each hook individually before combining
- Keep auto-commit disabled until confident with workflow
- Create `.claude/` directory structure first
- All hooks must be executable (`chmod +x`)
- Use `jq` for JSON parsing in bash hooks
- Python hooks need shebang: `#!/usr/bin/env python3`
- Review CLAUDE.md after implementation to document the system

---

**Status**: Ready for implementation
**Next Step**: Compact conversation, then implement Phase 1
