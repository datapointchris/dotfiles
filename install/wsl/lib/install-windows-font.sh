#!/usr/bin/env bash
# Install font files to Windows user fonts directory (WSL only)
# Usage: install-windows-font.sh <font-file> [font-file ...]
#
# This enables automatic font installation on WSL without manual steps.
# Fonts are installed per-user (no admin required).

set -euo pipefail

# Convert WSL path to Windows path
wsl_to_windows_path() {
  wslpath -w "$1"
}

install_font() {
  local font_file="$1"

  if [[ ! -f "$font_file" ]]; then
    echo "SKIP: File not found: $font_file" >&2
    return 1
  fi

  local win_path
  win_path=$(wsl_to_windows_path "$font_file")

  # Run PowerShell inline (avoids execution policy issues with external scripts)
  powershell.exe -NoProfile -Command "
    \$ErrorActionPreference = 'Stop'
    \$fontPath = '$win_path'

    \$fontFileName = [System.IO.Path]::GetFileName(\$fontPath)
    \$userFontsDir = \"\$env:LOCALAPPDATA\\Microsoft\\Windows\\Fonts\"
    \$destPath = Join-Path \$userFontsDir \$fontFileName

    # Create fonts directory if needed
    if (-not (Test-Path \$userFontsDir)) {
      New-Item -ItemType Directory -Path \$userFontsDir -Force | Out-Null
    }

    # Skip if already installed
    if (Test-Path \$destPath) {
      Write-Host \"SKIP: \$fontFileName\"
      exit 0
    }

    # Copy font file
    Copy-Item \$fontPath \$destPath -Force

    # Get font name using System.Drawing
    try {
      Add-Type -AssemblyName System.Drawing
      \$fontCollection = New-Object System.Drawing.Text.PrivateFontCollection
      \$fontCollection.AddFontFile(\$destPath)
      \$fontFamily = \$fontCollection.Families[0].Name

      \$style = ''
      if (\$fontFileName -match 'Bold' -and \$fontFileName -match 'Italic') {
        \$style = ' Bold Italic'
      } elseif (\$fontFileName -match 'Bold') {
        \$style = ' Bold'
      } elseif (\$fontFileName -match 'Italic') {
        \$style = ' Italic'
      }
      \$fontName = \"\$fontFamily\$style (TrueType)\"
    } catch {
      \$fontName = [System.IO.Path]::GetFileNameWithoutExtension(\$fontFileName) + ' (TrueType)'
    }

    # Register in user fonts registry
    \$regPath = 'HKCU:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Fonts'
    Set-ItemProperty -Path \$regPath -Name \$fontName -Value \$destPath

    Write-Host \"OK: \$fontFileName\"
  " </dev/null 2>&1
}

# Process all arguments as font files
for font_file in "$@"; do
  install_font "$font_file"
done
