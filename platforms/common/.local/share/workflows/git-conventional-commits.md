# git conventional commits

Format: `type(scope): subject` — imperative mood, no period, 50 char max.

| Type     | Purpose                                           |
| -------- | ------------------------------------------------- |
| feat     | New feature or functionality                      |
| fix      | Bug fix                                           |
| docs     | Documentation only                                |
| chore    | Maintenance (deps, configs, CI)                   |
| refactor | Code change that neither fixes nor adds           |
| test     | Adding or updating tests                          |
| perf     | Performance improvement                           |
| ci       | CI/CD changes                                     |

Breaking changes — append `!` after type: `feat!: remove legacy auth endpoint`

```bash
# Examples
feat: add dark mode toggle
fix(auth): handle expired refresh tokens
docs: update API migration guide
refactor: extract validation into middleware
test(api): add integration tests for /users
chore: bump dependencies to latest

# Body — blank line after subject, wrap at 72 chars
feat: add export to CSV

Add CSV export for transaction history.
Supports date range filtering and custom delimiters.

# Footer — reference issues
fix(checkout): prevent double charge

Closes #142
```
