---
icon: material/chart-timeline-variant
---

# Patterns

Quick timestamped note logging for tracking patterns in health, mood, habits, and daily observations. Stores entries in JSONL format for easy analysis.

## Quick Start

```bash
patterns 'had coffee around 3pm'
patterns 'feeling slight heartburn'
patterns 'slept well, 8 hours'

patterns list                    # View all entries
patterns search coffee           # Search for entries
```

Each entry is timestamped and appended to `~/.local/share/patterns/entries.jsonl`.

## Commands

### Log Entry

```bash
patterns 'your message here'
```

Log a timestamped observation. **Quotes are required** to distinguish messages from commands.

### List Entries

```bash
patterns list
```

View all entries in log format with syntax highlighting (via bat):

```yaml
2025-12-11T15:30:45-0500 | had coffee around 3pm
2025-12-11T18:22:10-0500 | feeling slight heartburn
2025-12-11T22:15:00-0500 | slept well, 8 hours
```

### Search Entries

```bash
patterns search 'term'
patterns search coffee
patterns search heartburn
```

Search entries for matching text (case-insensitive). Results displayed with syntax highlighting.

### Help

```bash
patterns help
```

Show usage information and examples.

## Data Format

Entries are stored as JSON Lines (JSONL) in `~/.local/share/patterns/entries.jsonl`:

```json
{"timestamp": "2025-12-11T15:30:45-0500", "message": "had coffee around 3pm"}
{"timestamp": "2025-12-11T18:22:10-0500", "message": "feeling slight heartburn"}
```

Each line is a complete JSON object with:

- `timestamp` - ISO 8601 format with local timezone offset
- `message` - Your note text

## Advanced Analysis

The JSONL format works seamlessly with command-line tools:

### Using jq

View all entries as JSON:

```bash
jq '.' ~/.local/share/patterns/entries.jsonl
```

Extract just messages:

```bash
jq -r '.message' ~/.local/share/patterns/entries.jsonl
```

Filter by date:

```bash
jq 'select(.timestamp | startswith("2025-12-11"))' ~/.local/share/patterns/entries.jsonl
```

Format for reading:

```bash
jq -r '"\(.timestamp) | \(.message)"' ~/.local/share/patterns/entries.jsonl
```

Group by date:

```bash
jq -r '.timestamp[:10] + " | " + .message' ~/.local/share/patterns/entries.jsonl | sort
```

### Using grep

Quick text search without JSON parsing:

```bash
grep -i coffee ~/.local/share/patterns/entries.jsonl
grep "2025-12-11" ~/.local/share/patterns/entries.jsonl
```

### Python Analysis

Import and analyze with Python:

```python
import json
from datetime import datetime
from collections import defaultdict

# Load all entries
entries = []
with open('~/.local/share/patterns/entries.jsonl') as f:
    for line in f:
        entries.append(json.loads(line))

# Find all entries with 'coffee'
coffee_entries = [e for e in entries if 'coffee' in e['message'].lower()]
print(f"Coffee mentioned {len(coffee_entries)} times")

# Group by date
by_date = defaultdict(list)
for entry in entries:
    date = entry['timestamp'][:10]
    by_date[date].append(entry['message'])

# Find correlations
for date, messages in by_date.items():
    if any('coffee' in m.lower() for m in messages) and \
       any('heartburn' in m.lower() for m in messages):
        print(f"{date}: Coffee AND heartburn")
```

## Use Cases

Track patterns over time by logging brief observations:

- **Health tracking** - Food intake, symptoms, energy levels, sleep quality
- **Mood monitoring** - Emotional states, triggers, stress levels
- **Habit formation** - Activities, exercise, meditation, reading
- **Work patterns** - Productivity, focus times, distractions
- **Symptom correlation** - Find connections between activities and outcomes (e.g., coffee → heartburn)

The goal is to capture many small data points throughout the day for later pattern analysis.

## Example Workflow

Morning:

```bash
patterns 'woke up at 6:30, felt rested'
patterns 'had coffee and toast for breakfast'
```

Afternoon:

```bash
patterns 'slight headache around 2pm'
patterns 'had second coffee at 3pm'
```

Evening:

```bash
patterns 'headache gone after water'
patterns 'feeling tired, going to bed early'
```

Later analysis:

```bash
patterns search headache
patterns search coffee
# Notice pattern: coffee → headache correlation
```

## Data Location

- **Data file**: `~/.local/share/patterns/entries.jsonl`
- **Format**: JSON Lines (one JSON object per line)
- **Backup**: Not tracked in dotfiles (personal data)

Consider backing up this file periodically if you accumulate valuable data.

## Dependencies

- **jq** - Required for logging and built-in commands
- **bat** - Optional, used for syntax highlighting in list/search (falls back to plain text)

## Tips

1. **Be consistent** - Log regularly throughout the day for better pattern detection
2. **Be brief** - Short observations are easier to analyze than long entries
3. **Be specific** - Include times and quantities when relevant
4. **Review regularly** - Use `patterns search` to look for correlations
5. **Backup data** - Your patterns are personal data worth preserving
