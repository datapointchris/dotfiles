#!/usr/bin/env bats
# shellcheck disable=SC2317
# ================================================================
# Unit tests for create-bundle.sh: the cross-build download cache
# ================================================================
# The cache is keyed on the asset URL, which names the asset's version, so a
# hit is only ever the same bytes. These tests pin the three behaviours that
# make that safe to rely on: a moved release misses, a corrupted entry is
# re-fetched rather than shipped, and a URL cannot write outside the cache root.
#
# file:// URLs stand in for releases — curl fetches them the same way, so the
# whole round trip runs with no network and no GitHub rate limit.
# ================================================================

load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

setup_file() {
  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
}

setup() {
  TEST_DIR=$(mktemp -d)
  UPSTREAM_DIR="$TEST_DIR/upstream"
  mkdir -p "$UPSTREAM_DIR"
  export TEST_DIR UPSTREAM_DIR
}

teardown() {
  rm -rf "$TEST_DIR"
}

# ================================================================
# Fixture helpers
# ================================================================

# A release asset at a version-bearing URL, as create-bundle.sh sees one.
publish_asset() {
  local version="$1" contents="$2"
  mkdir -p "$UPSTREAM_DIR/$version"
  printf '%s' "$contents" >"$UPSTREAM_DIR/$version/tool.tar.gz"
  echo "file://$UPSTREAM_DIR/$version/tool.tar.gz"
}

# Run a scenario inside one shell so the download and hit counters, which are
# process state, are observable across several calls.
run_scenario() {
  local body="$1"
  local script="$TEST_DIR/scenario.sh"

  cat >"$script" <<SCRIPT
#!/usr/bin/env bash
set -euo pipefail
export DOTFILES_DIR="$DOTFILES_DIR"
source "\$DOTFILES_DIR/install/offline/create-bundle.sh"
DOWNLOAD_CACHE_DIR="$TEST_DIR/cache"
TEST_DIR="$TEST_DIR"
$body
SCRIPT

  bash "$script"
}

# ================================================================
# Tests
# ================================================================

@test "cache/miss-then-hit: a second build for the same URL downloads nothing" {
  local url
  url=$(publish_asset v1 "PAYLOAD-V1")

  run run_scenario "
    download_versioned_file '$url' \"\$TEST_DIR/first\" tool
    download_versioned_file '$url' \"\$TEST_DIR/second\" tool
    echo \"downloads=\$TOTAL_DOWNLOADS hits=\$CACHE_HITS\"
    cat \"\$TEST_DIR/second\"
  "
  assert_success
  assert_line "downloads=1 hits=1"
  assert_line "PAYLOAD-V1"
}

@test "cache/reporting: the progress line says which builds came from cache" {
  local url
  url=$(publish_asset v1 "PAYLOAD-V1")

  run run_scenario "
    download_versioned_file '$url' \"\$TEST_DIR/first\" tool '  tool (v1)'
    download_versioned_file '$url' \"\$TEST_DIR/second\" tool '  tool (v1)'
  "
  assert_success
  # Exactly one of the two builds hit, so exactly one line carries the marker —
  # a warm build that reads identically to a cold one is how a working cache
  # gets reported as broken.
  [[ "$(grep -c '\[cached\]' <<<"$output")" -eq 1 ]]
}

@test "cache/new-version: a released version changes the URL and misses" {
  local old new
  old=$(publish_asset v1 "PAYLOAD-V1")
  new=$(publish_asset v2 "PAYLOAD-V2")

  run run_scenario "
    download_versioned_file '$old' \"\$TEST_DIR/old\" tool
    download_versioned_file '$new' \"\$TEST_DIR/new\" tool
    echo \"downloads=\$TOTAL_DOWNLOADS hits=\$CACHE_HITS\"
    cat \"\$TEST_DIR/new\"
  "
  assert_success
  assert_line "downloads=2 hits=0"
  assert_line "PAYLOAD-V2"
}

@test "cache/corrupt: a tampered entry is re-downloaded, not shipped" {
  local url
  url=$(publish_asset v1 "PAYLOAD-V1")

  run run_scenario "
    download_versioned_file '$url' \"\$TEST_DIR/first\" tool
    printf 'TAMPERED' >\"\$(download_cache_path '$url')\"
    download_versioned_file '$url' \"\$TEST_DIR/second\" tool
    echo \"downloads=\$TOTAL_DOWNLOADS hits=\$CACHE_HITS\"
    cat \"\$TEST_DIR/second\"
  "
  assert_success
  assert_line "downloads=2 hits=0"
  assert_line "PAYLOAD-V1"
  refute_line "TAMPERED"
}

@test "cache/no-cache: --no-cache re-downloads and leaves no entry behind" {
  local url
  url=$(publish_asset v1 "PAYLOAD-V1")

  run run_scenario "
    USE_DOWNLOAD_CACHE=false
    download_versioned_file '$url' \"\$TEST_DIR/first\" tool
    download_versioned_file '$url' \"\$TEST_DIR/second\" tool
    echo \"downloads=\$TOTAL_DOWNLOADS hits=\$CACHE_HITS\"
    [[ -f \"\$(download_cache_path '$url')\" ]] && echo 'cached' || echo 'not-cached'
  "
  assert_success
  assert_line "downloads=2 hits=0"
  assert_line "not-cached"
}

@test "cache/key: traversal and query segments cannot escape the cache root" {
  run run_scenario "
    download_cache_path 'https://example.com/../../etc/passwd?a=b'
  "
  assert_success
  assert_output "$TEST_DIR/cache/example.com/__/__/etc/passwd_a_b"
}

@test "cache/prune: entries older than the retention window are swept" {
  local url
  url=$(publish_asset v1 "PAYLOAD-V1")

  run run_scenario "
    download_versioned_file '$url' \"\$TEST_DIR/first\" tool
    find \"\$DOWNLOAD_CACHE_DIR\" -type f -exec touch -d '400 days ago' {} +
    prune_download_cache
    [[ -f \"\$(download_cache_path '$url')\" ]] && echo 'kept' || echo 'pruned'
  "
  assert_success
  assert_line "pruned"
}

@test "cache/prune: an entry used by this build survives the sweep" {
  local url
  url=$(publish_asset v1 "PAYLOAD-V1")

  run run_scenario "
    download_versioned_file '$url' \"\$TEST_DIR/first\" tool
    find \"\$DOWNLOAD_CACHE_DIR\" -type f -exec touch -d '400 days ago' {} +
    download_versioned_file '$url' \"\$TEST_DIR/second\" tool
    prune_download_cache
    [[ -f \"\$(download_cache_path '$url')\" ]] && echo 'kept' || echo 'pruned'
  "
  assert_success
  assert_line "kept"
}
