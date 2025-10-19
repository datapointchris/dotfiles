#!/usr/bin/env bash

SHELLS="$HOME/.shell"
source "$SHELLS/colors.sh"

# help.sh -- self-contained on-line help for bash scripts
#
# (C) Copyright 2013, Dario Hamidi <dario.hamidi@gmail.com>
#
# help.sh is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# help.sh is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with help.sh.  If not, see <http://www.gnu.org/licenses/>.
#

# To see help.sh in action try the following in the directory of
# help.sh:
#
## summary of all public commands (i.e. not idented)
#
# (source help.sh; help help.sh)
#
## summary of all documented commands
#
# (source help.sh; HELP_BOL=no; help help.sh)
#
## detailed description of a single command
#
# (source help.sh; help help.sh help)
#

# Provide your script with a help function:
#
# function help {
#     (source help.sh; help $0 $@)
# }

#@indent-to
#+WORD COL -- out spaces to position cursor after WORD in column COL
function indent-to {
    local word=$1
    declare -i col=$2

    for ((i = ${#word}; i < col; i++)); do
        echo -n " "
    done
}

#@warn
#+MSG -- outputs MSG on standard error, prefixed with the script name
function warn {
    local msg=$1

    echo "$0: $msg" >&2
}

#@fatal
#+MSG -- warn MSG, then exit with exit code 1
function fatal {
    local msg=$1

    warn "$msg"
    exit 1
}

#@help
#+FILE [COMMAND] -- briefly describe commands extracted from FILE
#
# This function parses special comments in the shell script FILE in
# order to display a summary of all interactive commands FILE supports.
#
# If COMMAND is given and names a existing command in FILE, a longer
# description of just COMMAND is displayed.
#
# The behavior of `help' can be influenced with these environment
# variables:
#
# - HELP_COL (Default: 25)
#
# the column where the command summary should start
#
# - HELP_BOL (Default: "yes")
#
# if set to "yes", then only comments starting in column 0 are taken
# into account when parsing a command's documentation.
function help {

    local file=$1
    local command=$2

    # command -> summary
    declare -A summary=()

    # command -> long description
    declare -A description=()

    # does FILE exist?
    [[ -n "$file" && -e "$file" ]] || fatal "'$file' does not exist"

    # parse FILE
    local current_command # the command currently being parsed
    local OLDIFS="$IFS"
    local IFS="$OLDIFS"
    if [[ "${HELP_BOL:-yes}" == "yes" ]]; then
        # preserve whitespace
        IFS=''
    fi

    while read -r line; do
        # Below, the first `#' after the slash in 'line/##@/'
        # anchors the pattern at the beginning of the string
        # (if the line is unequal to the stripped version, then it got stripped so it's what we want)

        # COMMAND - a line beginning with '#@name' introduces command `name'
        command_anchor="#@"
        if [[ "$line" != "${line/#$command_anchor/}" ]]; then
            anchor_len=${#command_anchor}
            # strip the command_anchor
            current_command="${line:$anchor_len}"

            if [[ -n $DEBUG ]]; then
                echo "command"
                echo $LINENO: "$anchor_len"
                echo $LINENO: "$current_command"
            fi

        # SUMMARY - a line beginning with '#SUMMARY-->' defines the summary
        summary_anchor="#-->"
        elif [[ -n "$current_command" && ("$line" != "${line/#$summary_anchor/}") ]]; then
            # strip the command_anchor
            # put it in the summary array
            anchor_len=${#summary_anchor}
            summary["$current_command"]="${line:$anchor_len}"

            if [[ -n $DEBUG ]]; then
                echo "summary"
                echo $LINENO: "$anchor_len"
                echo $LINENO: "$current_command"
            fi

        # FUNCTION - a line beginning with 'function' ends the command documentation
        elif [[ "$line" != "${line/#function/}" ]]; then
            current_command=""

            if [[ -n $DEBUG ]]; then
                echo "function"
                echo $LINENO: "$anchor_len"
                echo $LINENO: "$current_command"
            fi

        # DESCRIPTION - add the line to the description array
        elif [[ -n "$current_command" && ("$line" != "${line/##/}") ]]; then

            if [[ -n $DEBUG ]]; then
                echo "description"
                echo $LINENO: "$anchor_len"
                echo $LINENO: "$current_command"
            fi

            description["$current_command"]="${description[$current_command]}${line##\#}\n"

        fi
    done <"$file"
    IFS="$OLDIFS"

    # Give some space from the calling command
    echo

    # SINGLE COMMAND - if command provided
    if [[ -n "$command" ]]; then
        color_blue "$command"
        echo "${summary[$command]}"
        echo -e "${description[$command]}"

    # PRINT ALL - all commands and full descriptions printed
    elif [[ -n $PRINT_ALL ]]; then
        for command in "${!summary[@]}"; do
            color_blue "$command"
            echo "${summary[$command]}"
            echo -e "${description[$command]}"
        done
    else
        # output a short summary for each command
        for command in "${!summary[@]}"; do
            echo -n "$(color_blue "$command")"
            indent-to "$command" "${HELP_COL:-20}"
            echo "${summary[$command]}"
        done
    fi
}

if [[ -n "$1" ]]; then
    if [[ "$1" = "--all" ]]; then
        PRINT_ALL=true
        shift
    fi
    help "$@"
else
    echo "Must provide script to get docs from"
    exit 1
fi
