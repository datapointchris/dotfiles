# Homebrew Cleanup Analysis - Post Migration

**Date:** 2025-11-28
**Purpose:** Identify brew packages that can be safely uninstalled after migration to packages.yml

---

## Analysis Results

### Packages to UNINSTALL

#### 1. **borders** - Window border highlighter (macOS)

**Reason:** User confirmed not using this tool
**Action:** `brew uninstall borders`

#### 2. **deno** - JavaScript/TypeScript runtime

**Reason:** Not in packages.yml, likely experimental install
**Status:** Check if actively used
**Action:** `brew uninstall deno` (if not needed)

#### 3. **iterm2** (cask)

**Reason:** Not in packages.yml casks list
**Likely replaced by:** Ghostty or another terminal
**Action:** `brew uninstall --cask iterm2` (if confirmed not using)

#### 4. **qutebrowser** (cask)

**Reason:** Not in packages.yml casks list
**Status:** Check if actively used
**Action:** `brew uninstall --cask qutebrowser` (if not needed)

---

### Packages to KEEP (Dependencies)

These are brew-installed but not explicitly in packages.yml because they're dependencies:

#### Python-related (dependencies of other tools)

- `python@3.13`, `python@3.14` - Required by other brew packages
- `python-certifi`, `mpdecimal`, `certifi` - Python dependencies

#### FFmpeg/MPV dependencies (required by mpv)

All the following are dependencies of `mpv` and `ffmpeg`:

- `aom`, `aribb24`, `brotli`, `dav1d`, `ffmpeg`, `flac`, `frei0r`
- `lame`, `libass`, `libbluray`, `libvorbis`, `libvpx`, `opus`
- `rav1e`, `rtmpdump`, `rubberband`, `sdl2`, `sdl2_image`, `snappy`
- `speex`, `srt`, `svt-av1`, `theora`, `vapoursynth`, `x264`, `x265`, `xvid`
- `opencore-amr`, `librist`, `libsamplerate`, `libsndfile`, `libsoxr`
- `libvidstab`, `libvmaf`

#### ImageMagick dependencies (required by imagemagick)

- `jpeg-turbo`, `jpeg-xl`, `libheif`, `libraw`, `libtiff`, `libpng`
- `giflib`, `webp`, `openjpeg`, `openjph`, `openexr`, `imath`
- `little-cms2`, `fontconfig`, `freetype`, `cairo`, `pango`
- `gdk-pixbuf`, `librsvg`, `graphite2`, `harfbuzz`, `highway`
- `jasper`, `leptonica`, `liblqr`, `netpbm`

#### System libraries (dependencies of various tools)

- `ca-certificates`, `curl`, `openssl@3` - TLS/SSL
- `ncurses`, `readline` - Terminal libraries
- `gettext`, `libiconv` - Internationalization
- `pcre2`, `oniguruma` - Regex libraries
- `xz`, `zstd`, `lz4`, `lzo`, `brotli` - Compression
- `sqlite`, `libyaml` - Data storage
- `libevent`, `libssh2`, `libnghttp2`, `libnghttp3`, `libngtcp2` - Networking
- `libarchive`, `libzip`, `sevenzip` - Archive handling

#### Graphics/rendering libraries

- `libx11`, `libxau`, `libxcb`, `libxdmcp`, `libxext`, `libxrender`, `xorgproto` - X11
- `pixman`, `gd` - Graphics
- `vulkan-headers`, `vulkan-loader`, `molten-vk`, `shaderc` - Vulkan (for mpv)

#### Colima/Docker dependencies

- `lima` - Required by colima
- `libusb`, `zeromq` - System libraries

#### GnuPG dependencies

- `libgpg-error`, `libgcrypt`, `libassuan`, `libksba`, `npth`, `pinentry` - GPG libraries
- `gnutls`, `nettle`, `libtasn1`, `p11-kit`, `unbound` - Crypto libraries
- `nspr`, `nss` - Network Security Services

#### Other dependencies

- `glib`, `gmp` - Core libraries
- `icu4c@77`, `icu4c@78` - Unicode/internationalization
- `boost` - C++ libraries
- `shared-mime-info` - MIME type handling
- `libtool`, `m4`, `pkgconf` - Build tools (kept for lua/luarocks)
- `mujs` - JavaScript engine (for imagemagick PDF support)
- `tesseract` - OCR library (for imagemagick)
- `cjson` - JSON library (for lua)
- `uchardet`, `libunistring`, `libunibreak` - Character encoding
- `libsodium`, `libmicrohttpd`, `libb2`, `mbedtls`, `mbedtls@3` - Crypto/network
- `libomp` - OpenMP (parallel processing)
- `liblinear` - Machine learning library
- `libde265`, `libavif`, `libdeflate` - Image codecs
- `libogg` - Audio container
- `libplacebo` - Video processing
- `libudfread` - UDF filesystem

#### yt-dlp

**Status:** User confirmed it's a dependency
**Keep:** Yes, installed by brew as dependency of mpv

---

### Verification Commands

#### Check what depends on a package

```bash
brew uses --installed <package>
```

#### Check if Python is needed

```bash
brew uses --installed python@3.13
brew uses --installed python@3.14
```

#### Check iterm2 usage

```bash
# If you're using Ghostty or another terminal, safe to remove
ps aux | grep -i iterm
```

#### Check qutebrowser usage

```bash
# If you're not using this browser, safe to remove
ps aux | grep -i qutebrowser
```

#### Check deno usage

```bash
# If not actively developing with deno
which deno
deno --version
```

---

## Recommended Cleanup Commands

### Safe to Remove Immediately

```bash
# borders - User confirmed not using
brew uninstall borders
```

### Investigate Before Removing

```bash
# Check dependencies first
brew uses --installed deno
brew uses --installed python@3.13
brew uses --installed python@3.14

# If deno has no dependents and you're not using it:
brew uninstall deno

# Check if iterm2 is being used (if you switched to Ghostty)
brew uninstall --cask iterm2  # Only if confirmed not using

# Check if qutebrowser is being used
brew uninstall --cask qutebrowser  # Only if confirmed not using
```

### Python Cleanup (Advanced)

If Python versions are only kept by brew and not required:

```bash
# Check what needs each Python version
brew uses --installed python@3.13
brew uses --installed python@3.14

# If only one package needs it, consider if that package is essential
# Example: If only neovim needs it, and you have uv-managed Python, might be safe
```

---

## Summary

### ✅ REMOVED (Completed 2025-11-28)

- **borders** - Uninstalled (user not using)
- **iterm2** - Uninstalled (switched to different terminal)
- **qutebrowser** - Uninstalled (not using)

### ❌ CANNOT Remove

- **deno** - Required dependency of yt-dlp (discovered during uninstall attempt)

### Keep (All others)

- All packages in packages.yml (system_packages with brew)
- All casks in packages.yml (macos-casks)
- All dependency packages (verified via `brew uses`)
- **yt-dlp** (dependency of mpv/ffmpeg)
- **deno** (dependency of yt-dlp)
- **python@3.13/3.14** - Dependencies of brew packages (user confirmed these versions are fine)

---

## Post-Cleanup Verification

After removing packages:

```bash
# Verify no broken dependencies
brew doctor

# List remaining formulas
brew list --formula

# List remaining casks
brew list --cask

# Compare with packages.yml expectations
task macos:verify-installs
```

---

## Migration Status

✅ **borders** - Ready to remove
⚠️ **deno** - User decision needed
⚠️ **iterm2** - User decision needed
⚠️ **qutebrowser** - User decision needed
✅ All other packages - Keep (in packages.yml or dependencies)
