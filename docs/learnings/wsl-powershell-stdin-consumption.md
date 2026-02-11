# WSL PowerShell Stdin Consumption in Loops

When calling PowerShell from bash while-read loops, PowerShell can consume stdin meant for the loop.

## The Problem

A `while read` loop processing files was only handling 1-2 iterations instead of all 8 files:

```bash
while IFS= read -r -d '' font_file; do
    # Process file...
    powershell.exe -NoProfile -Command "..."  # This consumed remaining stdin!
done < <(find ... -print0)
```

The loop would exit early with no error - PowerShell silently consumed the process substitution's output.

## The Solution

Redirect stdin to `/dev/null` for PowerShell commands inside loops:

```bash
powershell.exe -NoProfile -Command "..." </dev/null 2>/dev/null || true
```

## Key Learnings

- PowerShell inherits stdin from the parent shell process
- In while-read loops using process substitution, this stdin is the loop's data source
- PowerShell can consume this data even when not explicitly reading input
- Always use `</dev/null` for PowerShell/cmd.exe calls inside loops
- This also applies to other Windows executables called via WSL interop

## Testing

```bash
# Verify loop processes all items
count=0
while IFS= read -r -d '' f; do
    powershell.exe -Command "Write-Host test" </dev/null
    count=$((count + 1))
done < <(find /tmp -maxdepth 1 -type f -print0 | head -c 1000)
echo "Processed: $count"  # Should match file count
```

## Related

- `management/common/lib/font-installer.sh` - WSL font registry integration
- `management/wsl/lib/install-windows-font.sh` - Standalone font installer
