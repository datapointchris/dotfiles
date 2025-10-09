#!/usr/bin/env zsh
# shellcheck shell=bash

source "$BASE_DIR/ENVIRONMENT.sh"
source colors.sh
source formatting.sh

# Symlink brew install java versions into system default folder
## Make the default

### I don't know or think I should need to do this
### This doesn't make a lot of sense

color_yellow "$(print_section "Brew Installed Java Versions")"

ln -sfn "$(brew --prefix)/opt/openjdk@8/libexec/openjdk.jdk" /Library/Java/JavaVirtualMachines/openjdk@8.jdk
ln -sfn "$(brew --prefix)/opt/openjdk@11/libexec/openjdk.jdk" /Library/Java/JavaVirtualMachines/openjdk@11.jdk
ln -sfn "$(brew --prefix)/opt/openjdk@17/libexec/openjdk.jdk" /Library/Java/JavaVirtualMachines/openjdk@17.jdk
echo


color_yellow "$(print_section "Add brew Java Versions to Jenv")"

jenv add /Library/Java/JavaVirtualMachines/openjdk@8.jdk/Contents/Home
jenv add /Library/Java/JavaVirtualMachines/openjdk@11.jdk/Contents/Home
jenv add /Library/Java/JavaVirtualMachines/openjdk@17.jdk/Contents/Home
