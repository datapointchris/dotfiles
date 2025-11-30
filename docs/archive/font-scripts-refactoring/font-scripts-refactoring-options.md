# Font Scripts Refactoring Options Analysis

## Option 1: Move Font List to packages.yml

### Current packages.yml Structure
```yaml
system_packages:
  brew: [simple list]
  apt: [simple list]

github_binaries:
  fzf:
    repo: junegunn/fzf
    min_version: "0.50"
```

### What Fonts Would Require
```yaml
fonts:
  # Simple case (Nerd Fonts)
  jetbrains:
    source: nerd_fonts
    package: JetBrainsMono
    dir: JetBrainsMono
    extension: ttf

  # Complex case (GitHub releases with custom logic)
  sgr-iosevka:
    source: github_custom
    repo: be5invis/Iosevka
    variants:
      - pattern: SuperTTC-SGr-Iosevka
        exclude: [Term, Slab]
        dir: SGr-Iosevka
      - pattern: SuperTTC-SGr-IosevkaTerm
        exclude: [Slab]
        dir: SGr-IosevkaTerm
      # ... 2 more variants

  # Another complex case (nested archives)
  victor:
    source: github_nested
    repo: rubjo/victor-mono
    steps:
      - download: zipball/latest
      - extract: public/VictorMonoAll.zip
      - pattern: "*/TTF/*.ttf"
    dir: VictorMono
```

### Analysis

**Pros:**
- ✅ Consistency with other install components
- ✅ Single source of truth for all installed software
- ✅ Declarative configuration
- ✅ Easy to see what's installed without reading bash
- ✅ Could leverage parse-packages.py infrastructure

**Cons:**
- ❌ Fonts have vastly different complexity than brew/apt packages
- ❌ Each font has unique download logic (see download_victor, download_sgr_iosevka)
- ❌ Would need complex nested YAML that's harder to read than bash
- ❌ Loss of bash's flexibility for one-off extraction patterns
- ❌ 23 different download patterns - YAML would be very complex
- ❌ Some fonts require multi-step logic (fetch JSON → parse → download multiple files)

**Verdict: ❌ NOT RECOMMENDED**

**Reasoning:** Unlike brew/apt packages which all install the same way, each font family has unique download/extraction logic. The current bash functions (download_jetbrains, download_victor, etc.) handle this variability well. Moving to YAML would require either:
1. Very complex YAML schemas that are harder to read than bash
2. Generic "steps" approach that's just bash-in-YAML
3. Limited YAML + fallback to bash for complex cases (worst of both worlds)

**Counter-argument:** "But we already have packages.yml!"
- Yes, but fonts ≠ packages. Packages have standard installers (brew, apt). Fonts have 23 different download patterns, archive formats, extraction rules, and post-processing steps.

## Option 2: Move Filtering Rules to packages.yml

### Current Filtering Rules (bash)

**Weight exclusions:**
```bash
ExtraLight, Light, Thin, Medium, SemiBold, ExtraBold, Black, Retina
```

**Spacing exclusions:**
```bash
*NerdFontPropo-*  # Keep only Mono and default
```

**Font exclusions:**
```bash
EXCLUDED_FONTS=(
  "IosevkaTermSlab"
)
```

### Potential YAML Structure
```yaml
font_filters:
  weights:
    exclude: [ExtraLight, Light, Thin, Medium, SemiBold, ExtraBold, Black, Retina]
    keep: [Regular, Bold, Italic, BoldItalic]

  spacing:
    exclude: [NerdFontPropo]
    keep: [NerdFontMono, default]

  excluded_fonts:
    - IosevkaTermSlab

  # Optional: Per-family overrides
  family_overrides:
    victor:
      weights:
        exclude: [Light]  # Less restrictive for Victor Mono
```

### Analysis

**Pros:**
- ✅ Easy to modify without editing bash
- ✅ Could support per-family overrides
- ✅ Declarative configuration

**Cons:**
- ❌ Filtering logic is universal (same weights for all fonts)
- ❌ Current exclusion list has 1 item - not worth YAML overhead
- ❌ Pattern matching (`find -iname "*Medium*"`) is better in bash
- ❌ Would need Python to read YAML and generate find patterns

**Verdict: ⚠️ NEUTRAL / SLIGHT NO**

**Reasoning:** The filtering rules are simple and universal. Moving to YAML adds complexity without much benefit. The current bash implementation with find commands is clear and efficient.

**Exception:** If we add per-family filter overrides, YAML makes more sense.

## Option 3: Switch to Python

### Current Size
- download.sh: 941 lines
- install.sh: 350 lines
- **Total: 1,291 lines**

### Why Scripts Are Large
1. **23 download functions** (one per font family) - ~500 lines
2. **Comprehensive help text** - ~100 lines
3. **Logging/progress output** - ~100 lines
4. **Pruning logic** - ~100 lines
5. **Multiple operation modes** - ~100 lines
6. **Platform-specific logic** - ~50 lines

### Would Python Reduce Size?

**No, because the verbosity comes from:**
- 23 different fonts with unique download logic
- Comprehensive help/documentation
- Multiple operation modes
- Detailed logging

**Python wouldn't eliminate:**
```python
def download_sgr_iosevka():
    """Still need unique logic for 4 variants with JSON parsing"""
    release = requests.get("https://api.github.com/repos/be5invis/Iosevka/releases/latest").json()
    # Parse download URLs for 4 different variants
    # Download each one
    # Extract to different directories
    # Still ~30 lines of unique logic

def download_victor():
    """Still need unique nested extraction logic"""
    # Download source zipball
    # Extract outer zip
    # Find VictorMonoAll.zip inside
    # Extract inner zip
    # Move TTF files from TTF/ subdirectory
    # Still ~25 lines of unique logic
```

### Language Strengths Comparison

**Bash Strengths in These Scripts:**
- ✅ File operations: `find`, `cp`, `mv`, `mkdir`
- ✅ Archive extraction: `tar -xf`, `unzip -qo`
- ✅ Downloads: `curl -fsSL`
- ✅ Platform detection: `$OSTYPE`, `/proc/version`
- ✅ Font cache: `fc-cache -f`
- ✅ Running external commands (no subprocess overhead)

**Python Strengths:**
- ✅ JSON parsing (GitHub API) - but bash + jq works fine
- ✅ Data structures (dicts vs bash arrays)
- ✅ String manipulation - but bash is adequate here
- ✅ Error handling - bash `set -euo pipefail` works well
- ✅ Testing - but these scripts are primarily integration code

**What Python Would Look Like:**
```python
import subprocess
import requests
import shutil
from pathlib import Path

def download_jetbrains():
    """Still need to shell out for tar, curl, etc."""
    subprocess.run(["curl", "-fsSL", url, "-o", "file.tar.xz"])
    subprocess.run(["tar", "-xf", "file.tar.xz"])
    subprocess.run(["mv", "*.ttf", target_dir])
    # Lost bash's native strength for file operations
```

### Analysis

**Pros of Python:**
- ✅ Better for complex data structures
- ✅ More familiar to many developers
- ✅ Better testing frameworks
- ✅ Libraries like requests, pathlib

**Cons of Python:**
- ❌ Would still call bash commands via subprocess (curl, tar, unzip)
- ❌ Lost native file operation strength
- ❌ Size wouldn't decrease much (23 functions still needed)
- ❌ Additional dependency (Python already required, but still)
- ❌ Bash is the right tool for file/archive/download operations

**Verdict: ❌ NOT RECOMMENDED**

**Reasoning:** The scripts are large because the problem domain is complex (23 fonts with unique download logic), not because bash is verbose. Python would:
1. Still need subprocess calls for curl, tar, unzip
2. Still need 23 different download functions
3. Still need all the help text, logging, and mode control
4. Lose bash's native strengths for file operations

**After refactoring:** Scripts will likely be ~800-900 lines even in Python. The complexity is inherent to the problem, not the language.

## Option 4: Merge into Single Script

### Current Structure
```
download.sh (941 lines)
├── Phase 1: Download
├── Phase 2: Prune
├── Phase 3: Standardize
└── Modes: --download-only, --prune-only, --standardize-only

install.sh (350 lines)
└── Phase 4: Install to system
    └── Modes: --dry-run, --force, --family
```

### Proposed Merged Structure
```
fonts.sh (~1,000-1,100 lines after dedup)
├── Phase 1: Download
├── Phase 2: Prune
├── Phase 3: Standardize
├── Phase 4: Install
└── Modes:
    --download-only
    --prune-only
    --standardize-only
    --install-only
    --skip-install  (download + prune + standardize)
    --full          (all phases)
```

### Analysis

**Pros:**
- ✅ Eliminates ALL cross-script duplication
- ✅ Single source of truth
- ✅ Clearer workflow (one tool, multiple phases)
- ✅ Already have phase control pattern in download.sh
- ✅ Easier to maintain (one file)
- ✅ Natural progression: download → prune → standardize → install

**Cons:**
- ❌ Larger single file (~1,000-1,100 lines)
- ⚠️ Less separation of concerns (but phases already separate)
- ⚠️ Users who only want download need to know flags (but already true)

**Verdict: ✅ STRONGLY RECOMMENDED**

**Reasoning:**
1. Scripts are tightly coupled (install.sh depends on download.sh output)
2. Workflow is sequential: download → prune → standardize → install
3. Already have phase control in download.sh
4. Eliminates duplication (count_fonts, platform detection, etc.)
5. Simpler mental model: one tool with multiple phases vs two related tools

**Implementation:**
- Start with download.sh as base (has most logic)
- Add Phase 4 (install) from install.sh
- Add mode flags: --install-only, --skip-install, --full
- Update help text
- Remove install.sh

## Updated Recommendations

### Recommended Approach

**Phase 1: Refactor in Bash (Keep Separate Scripts)**
1. ✅ Update usage documentation (reflect actual paths)
2. ✅ Create `font-helpers.sh` library
3. ✅ Use existing `platform-detection.sh`
4. ✅ Consolidate family mappings
5. ✅ Extract GitHub API helper
6. ✅ Unify installation logic

**Estimated result:** ~1,100 lines total (200 line reduction)

**Phase 2: Merge Scripts**
1. ✅ Merge download.sh + install.sh → fonts.sh
2. ✅ Add --install-only, --skip-install modes
3. ✅ Update install.sh to call: `bash fonts.sh --full`

**Estimated result:** ~900-1,000 lines (eliminate duplication)

**Phase 3: Move Exclusion to Download**
1. ✅ Check EXCLUDED_FONTS during download phase
2. ✅ Skip downloading fonts that won't be installed
3. ✅ Save bandwidth/time

### NOT Recommended

❌ **Move font list to packages.yml**
- Problem domain too complex for YAML
- Each font has unique download/extract logic
- Would require complex nested YAML or "bash-in-YAML"

❌ **Switch to Python**
- Size reduction would be minimal (~10-15%)
- Would lose bash's native strength for file/archive operations
- Complexity is in the problem domain (23 fonts), not the language
- Still need subprocess calls for curl, tar, unzip

⚠️ **Move filtering rules to YAML**
- Minor benefit, not worth the complexity
- Current bash find patterns are clear and efficient
- Only consider if adding per-family filter overrides

## Final Recommendation

**Incremental path:**

```
1. Refactor both scripts (bash, separate) → ~1,100 lines
   ├── Create font-helpers.sh
   ├── Use platform-detection.sh
   ├── Consolidate mappings
   └── Extract helpers

2. Merge into fonts.sh → ~900-1,000 lines
   ├── All phases in one script
   ├── Phase control via flags
   └── Update install.sh caller

3. Move exclusions to download phase → bandwidth savings
   └── Skip downloading excluded fonts
```

**Why this order:**
- Step 1 reduces duplication, improves code quality
- Step 2 eliminates cross-script duplication
- Step 3 optimizes bandwidth
- Each step is independently valuable
- Can stop at any point

**Why NOT YAML/Python:**
- YAML: Problem too complex, each font is unique
- Python: No significant size reduction, lose bash strengths
- Bash is the right tool for file/archive/download operations

**Estimated final size:** ~900 lines (30% reduction from current 1,291)
- Still large, but complexity is inherent (23 fonts × unique logic each)
- Well-structured with clear phases and helpers
- Single tool with comprehensive mode control
