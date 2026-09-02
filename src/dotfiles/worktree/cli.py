"""The grammar, and the one place a refusal becomes an exit code.

argparse rather than typer, which is what the rest of this package uses: the
verbs here take positional scope and a parent-supplied `-q`, and nothing in them
wants a type-annotated signature to derive a flag from.
"""

from __future__ import annotations

import argparse

from dotfiles.worktree import MAIN_PANE_WIDTH
from dotfiles.worktree import REGISTRATION_TIMEOUT
from dotfiles.worktree import Refused
from dotfiles.worktree.commands import cmd_choose
from dotfiles.worktree.commands import cmd_drop
from dotfiles.worktree.commands import cmd_land
from dotfiles.worktree.commands import cmd_list
from dotfiles.worktree.commands import cmd_new
from dotfiles.worktree.commands import cmd_show
from dotfiles.worktree.commands import cmd_spawn
from dotfiles.worktree.commands import cmd_sweep
from dotfiles.worktree.output import say_error
from dotfiles.worktree.output import say_info
from dotfiles.worktree.output import set_echo
from dotfiles.worktree.panes import usable_width


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='worktree',
        description='Give a session its own index, and land it on main without a PR.',
        epilog=(
            'Worktrees live under $WORKTREE_ROOT (default ~/.worktrees/<repo>/<slug>). '
            "'list' and 'choose' read every repo there. "
            'Every command it runs is echoed to stderr as you could re-type it; -q hides them. '
            "For work that grew into a large feature, 'git push -u origin HEAD' and open a PR instead."
        ),
    )
    commands = parser.add_subparsers(dest='command', metavar='<command>')

    # argparse parses a group's options before the subcommand name, so a -q
    # declared on `parser` turns `worktree land -q` into an unrecognized argument.
    # A parent puts it on every leaf, which is where it is typed.
    quiet = argparse.ArgumentParser(add_help=False)
    quiet.add_argument('-q', '--quiet', action='store_true', help='hide the commands this runs')

    new = commands.add_parser(
        'new',
        parents=[quiet],
        help="isolate a session off origin's default branch, run the repo's `task setup`, print the path",
    )
    new.add_argument('slug', help='names both the directory and the branch')

    spawn = commands.add_parser(
        'spawn',
        parents=[quiet],
        help='start a Claude session in a pane: with a slug in a worktree, without one in the checkout',
        description=(
            "Split the caller's pane, launch `claude` against a written brief, and print the name the session "
            'registered under. '
            'A slug names the branch, so `spawn <slug>` creates or attaches a worktree and puts the session in '
            'it, and `spawn` with no slug stands the session in the primary checkout with no branch — which is '
            'what a reviewer needs, since a session inside a worktree is refused any `git -C` that leaves it. '
            'The brief is copied and the session reads the copy, whose path `--json` returns. '
            'It exits non-zero when no session registered, because the name is the product.'
        ),
    )
    spawn.add_argument(
        'slug', nargs='?', help='names the directory and the branch; without it the session stands in the checkout and gets no branch'
    )
    spawn.add_argument(
        '--brief', required=True, metavar='PATH', help='the file the session is told to read; it is copied, and the copy is what it reads'
    )
    spawn.add_argument('--below', action='store_true', help='split under the caller rather than beside it, and leave the layout alone')
    # No default here, so an absent flag is distinguishable from one spelling the default
    # out. `cli-design.md` § "A sentinel never steals a value the caller can mean" —
    # with the default as the sentinel, `--below --width 66%` reads as no --width at all.
    # argparse also runs a help string through %-formatting, so a literal percent in the
    # default has to arrive doubled or `--help` dies rather than the command.
    spawn.add_argument(
        '--width',
        metavar='WIDTH',
        help=f"the caller's share of the window after the split, in columns or a percentage (default {MAIN_PANE_WIDTH.replace('%', '%%')})",
    )
    spawn.add_argument(
        '--timeout',
        type=float,
        default=REGISTRATION_TIMEOUT,
        metavar='SECONDS',
        help=f'how long to wait for the session to register (default {REGISTRATION_TIMEOUT:g})',
    )
    spawn.add_argument('--json', action='store_true', dest='as_json', help='the session, pane, path, branch and brief for a script to read')
    spawn.set_defaults(subparser=spawn)

    commands.add_parser('land', parents=[quiet], help='rebase, push onto the default branch, then clean up')

    drop = commands.add_parser('drop', parents=[quiet], help='abandon the worktree you are in, without landing it')
    drop.add_argument('--force', action='store_true', help='throw the work away, commits included')

    # `sweep` is the counterpart to `drop`, not a bulk spelling of it. `drop` abandons
    # work that was never landed and needs you standing in it; `sweep` disposes of work
    # that is already merged, anywhere on the machine, and refuses anything unlanded.
    sweep = commands.add_parser(
        'sweep',
        parents=[quiet],
        help='remove every finished worktree on the machine: merged, and deleted on the remote',
        description=(
            'Remove every worktree whose work is finished, and delete its branch. '
            'A worktree qualifies only when its tree is clean, no session is standing in it, '
            'its changes are already on origin/<base>, and the branch it was pushed to '
            'under its own name has since been deleted on the remote. Everything else is kept, '
            'with the reason printed. '
            'It lists what it will remove and asks first; without a terminal it removes nothing '
            'unless --yes is passed.'
        ),
    )
    sweep.add_argument('repo', nargs='?', help='narrow to one repo')
    sweep.add_argument('--yes', action='store_true', help='remove without asking; required when there is no terminal')

    listing = commands.add_parser('list', parents=[quiet], help="every worktree on this machine, or one repo's")
    listing.add_argument('repo', nargs='?', help='narrow to one repo')
    listing.add_argument('--json', action='store_true', dest='as_json', help='the same rows for a script to read')
    # Scope is structural here: `list` is the whole machine and `list <repo>` is
    # one repo. --all is caught rather than left to argparse's "unrecognized
    # arguments", because it is the spelling a flag-shaped habit reaches for and
    # the error is the only chance to teach the argument.
    listing.add_argument('--all', action='store_true', help=argparse.SUPPRESS)
    listing.set_defaults(subparser=listing)

    show = commands.add_parser('show', parents=[quiet], help='what one worktree carries, and which session is in it')
    show.add_argument('path', nargs='?', help='defaults to the worktree you are standing in')

    choose = commands.add_parser('choose', parents=[quiet], help='pick one with fzf; prints the path it chose')
    choose.add_argument('repo', nargs='?', help='narrow to one repo')

    return parser


def dispatch(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    match args.command:
        case 'new':
            return cmd_new(args.slug)
        case 'spawn':
            # `--width` is spawn's own flag and `--below` is what voids it: a below split
            # leaves the layout alone, so main-pane-width would parse and reach nothing.
            # `cli-design.md` § "A flag the run cannot honour says so" makes that a usage
            # error rather than a silent no-op.
            if args.below and args.width is not None:
                args.subparser.error('no --width with --below: a split below leaves the layout alone, so there is no main pane to size')
            # Validated here rather than downstream, because tmux takes anything and then
            # falls back to the 80 columns this flag exists to replace.
            if args.width is not None and not usable_width(args.width):
                args.subparser.error(f'--width takes columns or a percentage, like 120 or {MAIN_PANE_WIDTH}, not {args.width!r}')
            return cmd_spawn(
                args.slug,
                args.brief,
                below=args.below,
                width=args.width or MAIN_PANE_WIDTH,
                timeout=args.timeout,
                as_json=args.as_json,
            )
        case 'land':
            return cmd_land()
        case 'drop':
            return cmd_drop(args.force)
        case 'sweep':
            return cmd_sweep(args.repo, args.yes)
        case 'list':
            if args.all:
                args.subparser.error("no --all: 'worktree list' is already every repo, and 'worktree list <repo>' narrows it")
            return cmd_list(args.repo, args.as_json)
        case 'show':
            return cmd_show(args.path)
        case 'choose':
            return cmd_choose(args.repo)
        case _:
            parser.print_help()
            return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    set_echo(not getattr(args, 'quiet', False))
    try:
        return dispatch(parser, args)
    except Refused as refusal:
        say_error(refusal.reason)
        for hint in refusal.hints:
            say_info(hint)
        return 1
