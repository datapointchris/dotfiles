# Logsift Command Metrics

Tracking system for measuring token usage, context efficiency, and quality of `/logsift` and `/logsift-auto` commands.

## Metrics Collected

### Quantitative Metrics (Automated)

1. **Token Usage**
   - Via `/cost` command during sessions
   - OpenTelemetry export (when enabled)
   - Input vs output tokens
   - Cache hit rates

2. **Command Execution**
   - Total invocations per command type
   - Timestamp and session ID
   - Working directory context
   - Command parameters

3. **Error Resolution**
   - Initial error count (from logsift)
   - Final error count (from logsift)
   - Iterations required to resolve
   - Error types encountered

### Qualitative Metrics (Manual Tracking)

Track these in `quality-log.md` after each session:

1. **Correctness**
   - Did the command complete successfully?
   - Were all errors resolved?
   - Were root causes identified?
   - Were fixes appropriate?

2. **Efficiency**
   - How many iterations needed?
   - Was Claude's approach optimal?
   - Did it read necessary files?
   - Did it avoid unnecessary exploration?

3. **Methodology Adherence**
   - Did Claude follow the 5-phase approach?
   - Did it distinguish related vs independent errors?
   - Did it prioritize correctly?
   - Did it background the process? (should never happen)

4. **Comparison: /logsift vs /logsift-auto**
   - Command parsing accuracy (auto only)
   - Token difference
   - Quality difference
   - Time to resolution

## Data Files

```text
.claude/metrics/
├── README.md                          # This file
├── command-metrics-YYYY-MM-DD.jsonl   # Automated command logs
├── quality-log.md                     # Manual quality assessments
└── analysis/                          # Generated reports
    ├── weekly-summary.md
    └── comparison-logsift-vs-auto.md
```

## Usage

### View Metrics

```bash
analyze-logsift-metrics              # Summary
analyze-logsift-metrics --details    # Detailed breakdown
analyze-logsift-metrics --date 2025-12-03  # Specific date
```

### Manual Quality Entry Template

Add to `quality-log.md` after significant logsift sessions:

```markdown
## YYYY-MM-DD HH:MM - Session ID

**Command**: `/logsift "command here"` or `/logsift-auto description`

**Context**: Brief description of what you were testing

**Quantitative**:
- Initial errors: X
- Final errors: 0
- Iterations: Y
- Estimated tokens: Z (from /cost)

**Qualitative**:
- Correctness: ✅/⚠️/❌
- Efficiency: ✅/⚠️/❌
- Methodology: ✅/⚠️/❌

**Notes**:
- What worked well
- What could improve
- Specific observations

**Comparison** (if applicable):
- /logsift vs /logsift-auto differences
```

## Key Performance Indicators (KPIs)

Based on [LLM agent best practices](https://www.confident-ai.com/blog/llm-evaluation-metrics-everything-you-need-for-llm-evaluation):

### Quality KPIs

- **Success Rate**: % of sessions that resolved all errors
- **Root Cause Accuracy**: % where root causes were correctly identified
- **Methodology Compliance**: % following the 5-phase approach
- **Anti-pattern Avoidance**: % avoiding backgrounding, symptom fixes, etc.

### Efficiency KPIs

- **Average Iterations to Success**: Lower is better
- **Token Usage per Error Resolved**: Efficiency metric
- **Context Usage Efficiency**: Tokens saved by logsift filtering
- **Time to First Fix**: How quickly Claude starts fixing

### Comparative KPIs

- **/logsift vs /logsift-auto Success Delta**: Quality difference
- **/logsift vs /logsift-auto Token Delta**: Context efficiency difference
- **Parsing Accuracy**: % of /logsift-auto commands parsed correctly

## Analysis Cadence

- **Daily**: Quick review of command usage (`analyze-logsift-metrics`)
- **Weekly**: Quality assessment of 5-10 sessions (manual log)
- **Monthly**: Generate comparison reports and trends

## OpenTelemetry Export (Optional)

For detailed token tracking:

```bash
# In ~/.zshrc or ~/.bashrc
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_LOGS_EXPORTER=otlp
export OTEL_METRICS_EXPORTER=otlp
```

Exported metrics include:

- `claude_code.token.usage` - Token breakdown
- `claude_code.api_request` - Request duration
- `claude_code.tool_result` - Tool performance

## Future Enhancements

1. **Automated Quality Detection**
   - Parse logsift analysis reports
   - Detect methodology compliance from transcript
   - Auto-score sessions

2. **Cost Tracking Integration**
   - Hook into Anthropic Admin API
   - Track per-command costs
   - Budget alerts

3. **Comparison Dashboard**
   - Visual comparison of /logsift vs /logsift-auto
   - Token usage trends
   - Success rate over time

4. **Pre-commit Agent Metrics**
   - Track commit agent usage
   - Pre-commit hook token savings
   - Quality of commit messages

## References

- [Claude Code Monitoring Usage](https://code.claude.com/docs/en/monitoring-usage.md)
- [LLM Evaluation Metrics Guide](https://www.confident-ai.com/blog/llm-evaluation-metrics-everything-you-need-for-llm-evaluation)
- [Token Usage Tracking in LLMs](https://codesignal.com/learn/courses/behavioral-benchmarking-of-llms/lessons/measuring-and-interpreting-token-usage-in-llms)
- [LLM Observability Tools 2025](https://www.comet.com/site/blog/llm-observability-tools/)
