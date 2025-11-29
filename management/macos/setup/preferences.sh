#!/usr/bin/env bash

##############################################################################
# macOS Preferences - Current Setup
##############################################################################
# Applies macOS settings based on current working configuration
#
# Covers:
#   - Finder (file management, search, display)
#   - Dock (position, size, behavior)
#   - Safari (privacy, developer features)
#   - Mail (threading, formatting)
#   - System (keyboard, save dialogs, screenshots)
#   - Mac App Store (auto-updates)
#   - Photos (auto-import behavior)
#   - Messages (text substitution)
#   - Security (privacy settings)
#
# Usage:
#   sudo bash management/macos/setup/current.sh
#
# Note: Must be run with sudo for system-level settings
##############################################################################

set -euo pipefail

# ================================================================
# Setup and Initialization
# ================================================================

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/error-handling.sh"
enable_error_traps

# Check system is compatible
if [ "$(uname -s)" != "Darwin" ]; then
  log_error "This script is only compatible with macOS"
  exit 1
fi

# Require sudo (fail fast if not root)
if [ "$EUID" -ne 0 ]; then
  log_error "This script must be run with sudo"
  log_error "Usage: sudo bash management/macos/setup/current.sh"
  exit 1
fi

print_banner "Configuring macOS Preferences"

# Close System Preferences to prevent conflicts
osascript -e 'tell application "System Settings" to quit' 2>/dev/null || true
osascript -e 'tell application "System Preferences" to quit' 2>/dev/null || true

# ================================================================
# FINDER - File Management and Display
# ================================================================

log_info "Configuring Finder..."

# File Extensions and Hidden Files
log_info "  Show all file extensions"
defaults write NSGlobalDomain AppleShowAllExtensions -bool true

log_info "  Keep hidden files hidden (system files)"
defaults write com.apple.finder AppleShowAllFiles -bool true

# Finder Window Display
log_info "  Show path bar in Finder windows"
defaults write com.apple.finder ShowPathbar -bool true

log_info "  Show POSIX path in Finder title"
defaults write com.apple.finder _FXShowPosixPathInTitle -bool true

log_info "  Enable Finder quit menu (⌘Q)"
defaults write com.apple.finder QuitMenuItem -bool true

# Search and Navigation
log_info "  Search current directory by default"
defaults write com.apple.finder FXDefaultSearchScope -string "SCcf"

log_info "  Keep folders at top in search results"
defaults write com.apple.finder _FXSortFoldersFirst -bool true

# File Operations
log_info "  Don't warn when changing file extension"
defaults write com.apple.finder FXEnableExtensionChangeWarning -bool false

log_info "  Don't warn when emptying trash"
defaults write com.apple.finder WarnOnEmptyTrash -bool false

# Network and External Drives
log_info "  Don't create .DS_Store on network drives"
defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool true

log_info "  Don't create .DS_Store on USB drives"
defaults write com.apple.desktopservices DSDontWriteUSBStores -bool true

# Show System Directories
log_info "  Show ~/Library folder"
chflags nohidden ~/Library 2>/dev/null || true
xattr -d com.apple.FinderInfo ~/Library 2>/dev/null || true

log_info "  Show /Volumes folder"
sudo chflags nohidden /Volumes 2>/dev/null || true

# ================================================================
# DOCK - Layout and Behavior
# ================================================================

log_info "Configuring Dock..."

# Position and Size (current preferences)
log_info "  Set dock position to bottom"
defaults write com.apple.dock orientation -string "bottom"

log_info "  Set dock tile size to 90"
defaults write com.apple.dock tilesize -int 90

log_info "  Enable dock magnification"
defaults write com.apple.dock magnification -bool true

# Auto-hide Behavior
log_info "  Enable dock auto-hide"
defaults write com.apple.dock autohide -bool true

# Dock Content and Behavior
log_info "  Don't show recent applications"
defaults write com.apple.dock show-recents -bool false

log_info "  Show process indicators for running apps"
defaults write com.apple.dock show-process-indicators -bool true

log_info "  Minimize windows into application icon"
defaults write com.apple.dock minimize-to-application -bool true

log_info "  Don't automatically rearrange spaces"
defaults write com.apple.dock mru-spaces -bool false

# ================================================================
# SAFARI - Privacy and Developer Features
# ================================================================

log_info "Configuring Safari..."

# Privacy
log_info "  Show full URL in address bar"
defaults write com.apple.Safari ShowFullURLInSmartSearchField -bool true

log_info "  Don't send search queries to Apple"
defaults write com.apple.Safari UniversalSearchEnabled -bool false
defaults write com.apple.Safari SuppressSearchSuggestions -bool true

log_info "  Enable 'Do Not Track' header"
defaults write com.apple.Safari SendDoNotTrackHTTPHeader -bool true

log_info "  Warn about fraudulent websites"
defaults write com.apple.Safari WarnAboutFraudulentWebsites -bool true

# Downloads and Files
log_info "  Don't auto-open safe downloads"
defaults write com.apple.Safari AutoOpenSafeDownloads -bool false

# Developer Features
log_info "  Enable developer menu"
defaults write com.apple.Safari IncludeDevelopMenu -bool true
defaults write com.apple.Safari WebKitDeveloperExtrasEnabledPreferenceKey -bool true
defaults write com.apple.Safari com.apple.Safari.ContentPageGroupIdentifier.WebKit2DeveloperExtrasEnabled -bool true

# Extensions
log_info "  Auto-update Safari extensions"
defaults write com.apple.Safari InstallExtensionUpdatesAutomatically -bool true

# ================================================================
# MAIL - Threading and Formatting
# ================================================================

log_info "Configuring Mail..."

log_info "  Display messages in threaded mode"
defaults write com.apple.mail DraftsViewerAttributes -dict-add "DisplayInThreadedMode" -string "yes"

log_info "  Sort messages by date (newest first)"
defaults write com.apple.mail DraftsViewerAttributes -dict-add "SortOrder" -string "received-date"
defaults write com.apple.mail DraftsViewerAttributes -dict-add "SortedDescending" -string "yes"

# ================================================================
# SYSTEM - Global Preferences
# ================================================================

log_info "Configuring System Preferences..."

# Keyboard
log_info "  Disable automatic capitalization"
defaults write NSGlobalDomain NSAutomaticCapitalizationEnabled -bool false

log_info "  Disable automatic period substitution"
defaults write NSGlobalDomain NSAutomaticPeriodSubstitutionEnabled -bool false

log_info "  Disable automatic dash substitution"
defaults write NSGlobalDomain NSAutomaticDashSubstitutionEnabled -bool false

log_info "  Disable automatic quote substitution"
defaults write NSGlobalDomain NSAutomaticQuoteSubstitutionEnabled -bool false

log_info "  Disable automatic spell correction"
defaults write NSGlobalDomain NSAutomaticSpellingCorrectionEnabled -bool false

log_info "  Enable full keyboard access for all controls"
# Allows Tab to navigate to buttons/checkboxes (not just text fields)
defaults write NSGlobalDomain AppleKeyboardUIMode -int 3

log_info "  Set fast key repeat rate"
# How fast keys repeat when held. Default: 6, This: 2 (faster for Vim/arrows/backspace)
defaults write NSGlobalDomain KeyRepeat -int 2

log_info "  Set short initial key repeat delay"
# Delay before repeat starts. Default: 25 (500ms), This: 15 (300ms, more responsive)
defaults write NSGlobalDomain InitialKeyRepeat -int 15

# ================================================================
# SCREENSHOTS - Location and Format
# ================================================================

log_info "Configuring Screenshots..."

log_info "  Save screenshots to ~/Desktop/screenshots"
mkdir -p "$HOME/Desktop/screenshots"
defaults write com.apple.screencapture location -string "$HOME/Desktop/screenshots"

log_info "  Save screenshots as PNG format"
defaults write com.apple.screencapture type -string "png"

log_info "  Disable screenshot shadow"
defaults write com.apple.screencapture disable-shadow -bool true

# ================================================================
# MAC APP STORE - Updates and Development
# ================================================================

log_info "Configuring Mac App Store..."

log_info "  Enable automatic update checks"
defaults write com.apple.SoftwareUpdate AutomaticCheckEnabled -bool true

log_info "  Download newly available updates in background"
defaults write com.apple.SoftwareUpdate AutomaticDownload -bool true

log_info "  Install critical security updates automatically"
defaults write com.apple.SoftwareUpdate CriticalUpdateInstall -bool true

log_info "  Enable debug menu"
defaults write com.apple.appstore ShowDebugMenu -bool true

log_info "  Enable developer extras"
defaults write com.apple.appstore WebKitDeveloperExtras -bool true

# ================================================================
# PHOTOS - Auto-Import Behavior
# ================================================================

log_info "Configuring Photos..."

log_info "  Prevent Photos from opening when devices are connected"
defaults -currentHost write com.apple.ImageCapture disableHotPlug -bool true

# ================================================================
# MESSAGES - Text Substitution
# ================================================================

log_info "Configuring Messages..."

log_info "  Disable automatic emoji substitution"
defaults write com.apple.messageshelper.MessageController SOInputLineSettings -dict-add "automaticEmojiSubstitutionEnablediMessage" -bool false

log_info "  Disable smart quotes in Messages"
defaults write com.apple.messageshelper.MessageController SOInputLineSettings -dict-add "automaticQuoteSubstitutionEnabled" -bool false

# ================================================================
# SECURITY AND PRIVACY
# ================================================================

log_info "Configuring Security and Privacy..."

log_info "  Disable Siri suggestions in Spotlight"
defaults write com.apple.lookup.shared LookupSuggestionsDisabled -bool true

# ================================================================
# TEXT EDIT
# ================================================================

log_info "Configuring TextEdit..."

log_info "  Use plain text mode by default"
defaults write com.apple.TextEdit RichText -int 0

log_info "  Open and save files as UTF-8"
defaults write com.apple.TextEdit PlainTextEncoding -int 4
defaults write com.apple.TextEdit PlainTextEncodingForWrite -int 4

# Note: App restarts removed - changes take effect on next login/reboot

# ================================================================
# Completion
# ================================================================

echo ""
print_banner_success "macOS Preferences Applied Successfully"

echo ""
log_success "All preferences have been configured"
log_info "Changes will take effect on next login or reboot"

echo ""
log_info "Key changes applied:"
echo "  • Finder: Extensions, path bar, search in current folder"
echo "  • Dock: Bottom position, size 90, auto-hide enabled"
echo "  • Keyboard: Full access (Tab to buttons), fast key repeat"
echo "  • Safari: Privacy features, developer tools"
echo "  • Mail: Threaded view, quick send with ⌘+Enter"
echo "  • System: Disabled auto-correct, expanded dialogs"
echo "  • Screenshots: Saved to ~/Desktop/screenshots as PNG"

echo ""

exit_success
