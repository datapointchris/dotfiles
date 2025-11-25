# Bash Script Testing - Lessons from backup-dirs

## Context

Developed a complex bash script (`backup-dirs`) with progress tracking, path handling, and background processes. Passed shellcheck and appeared production-ready, but had multiple critical bugs that only surfaced during real-world testing.

## The Problem

Shellcheck passing does not mean a bash script works correctly. We encountered:

1. **Unbound variable errors** with `set -u` when arrays were empty
2. **Path handling bugs** - double-prepending HOME to absolute paths
3. **Missing fd flags** - `--no-ignore` and `--hidden` needed to match tar behavior
4. **Progress tracking broken** - file count stuck at 0 due to subshell scope
5. **Exclude pattern expansion** - wrong syntax for array expansion
6. **Estimate accuracy** - 409 estimated vs 2929 actual (7x off!)

All of these passed shellcheck but failed during execution.

## The Solution

### Comprehensive Testing Strategy

**1. Shellcheck First (Syntax & Best Practices)**

```bash
shellcheck script.sh
```

Catches common issues but NOT logic errors.

**2. Test All Flag Combinations**

```bash
# No arguments
script.sh

# Single argument
script.sh arg1

# Multiple arguments
script.sh arg1 arg2 arg3

# With flags
script.sh --flag value arg1
script.sh arg1 --flag value

# Edge cases
script.sh ~/absolute/path
script.sh relative/path
script.sh /outside/home/path
script.sh nonexistent-dir
```

**3. Test With Real Data**

Don't just test with toy examples. Run on actual target data:

- Small datasets (quick iterations)
- Real-world datasets (uncover scaling issues)
- Edge case datasets (symlinks, special chars, deep nesting)

**4. Verify Assumptions**

Document and test assumptions:

```bash
# Assumption: fd and tar count the same entries
# Test: Compare counts manually
cd ~ && fd --type f . dotfiles | wc -l  # Wrong! Missing --no-ignore
cd ~ && tar -czf test.tar.gz -v dotfiles | wc -l
```

Our assumption was wrong: fd respects .gitignore by default, tar doesn't!

**5. Handle Empty Arrays with set -u**

```bash
# Wrong - fails with set -u when array is empty
RESULT=("${array[@]}")

# Right - handle empty arrays
if [[ ${#array[@]} -gt 0 ]]; then
  RESULT=("${array[@]}")
else
  RESULT=()
fi
```

**6. Test Background Processes**

Scripts with background processes need special attention:

- Verify cleanup on Ctrl+C
- Check for race conditions
- Test temp file IPC
- Verify final counts are written before reading

**7. Test Timing-Dependent Code**

Progress bars with time-based updates can fail on fast operations:

```bash
# Wrong - may never update if completes too fast
if [[ $elapsed -ge $update_interval ]]; then
  echo "$count" > "$progress_file"
fi
# Loop ends, count never written!

# Right - always write final count
while ...; do
  # Time-based updates during loop
done
echo "$final_count" > "$progress_file"  # Ensure final write
```

## Key Learnings

**Testing Hierarchy:**

1. Shellcheck (syntax, common pitfalls)
2. Unit testing (each function/feature)
3. Integration testing (all flags, combinations)
4. Real-world testing (actual use cases)
5. Edge case testing (failure modes)

**Common Bash Gotchas:**

- `set -u` with empty arrays
- Variables in pipes/subshells don't affect parent
- fd respects .gitignore by default (use `--no-ignore --hidden`)
- Array expansion syntax differs from string expansion
- Background process cleanup needs trap handlers
- Time-based logic can skip on fast operations

**Best Practices:**

- Pull configuration values to top of script
- Make assumptions explicit in comments
- Test each assumption independently
- Document why certain flags are needed
- Test with both toy data AND real data
- Verify counts/estimates match reality

**When "Production Ready" Isn't:**

Passing shellcheck and looking correct doesn't mean it works. The only way to know: run it with real data, all flag combinations, and edge cases. Thorough testing is especially critical for bash where the syntax is terse and errors are often silent.

## Related

- `apps/common/backup-dirs` - The script that taught us these lessons
- [Shellcheck Wiki](https://www.shellcheck.net/wiki/)
- `docs/development/testing.md` - General testing documentation
