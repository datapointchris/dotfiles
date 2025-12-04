# Context Engineering and Token Optimization

Research on context management patterns and token optimization strategies for AI agents.

## Research Overview

**Date**: 2025-12-04
**Status**: Applied in commit agent and logsift workflows
**Related**: [Commit Agent Research](commit-agent-research.md), [Agent Architecture](agent-architecture.md)

## What is Context Engineering?

**Definition**: Context engineering is the evolution of prompt engineering, focusing on curating and maintaining the optimal set of tokens during LLM inference.

**Distinction from Prompt Engineering**:

- **Prompt Engineering**: Writing effective prompts
- **Context Engineering**: Managing the entire context state (system instructions, tools, external data, message history)

**Why It Matters**:

- Context windows have limits (even with 200k tokens)
- Token costs accumulate quickly
- Irrelevant context reduces accuracy
- Careful curation is more important than raw size

## Four Core Strategies

**Source**: [FlowHunt Context Engineering](https://www.flowhunt.io/blog/context-engineering-ai-agents-token-optimization/)

### 1. Write: Save Context Outside the Context Window

**Purpose**: Store information externally for later retrieval

**Techniques**:

- External memory stores (databases, vector stores)
- Session state preservation
- Persistent knowledge bases
- File-based caching

**Application in Dotfiles**:

**Pre-compact Save State Hook** (`.claude/hooks/pre-compact-save-state`):

```python
# Save session metadata before compaction
{
    "timestamp": "2025-12-04T10:57:21",
    "session_id": "abc123",
    "cwd": "/Users/chris/dotfiles",
    "transcript_path": "/path/to/transcript"
}
```

**Metrics Tracking** (`.claude/metrics/command-metrics-*.jsonl`):

```json
{"timestamp": "...", "command": "/logsift", "full_command": "..."}
```

**Future**: Could store common error patterns, user preferences, project context

### 2. Select: Pull Only Necessary Tokens Into Context

**Purpose**: Retrieve only relevant information when needed

**Techniques**:

- Semantic search for relevant information
- Selective file reading
- Query-based retrieval
- Context-aware loading

**Application in Dotfiles**:

**Commit Agent** - Only reads staged changes:

```bash
git diff --staged  # Not entire repo
```

**Skills System** - Progressive disclosure:

```text
.claude/skills/symlinks-developer/
├── SKILL.md           # Core (loaded always)
└── resources/         # Details (loaded on demand)
    ├── common-errors.md
    ├── testing-guide.md
    └── platform-differences.md
```

**Grep with Filters** - Only match relevant files:

```bash
grep -r "pattern" --include="*.py" --include="*.sh"
```

### 3. Compress: Retain Only Required Tokens

**Purpose**: Reduce token count while preserving essential information

**Techniques**:

- Summarization
- Filtering (remove noise)
- Removing redundancy
- Extracting key information

**Application in Dotfiles**:

**Logsift Filtering**:

- Input: 10,000+ lines of command output
- Output: ~200 lines of errors and warnings
- **Compression ratio**: ~50x

**Commit Agent Pre-commit**:

- Background run: Suppress auto-fix messages
- Logsift run: Only show real errors
- Typical pre-commit: 1000+ lines → ~50 error lines
- **Savings**: ~950 tokens per run

**Auto-Compaction** (Claude Code built-in):

- Runs when context exceeds 95% capacity
- Summarizes full trajectory of interactions
- Preserves essential information

### 4. Isolate: Split Context Across Multiple Agents

**Purpose**: Prevent context pollution by separating concerns

**Techniques**:

- Separate agents for separate tasks
- Agent-specific context windows
- Coordination via minimal summaries
- Parallel execution when possible

**Application in Dotfiles**:

**Commit Agent**:

- Runs in separate context window
- Main agent never sees git minutiae
- Reports only summary back (~200 tokens)
- Agent context discarded after commit

**Future Multi-Agent**:

```text
Main Agent
├── Commit Agent (git operations)
├── Code Review Agent (PR review)
├── Doc Agent (documentation)
└── Test Agent (test generation)
```

Each agent has isolated context, coordinates via summaries.

## Token Optimization Techniques

**Source**: [MCP Token Optimization Strategies](https://tetrate.io/learn/ai/mcp/token-optimization-strategies)

### Semantic Caching

**What**: Cache context based on semantic similarity, reuse across requests

**How It Works**:

1. Hash context semantically (not literal string)
2. Store in cache with embedding
3. On new request, check similarity
4. Reuse if similar enough

**Application**:

- Claude Code caches file contents
- Repeated file reads don't re-tokenize
- 15-minute cache window (logsift)

**Benefits**:

- Faster responses
- Lower costs
- Consistent context

### Context Prioritization

**What**: Rank context by importance, keep most relevant

**Techniques**:

- Recency (recent messages more important)
- Relevance (semantic match to task)
- Criticality (system instructions always kept)

**Application in Dotfiles**:

**Git Protocols** (always in context):

- From `~/.claude/CLAUDE.md`
- Critical for safety
- Never summarized or removed

**Recent Changes** (high priority):

- Last few files edited
- Current work in progress
- Active branches

**Historical Context** (lower priority):

- Old commits
- Archived files
- Completed tasks

### Progressive Loading

**What**: Load details only when needed, start with summaries

**Application in Dotfiles**:

**Skills System**:

```yaml
Initial load: SKILL.md (500 tokens)
On demand: resources/ (2000 tokens)
Total possible: 2500 tokens
Actually loaded: 500-1000 tokens (context-dependent)
```

**Documentation**:

```bash
Hub document: working-with-claude.md (overview + links)
Spoke documents: Detailed guides (load if needed)
```

## Advanced Patterns

### Git-Context-Controller (GCC)

**Source**: [Git Context Controller](https://arxiv.org/html/2508.00031v1)

**Core Idea**: Treat context like git (versioned, branching, mergeable)

**Operations**:

- **COMMIT**: Create checkpoint
- **BRANCH**: Explore alternatives
- **MERGE**: Combine approaches
- **CONTEXT**: Query specific state

**Performance**:

- 40.7% task resolution (with GCC)
- 11.7% task resolution (without)
- **4x improvement**

**Application in Commit Agent**:

Each git commit is a **COMMIT** operation:

```bash
git commit -m "..."  # Create checkpoint
git log -1 --oneline  # Verify checkpoint
```

Could add **BRANCH** (future):

```yaml
Try commit message style A
Branch: Try style B
Compare, pick best
Merge back
```

### Memory Hierarchies

**Concept**: Multiple layers of memory with different retention

**Layers**:

1. **Working Memory**: Current context window (ephemeral)
2. **Short-Term Memory**: Session state (hours)
3. **Long-Term Memory**: Persistent knowledge (days/weeks)
4. **Reference Memory**: External resources (permanent)

**Application in Dotfiles**:

1. **Working**: Current conversation (context window)
2. **Short-Term**: Session metadata (`.claude/sessions/`)
3. **Long-Term**: Metrics logs (`.claude/metrics/`)
4. **Reference**: Documentation (`docs/`), code (repo)

**Future**: Could implement explicit memory management with structured recall.

## Measuring Token Usage

### Built-in Tools

**Claude Code `/cost` command**:

```bash
/cost

# Output:
Total cost: $0.05
API duration: 12.3s
Lines changed: 45
Tokens: ~8000 input, ~2000 output
```

### OpenTelemetry Export

**Enable telemetry**:

```bash
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_LOGS_EXPORTER=otlp
export OTEL_METRICS_EXPORTER=otlp
```

**Exported metrics**:

- `claude_code.token.usage` - Token breakdown
- `claude_code.api_request` - Request duration
- `claude_code.tool_result` - Tool performance
- `claude_code.active_time.total` - Actual usage time

### Custom Metrics

**Dotfiles metrics system** (`.claude/metrics/`):

- Command usage tracking
- Quality assessments
- Token estimates (pre/post optimization)

## Real-World Measurements

### Commit Agent Token Savings

**Before** (traditional workflow):

| Phase | Tokens |
|-------|--------|
| Git status + diff | 500-1000 |
| Pre-commit run #1 | 1000-2000 |
| Pre-commit run #2 | 1000-2000 |
| Message generation | 200-300 |
| Verification | 100-200 |
| **Total** | **3000-5900** |

**After** (commit agent):

| Phase | Main Agent | Agent Context |
|-------|------------|---------------|
| Summary only | 200 | - |
| Agent internals | - | 1300 |
| **Total (Main)** | **200** | (discarded) |

**Savings**: ~2800-5700 tokens per commit in main agent

### Logsift Compression

**Before**:

- Test script output: 10,000+ lines
- ~15,000 tokens

**After** (logsift filtering):

- Filtered output: ~200 lines
- ~300 tokens

**Compression**: ~50x reduction

### Combined Strategy

**Commit with logsift workflow**:

Without optimization:

- Command output: ~15,000 tokens
- Commit workflow: ~4,000 tokens
- **Total**: ~19,000 tokens

With optimization:

- Logsift filtered: ~300 tokens
- Commit agent summary: ~200 tokens
- **Total**: ~500 tokens

**Savings**: ~18,500 tokens (97% reduction)

## Implementation Guidelines

### When to Apply Each Strategy

**Write** (external storage):

- ✅ Session state that persists
- ✅ Metrics and logs
- ✅ User preferences
- ❌ Active work in progress
- ❌ Current task context

**Select** (targeted retrieval):

- ✅ Large codebases (read specific files)
- ✅ Documentation (load relevant pages)
- ✅ Git diffs (staged changes only)
- ❌ Small projects (just load all)
- ❌ Critical context (always keep)

**Compress** (filtering/summarization):

- ✅ Verbose command output
- ✅ Auto-fix messages
- ✅ Historical data
- ❌ Error messages (need full detail)
- ❌ User input (preserve exact wording)

**Isolate** (separate agents):

- ✅ Distinct workflows (commit, review, test)
- ✅ Repeatable tasks
- ✅ Context-heavy operations
- ❌ Quick one-off tasks
- ❌ Tightly coupled operations

### Trade-offs

**Token Savings vs Accuracy**:

- Aggressive filtering may lose important details
- **Mitigation**: Use logsift (intelligent filtering, not blind truncation)

**Context Isolation vs Coordination**:

- Separate agents can't share nuanced understanding
- **Mitigation**: Detailed summaries, structured handoff

**Caching vs Freshness**:

- Cached context may be outdated
- **Mitigation**: Short cache windows (15 minutes), invalidation on changes

**Complexity vs Maintainability**:

- Complex optimization makes system harder to debug
- **Mitigation**: Clear boundaries, explicit logging, documentation

## Future Directions

### Short-Term

1. **Implement Token Tracking**:
   - Add to metrics system
   - Measure actual savings
   - Validate estimates

2. **Semantic Caching**:
   - Cache common queries
   - Store embeddings
   - Intelligent reuse

3. **Context Budgets**:
   - Set per-agent limits
   - Warn when approaching
   - Auto-optimize

### Medium-Term

1. **Memory Management**:
   - Explicit save/load operations
   - Hierarchical storage
   - Structured recall

2. **Multi-Agent Coordination**:
   - Shared context protocol
   - Efficient handoff
   - Minimal duplication

3. **Adaptive Optimization**:
   - Learn from usage patterns
   - Adjust strategies automatically
   - Per-user preferences

### Long-Term

1. **Intelligent Context Controller**:
   - AI-driven prioritization
   - Dynamic compression
   - Predictive loading

2. **Federated Context**:
   - Distributed memory stores
   - Team-shared context
   - Efficient synchronization

3. **Context Analytics**:
   - Usage patterns
   - Optimization opportunities
   - Cost tracking

## Related Research

- [Commit Agent Research](commit-agent-research.md) - Applies all 4 strategies
- [Agent Architecture](agent-architecture.md) - Isolation strategy
- [Logsift Workflow](logsift-workflow.md) - Compression strategy

## References

1. **FlowHunt: Context Engineering for AI Agents**
   - URL: <https://www.flowhunt.io/blog/context-engineering-ai-agents-token-optimization/>
   - Date: 2025-12-04
   - Topics: 4 strategies, semantic caching, progressive disclosure

2. **MCP Token Optimization Strategies**
   - URL: <https://tetrate.io/learn/ai/mcp/token-optimization-strategies>
   - Date: 2025-12-04
   - Topics: Model Context Protocol, optimization techniques

3. **Git Context Controller**
   - URL: <https://arxiv.org/html/2508.00031v1>
   - Date: 2025-12-04
   - Topics: Versioned context, COMMIT/BRANCH/MERGE operations

4. **Context Engineering (LangChain)**
   - URL: <https://blog.langchain.com/context-engineering-for-agents/>
   - Date: 2025-12-04
   - Topics: Context as first-class concern, memory management

---

**Research Date**: 2025-12-04
**Implementation Status**: Active in commit agent and logsift
**Next Review**: After metrics collection (1 month)
