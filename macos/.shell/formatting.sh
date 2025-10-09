# shellcheck shell=bash

bold=$(tput bold)
underline=$(tput smul)
normal=$(tput sgr0)

print_title() {
    local message=$(
        cat <<-TITLE

		$(terminal_width_separator "=")
		$(center_text "$(color_green "$1")")
		$(terminal_width_separator "-")
	TITLE
    )
    echo "$message"
    echo
}

print_section() { echo "${underline}        $1          ${normal}"; }

center_text() { printf "%*s\n" $((($(tput cols) + ${#1}) / 2)) "$1"; }

section_separater() { printf "${underline}%0$(tput cols)d${normal}\n\n" 0 | tr '0' " "; }

terminal_width_separator() { printf "%0$(tput cols)d" 0 | tr '0' "${1:-_}"; }


print_conclusion() {
    local message=$(
        cat <<-TITLE

		$(terminal_width_separator "-")
		$(center_text "$(color_green "$1")")
		$(terminal_width_separator "=")
	TITLE
    )
    echo "$message"
    echo
}

yell() {
    echo "$0: $*" >&2
}

die() {
    yell "$*"
    exit 1
}

try() {
    "$@" || die "cannot $*"
}
