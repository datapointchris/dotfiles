# Font Comparison

Detailed comparison of fonts in your code_fonts collection, helping choose which to test and keep.

## Your Font Collection

You have approximately **20 font families** in `~/Documents/code_fonts/`. This guide compares their characteristics, strengths, and ideal use cases.

## Quick Reference Table

| Font | Width | Ligatures | Best For | Character | Priority |
|------|-------|-----------|----------|-----------|----------|
| **FiraCode** | Normal | ★★★ Extensive | Modern code, JS/Python | Professional | High |
| **JetBrains Mono** | Normal | ★★ Good | Long sessions, clarity | Clean | High |
| **Iosevka** | Narrow | ★★ Optional | Dense code, small screens | Technical | High |
| **Source Code Pro** | Normal | ★ Optional | Professional work, Adobe | Classic | High |
| **Meslo** | Normal | ✗ None | Terminal work, macOS feel | Reliable | Medium |
| **CommitMono** | Normal | ★★ Good | Modern, neutral | Contemporary | Medium |
| **SeriousShanns** | Normal | ✗ None | Fun, daily use | Comic Sans | High* |
| **ComicMono** | Normal | ✗ None | Comic Sans style | Casual | Low |
| **Terminess** | Normal | ✗ None | Retro, bitmap feel | Classic | Low |
| **DroidSans** | Normal | ✗ None | Android dev | Neutral | Low |

*High because you already like it

## Detailed Comparisons

### Tier 1: Industry Standards (Test These First)

These fonts are battle-tested by millions of developers worldwide.

#### FiraCode Nerd Font

**Origin**: Extension of Mozilla's Fira Mono (2014)
**Designer**: Nikita Prokopov

**Characteristics**:

- **Ligatures**: Extensive, comprehensive coverage
- **Width**: Standard monospace
- **Weight options**: 7 weights (Light to Bold)
- **Character**: Modern, professional, friendly

**Strengths**:

- **Leading ligature support** - Combines `=>`, `!=`, `===`, `->` elegantly
- Clear character differentiation (0O, 1lI)
- Excellent at medium sizes (13-16pt)
- Works everywhere, universally compatible

**Trade-offs**:

- Ligatures can distract some people
- Slightly wider than some alternatives
- Can feel "busy" with lots of operators

**Best for**:

- JavaScript, Python, Rust (operator-heavy languages)
- Modern codebases
- Developers who love ligatures
- 4K/HiDPI displays

**When to skip**:

- You dislike ligatures
- Need maximum code density
- Prefer minimalist aesthetics

**Testing priority**: ⭐⭐⭐⭐⭐ Test first or second

**Similar fonts**: JetBrains Mono, Cascadia Code

---

#### JetBrains Mono Nerd Font

**Origin**: Created by JetBrains (2020)
**Designer**: Philipp Nurullin, Konstantin Bulenkov

**Characteristics**:

- **Ligatures**: Good coverage, conservative
- **Width**: Standard monospace
- **Weight options**: 8 weights
- **Character**: Clean, ergonomic, optimized

**Strengths**:

- **Designed for extended coding** - Less eye strain
- Increased character height
- Excellent character differentiation
- Slightly wider letter spacing
- True Italics optimized for code

**Trade-offs**:

- Less horizontal density than narrow fonts
- Some find it too "plain"
- Ligatures less comprehensive than FiraCode

**Best for**:

- Long coding sessions (6+ hours)
- Reducing eye fatigue
- Professional, clean aesthetics
- IntelliJ/JetBrains IDE users

**When to skip**:

- Want more personality
- Need maximum density
- Prefer extensive ligatures

**Testing priority**: ⭐⭐⭐⭐⭐ Test first or second

**Similar fonts**: Source Code Pro, Inter Mono

---

#### Source Code Pro Nerd Font

**Origin**: Adobe (2012)
**Designer**: Paul D. Hunt

**Characteristics**:

- **Ligatures**: Limited/optional
- **Width**: Standard monospace
- **Weight options**: 7 weights (ExtraLight to Black)
- **Character**: Professional, Adobe quality

**Strengths**:

- **Professional and neutral** - Timeless design
- Part of Adobe Source family (Sans, Serif, Code)
- Excellent readability
- True italics, comprehensive weights
- Open source, widely supported

**Trade-offs**:

- Minimal ligature support
- Can feel "corporate" or plain
- Not distinctive

**Best for**:

- Professional environments
- Clean, no-nonsense coding
- Adobe ecosystem users
- Developers who dislike ligatures

**When to skip**:

- Want ligatures
- Prefer modern aesthetics
- Need distinctive character

**Testing priority**: ⭐⭐⭐⭐ Test in first 5

**Similar fonts**: DejaVu Sans Mono, Liberation Mono

---

#### Iosevka Nerd Font

**Origin**: Open source project (2015)
**Designer**: Belleve Invis

**Characteristics**:

- **Ligatures**: Configurable, extensive options
- **Width**: Narrow, condensed
- **Weight options**: 9+ weights
- **Character**: Technical, space-efficient

**Strengths**:

- **Maximum code density** - Fits more on screen
- Highly customizable (143 configurable characters)
- Slashed zero, excellent 0O/1lI distinction
- Multiple stylistic variants (SS01-SS20)
- Very active development

**Trade-offs**:

- Narrow width not for everyone
- Can feel cramped
- Many variants can be overwhelming
- Thin appearance at some weights

**Best for**:

- Small screens, laptops
- Fitting more code horizontally
- Split-pane workflows
- Users who want customization

**When to skip**:

- Prefer wider spacing
- Find narrow fonts hard to read
- Want simple, standard appearance

**Testing priority**: ⭐⭐⭐⭐ Test if you want density

**Similar fonts**: Input Mono Narrow, PragmataPro

**Variants you have**:

- **Iosevka**: Standard narrow monospace
- **IosevkaAile**: Sans-serif, NOT for terminal
- **IosevkaEtoile**: Serif, NOT for terminal
- **SGr-Iosevka**: Stylistic variant

**Recommendation**: Test `Iosevka Nerd Font Mono` first. Ignore Aile and Etoile for terminal use.

---

#### Meslo Nerd Font

**Origin**: Customization of Apple's Menlo (2011)
**Designer**: André Berg

**Characteristics**:

- **Ligatures**: None
- **Width**: Standard monospace
- **Weight options**: Regular, Bold
- **Character**: macOS default feel, familiar

**Strengths**:

- **Based on macOS default** - Familiar to Mac users
- Slightly larger line spacing
- Excellent vertical rhythm
- Clean, no-frills design
- Optimized for terminal use

**Trade-offs**:

- No ligatures
- Limited weight options
- Not distinctive
- Similar to many system fonts

**Best for**:

- macOS users wanting familiar feel
- Terminal-heavy workflows
- tmux and vim users
- Developers who want reliability over features

**When to skip**:

- Want ligatures
- Need lots of weight options
- Want something unique

**Testing priority**: ⭐⭐⭐ Solid choice, test if macOS user

**Similar fonts**: Menlo, Monaco, DejaVu Sans Mono

---

### Tier 2: Modern Alternatives

Newer fonts with specific design philosophies.

#### CommitMono Nerd Font

**Origin**: Modern open source (2023)
**Designer**: Community project

**Characteristics**:

- **Ligatures**: Moderate, tasteful
- **Width**: Standard monospace
- **Weight options**: Regular, Bold, Italic
- **Character**: Contemporary, neutral

**Strengths**:

- Very modern design
- Optimized for Git commit messages
- Clean, minimal aesthetics
- Good balance of features

**Trade-offs**:

- Newer, less battle-tested
- Smaller community
- Limited weight options

**Best for**:

- Modern workflows
- Git-heavy development
- Minimalist preferences
- Trying something new

**When to skip**:

- Want proven track record
- Need extensive weight options

**Testing priority**: ⭐⭐⭐ Try if you like modern fonts

---

### Tier 3: Personality Fonts

Fonts with unique character and style.

#### SeriousShanns Nerd Font

**Origin**: Comic Sans-inspired monospace
**Designer**: Shannon Miwa

**Characteristics**:

- **Ligatures**: None
- **Width**: Standard monospace
- **Weight options**: Light, Regular, Bold
- **Character**: Fun, comic sans style, casual

**Strengths**:

- **Unique personality** - Stands out
- Friendly, approachable aesthetic
- Surprisingly readable
- Makes coding fun
- You already like this!

**Trade-offs**:

- Not professional-looking
- Polarizing design
- May not be taken seriously in screen shares
- Limited ligature support

**Best for**:

- Personal projects
- Solo development
- Developers who hate "serious" fonts
- Making coding feel less sterile

**When to skip**:

- Professional environments
- Screen sharing with colleagues
- Want "serious" aesthetics

**Testing priority**: ⭐⭐⭐⭐⭐ You're already using it!

**Similar fonts**: Comic Mono, Comic Code

---

#### ComicMono

**Origin**: Comic Sans → Monospace conversion
**Designer**: Shannon Miwa

**Characteristics**:

- **Ligatures**: None
- **Width**: Standard monospace
- **Character**: Comic Sans, very casual

**Strengths**:

- True Comic Sans aesthetic
- Friendly and casual
- Fun for side projects

**Trade-offs**:

- Less refined than SeriousShanns
- Very casual, not professional
- Limited font family

**Best for**:

- Fun projects
- Personal use
- If you love Comic Sans

**Testing priority**: ⭐⭐ Only if you want Comic Sans

**Note**: You already have SeriousShanns which is similar but more refined. Probably skip this.

---

### Tier 4: Specialized/Niche

#### Terminess (Terminus) Nerd Font

**Origin**: Based on Terminus bitmap font
**Designer**: Dimitar Zhekov (original Terminus)

**Characteristics**:

- **Ligatures**: None
- **Width**: Standard monospace
- **Weight options**: Limited
- **Character**: Bitmap-style, retro, crisp

**Strengths**:

- Extremely crisp at specific sizes
- Retro aesthetic
- Low resolution optimization
- Very small file size

**Trade-offs**:

- Bitmap origin, can look pixelated when scaled
- Best at specific sizes only
- Limited weights
- Niche appeal

**Best for**:

- Retro setups
- Low-DPI displays
- Specific size preferences
- Nostalgia

**Testing priority**: ⭐ Low, niche use case

---

#### DroidSans Nerd Font

**Origin**: Google Android system font
**Designer**: Steve Matteson

**Characteristics**:

- **Ligatures**: None
- **Width**: Standard monospace
- **Character**: Neutral, Android-like

**Strengths**:

- Familiar to Android developers
- Clean, neutral design
- Part of larger Droid family

**Trade-offs**:

- Not specifically designed for code
- Less distinctive
- Better alternatives exist

**Best for**:

- Android development
- Google ecosystem preference
- Neutral aesthetics

**Testing priority**: ⭐⭐ Low priority

---

## Font Selection Decision Tree

```text
Do you want ligatures?
├─ Yes
│  ├─ Extensive ligatures → FiraCode
│  └─ Moderate ligatures → JetBrains Mono or CommitMono
└─ No
   ├─ Want personality → SeriousShanns (you have this!)
   ├─ Want density → Iosevka
   ├─ Want classic → Source Code Pro or Meslo
   └─ Want retro → Terminess
```

## Ligature Comparison

### Extensive Ligatures (FiraCode)

```text
->  →    =>  ⇒    !=  ≠    ==  ═    ===  ≡
>=  ≥    <=  ≤    ||  ‖    &&  ＆   ::  ∷
```

### Moderate Ligatures (JetBrains Mono)

```text
->  →    =>  ⇒    !=  ≠    ==  ═
>=  ≥    <=  ≤    ::  ∷
```

### No Ligatures (Source Code Pro, Meslo, SeriousShanns)

```text
-> -> => => != != == == === ===
(Characters stay separate)
```

## Width Comparison

At same font size (14pt):

**Narrow** (Iosevka):

```text
const myFunction = () => { return value; }  // 80 chars
```

**Standard** (FiraCode, JetBrains, Source):

```text
const myFunction = () => { return value; }  // 80 chars (wider)
```

**Impact**: Narrow fonts fit ~10-15% more code horizontally.

## Character Differentiation Test

Critical characters that must be distinguishable:

```text
0O  (zero vs capital O)
1lI (one vs lowercase L vs capital i)
`'  (backtick vs quote)
-–— (hyphen vs en dash vs em dash)
,;  (comma vs semicolon)
```

**All fonts in your collection** handle this well. Specifically optimized for code.

## Recommended Testing Order

Based on popularity, features, and your preferences:

### Week 1-5: The Essential Five

1. **JetBrains Mono** - Modern, ergonomic, ligatures
2. **FiraCode** - If Week 1 feels good but want more ligatures
3. **Source Code Pro** - If you want no-nonsense, professional
4. **Iosevka** - If you want maximum density
5. **Meslo** - macOS familiarity

### Week 6-8: The Alternatives

1. **CommitMono** - Modern alternative
2. **SeriousShanns** (re-test your current favorite)
3. **Any wildcard** that caught your eye

### Skip Unless Curious

- ComicMono (you have SeriousShanns)
- Terminess (niche retro use)
- DroidSans (better options exist)
- IosevkaAile/Etoile (not for terminal)

## Font Pairing Recommendations

If you end up keeping 3-5 fonts, good combinations:

**Balanced Trio**:

- **Daily**: SeriousShanns (fun, your favorite)
- **Professional**: Source Code Pro (screen sharing, work)
- **Dense**: Iosevka (small screen, lots of code)

**Ligature Lover Trio**:

- **Main**: FiraCode (extensive ligatures)
- **Alternative**: JetBrains Mono (when FiraCode feels busy)
- **Fun**: SeriousShanns (personal projects)

**Minimalist Duo**:

- **Main**: JetBrains Mono (all-around excellent)
- **Backup**: Source Code Pro (alternative feel)

**Maximum Variety**:

- **Modern ligatures**: FiraCode
- **Clean professional**: JetBrains Mono
- **Classic**: Source Code Pro
- **Personality**: SeriousShanns
- **Density**: Iosevka

(Five fonts max - don't exceed this!)

## Font Sizes by Screen

### 13" Laptop (1440p)

- **12-13pt**: Iosevka (narrow, fits more)
- **13-14pt**: FiraCode, JetBrains, Source
- **14-15pt**: SeriousShanns, Meslo

### 15" Laptop (1080p)

- **13-14pt**: Most fonts
- **14-15pt**: Comfortable for long sessions

### 27" 4K Monitor

- **14-16pt**: Standard
- **16-18pt**: If far from screen

### General Rule

- Start at 14pt
- Adjust ±1-2pt based on comfort
- Bigger = less eye strain, less code visible
- Smaller = more code, more eye strain

## Common Questions

### Which font is "best"?

There isn't one. Depends on:

- Your vision
- Screen size and resolution
- Language you code in
- Personal aesthetic preference
- Ligature preference

**Best approach**: Test 5-10, pick favorite.

### How long to test each?

**Minimum**: 3 days of real work
**Recommended**: 1 week
**Ideal**: 2 weeks

### What if I like multiple fonts?

**Keep 3-5 max**:

- Main daily driver (80% of time)
- Professional alternative (for work/screen sharing)
- Fun option (personal projects)
- Optional: specialty (dense code, specific use)

### Do I need all font weights?

**No.** For each font family:

- Keep: Regular, Bold, Italic, Bold Italic
- Skip: Light, Medium, SemiBold, ExtraBold, Black

See [Font Weights Guide](font-weights-and-variants.md) for details.

### What about Iosevka variants?

**For terminal/coding**:

- Use: `Iosevka Nerd Font` or `Iosevka Nerd Font Mono`
- Skip: IosevkaAile (sans-serif, not monospace)
- Skip: IosevkaEtoile (serif, not monospace)
- Maybe: SGr variants (stylistic alternatives)

## After Testing: Cleanup

Once you've found your favorites (3-5 fonts):

### Keep

```text
~/Documents/code_fonts/
├── FiraCode*.otf (if you liked it)
├── JetBrains*.ttf (if you liked it)
├── SeriousShanns*.otf (you like this!)
└── (2-3 more you actually use)
```

### Delete

Everything marked "dislike" in your font-sync log.

### Archive

Fonts you're unsure about, save for 6 months then delete.

## Summary Tables

### By Use Case

| Use Case | Top Choice | Alternative |
|----------|------------|-------------|
| Ligatures | FiraCode | JetBrains Mono |
| No ligatures | Source Code Pro | Meslo |
| Maximum density | Iosevka | - |
| Long sessions | JetBrains Mono | Source Code Pro |
| Personality | SeriousShanns | ComicMono |
| Professional | Source Code Pro | JetBrains Mono |
| Modern | CommitMono | FiraCode |

### By Priority

| Priority | Fonts | Why |
|----------|-------|-----|
| Must Test | FiraCode, JetBrains, Source Code Pro | Industry standards, proven |
| Should Test | Iosevka, Meslo | Excellent, specific strengths |
| Optional | CommitMono | Newer, interesting |
| Keep | SeriousShanns | You already like it! |
| Skip | ComicMono, Terminess, DroidSans | Better alternatives exist |

---

**Next Steps**:

1. Use `font-sync adventure` to try a random font
2. Or `font-sync preview` to choose interactively
3. Test for a week with `font-sync test`
4. Log your decision with `font-sync like` or `font-sync dislike`
5. Repeat until you've found your 3-5 favorites

## Related Documentation

- [Nerd Fonts Explained](nerd-fonts-explained.md) - Understanding Nerd Font variants
- [Font Weights and Variants](font-weights-and-variants.md) - When to use Bold, Italic
- [Terminal Fonts Guide](terminal-fonts-guide.md) - Why monospace matters
