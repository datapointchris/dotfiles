# Skills System

Claude Code skills provide domain-specific expertise that auto-activates based on prompt keywords, intent patterns, and file context.

## How It Works

The UserPromptSubmit hook analyzes your prompts and recently modified files, then suggests relevant skills before Claude sees your message.

**Auto-activation triggers**:

- **Keyword matching** - Prompt contains skill keywords (e.g., "symlink", "install", "docs")
- **Intent patterns** - Regex matches on user intent like `"(fix|debug).*symlink"`
- **File patterns** - Editing files matching pathPatterns (e.g., `tools/symlinks/**/*.py`)

**Configuration**: `.claude/skill-rules.json`

## Available Skills

### symlinks-developer

Expertise in the dotfiles symlink management system.

**Triggers**:

- Keywords: symlink, symlinks, relink
- Intent: `(fix|debug|update).*symlink`, `symlink.*(broken|missing|error)`
- Files: `tools/symlinks/**/*.py`

**Provides**:

- Core principles (layered architecture, exclusion patterns)
- Common commands (relink, check)
- Critical bugs to avoid
- Testing guide
- Platform differences

**Resources**: common-errors.md, testing-guide.md, platform-differences.md

### dotfiles-install

Bootstrap and installation process expertise.

**Triggers**:

- Keywords: install, bootstrap, setup, taskfile
- Intent: `(create|update|fix).*install`, `(macos|wsl|arch).*(setup|install)`
- Files: `install/*.sh`, `Taskfile.yml`, `taskfiles/*.yml`

### documentation

Documentation writing and updates.

**Triggers**:

- Keywords: docs, documentation, readme, changelog
- Intent: `(write|update|create).*docs`, `document.*`
- Files: `docs/**/*.md`

## Creating Skills

Skills follow progressive disclosure pattern: concise main file with detailed resources on demand.

### Structure

```text
.claude/skills/skill-name/
├── SKILL.md              # Main file (keep under 500 lines)
└── resources/            # Detailed documentation
    ├── topic-1.md
    ├── topic-2.md
    └── topic-3.md
```

### Main SKILL.md

Include frontmatter with description and tags:

```markdown
---
description: "Brief description"
tags: ["tag1", "tag2"]
---

# Skill Name

Core principles, common patterns, critical bugs, quick reference.
```

**Keep concise**: Main file should be skimmable reference, not comprehensive guide.

### Resources

Detailed docs that load only when needed:

- Common errors and solutions
- Testing strategies
- Platform-specific considerations
- Extended examples

Target 30-100 lines per resource file.

## Configuration

Edit `.claude/skill-rules.json` to define activation triggers.

**Structure**:

```json
{
  "skill-name": {
    "type": "domain",              // or "cross-cutting"
    "enforcement": "suggest",       // non-blocking
    "priority": "high",             // high, medium, low
    "promptTriggers": {
      "keywords": ["keyword1", "keyword2"],
      "intentPatterns": [
        "regex pattern 1",
        "regex pattern 2"
      ]
    },
    "fileTriggers": {
      "pathPatterns": ["glob/pattern/**/*.ext"],
      "contentPatterns": ["regex for file contents"]
    }
  }
}
```

**Trigger types**:

- **keywords**: Literal strings in prompt (case-insensitive)
- **intentPatterns**: Regex patterns for user intent
- **pathPatterns**: Glob patterns for file paths (use `**` for recursive)
- **contentPatterns**: Regex patterns for file contents

Skills activate if ANY trigger matches (keywords OR intent OR files).

## Testing Skill Activation

Test the UserPromptSubmit hook directly:

```bash
# Test keyword trigger
echo '{"prompt": "fix symlink issue"}' | python .claude/hooks/user-prompt-submit-skill-activation

# Test file trigger (modify file first)
touch tools/symlinks/test.py
echo '{"prompt": "test"}' | python .claude/hooks/user-prompt-submit-skill-activation
```

Expected output shows activated skills:

```text
🎯 **Skill Activation Check**

- Use `symlinks-developer` skill (triggered by prompt)
```

## Best Practices

**Skill design**:

- One skill per domain (symlinks, installation, themes, etc.)
- Keep main SKILL.md under 500 lines
- Use resources for detailed docs
- Include "Critical Bugs to Avoid" section
- Provide testing commands

**Trigger configuration**:

- Use specific keywords (avoid generic terms like "update")
- Intent patterns should match common phrasing
- File patterns should be specific to avoid false positives
- Test triggers before committing

**Progressive disclosure**:

- Main file: principles, commands, quick reference
- Resources: detailed guides, platform differences, edge cases
- Link to learnings docs for specific gotchas

## Troubleshooting

**Skill not activating**:

- Check keyword spelling in `.claude/skill-rules.json`
- Verify regex patterns are correct (test with online regex tester)
- Ensure file patterns use glob syntax (`**` for recursive, `*` for wildcard)
- Test hook manually with sample input

**Wrong skill activating**:

- Refine keywords to be more specific
- Adjust priority (high/medium/low) to control precedence
- Narrow file patterns to avoid overlap

**Skill loads but doesn't help**:

- Main SKILL.md may need more detail
- Add resources for complex topics
- Include more examples in common patterns section
- Reference relevant learnings docs

## See Also

- [Claude Code Hooks](hooks.md) - Full hooks system documentation
- Claude Code README (`.claude/README.md`) - Complete hooks and skills reference
- [Symlinks Tool](symlinks.md) - Tool that symlinks-developer skill supports
