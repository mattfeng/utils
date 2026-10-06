from __future__ import annotations

import argparse
import curses
import os
import stat
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


DEFAULT_VIM_CONFIG = Path("~/.vimrc")
DEFAULT_OMP_CONFIG = Path("~/.omp/agent/config.yml")
DEFAULT_OMP_KEYBINDINGS = Path("~/.omp/agent/keybindings.yml")
MARKER_TEXT = "mattfeng-utils devcontainer config"

VIM_CONFIG = r'''" Copy yanked text to the host clipboard with OSC 52.
if exists('##TextYankPost')
  function! s:Osc52Copy(lines, register_type) abort
    let l:text = join(a:lines, "\n")
    if a:register_type ==# 'V'
      let l:text .= "\n"
    endif

    let l:encoded = substitute(system('base64', l:text), '\_s', '', 'g')
    if v:shell_error
      echoerr 'OSC 52 copy failed: base64 exited with an error'
      return
    endif

    silent! call writefile(["\x1b]52;c;" . l:encoded . "\x07"], '/dev/tty', 'b')
  endfunction

  function! s:Osc52CopyYank() abort
    if v:event.operator !=# 'y' || v:event.regname ==# '_'
      return
    endif
    call s:Osc52Copy(v:event.regcontents, v:event.regtype)
  endfunction

  augroup osc52_yank
    autocmd!
    autocmd TextYankPost * call <SID>Osc52CopyYank()
  augroup END
endif
'''

OMP_CONFIG = """\
setupVersion: 2
modelRoles:
  slow: openai-codex/gpt-6-astra:high
  default: openai-codex/gpt-6-astra:medium
  smol: openai-codex/gpt-6-luna:low
defaultThinkingLevel: medium
symbolPreset: unicode
composer:
  shape: rule
theme:
  dark: dark-catppuccin
statusLine:
  compactThinkingLevel: false
  preset: custom
  leftSegments: [model, status, mode, path, git]
  rightSegments: [context_pct, usage, cost]
  showHookStatus: false
providers:
  webSearchExclude:
    - perplexity
    - gemini
    - anthropic
    - xai
    - zai
    - exa
    - tinyfish
    - jina
    - kagi
    - tavily
    - firecrawl
    - brave
    - kimi
    - parallel
    - synthetic
    - searxng
    - startpage
    - duckduckgo
    - ecosia
    - google
    - mojeek
    - public
  webSearchOrder:
    - codex
startup:
  checkUpdate: false
"""

OMP_KEYBINDINGS = """\
app.model.selectTemporary: []
app.model.cycleForward: Alt+P
"""


@dataclass(frozen=True)
class ConfigFile:
    name: str
    destination: Path
    content: str
    comment_prefix: str

    @property
    def begin_marker(self) -> str:
        return f"{self.comment_prefix} <-- {MARKER_TEXT}: begin -->"

    @property
    def end_marker(self) -> str:
        return f"{self.comment_prefix} <-- {MARKER_TEXT}: end -->"


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return setup_devcontainer_configs(args)
    except SetupError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("cancelled", file=sys.stderr)
        return 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="setup-devcontainer-configs",
        description="Install Vim and Oh My Pi configuration for a dev container.",
    )
    parser.add_argument(
        "--vim-config",
        type=Path,
        default=DEFAULT_VIM_CONFIG,
        help=f"Vim configuration file. Defaults to {DEFAULT_VIM_CONFIG}.",
    )
    parser.add_argument(
        "--omp-config",
        type=Path,
        default=DEFAULT_OMP_CONFIG,
        help=f"Oh My Pi configuration file. Defaults to {DEFAULT_OMP_CONFIG}.",
    )
    parser.add_argument(
        "--omp-keybindings",
        type=Path,
        default=DEFAULT_OMP_KEYBINDINGS,
        help=(
            "Oh My Pi keybindings file. "
            f"Defaults to {DEFAULT_OMP_KEYBINDINGS}."
        ),
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Select all config files without opening the interactive selector.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print selected destinations and content without writing files.",
    )
    return parser


def setup_devcontainer_configs(args: argparse.Namespace) -> int:
    configs = [
        ConfigFile("Vim", args.vim_config.expanduser(), VIM_CONFIG, '"'),
        ConfigFile("Oh My Pi", args.omp_config.expanduser(), OMP_CONFIG, "#"),
        ConfigFile(
            "Oh My Pi keybindings",
            args.omp_keybindings.expanduser(),
            OMP_KEYBINDINGS,
            "#",
        ),
    ]
    ensure_distinct_destinations(configs)
    rendered = [render_config(config) for config in configs]
    selected = rendered if args.all else run_config_tui(rendered)

    if not selected:
        print("no config files selected")
        return 0

    if args.dry_run:
        print_configs(selected)
        return 0

    pending = [config for config in selected if config.changed]
    if not pending:
        print("selected config files are already up to date")
        return 0

    for config in pending:
        write_atomically(config.spec.destination, config.rendered_content)
        print(f"updated {config.spec.name} config at {config.spec.destination}")
    return 0


def ensure_distinct_destinations(configs: list[ConfigFile]) -> None:
    destinations = [config.destination.resolve() for config in configs]
    if len(destinations) != len(set(destinations)):
        raise SetupError("managed configs must use different destinations")


@dataclass(frozen=True)
class RenderedConfig:
    spec: ConfigFile
    rendered_content: str
    changed: bool
    state: str


def render_config(config: ConfigFile) -> RenderedConfig:
    existing = read_config(config.destination)
    managed_block = (
        f"{config.begin_marker}\n{config.content.rstrip()}\n{config.end_marker}\n"
    )

    if existing is None:
        rendered = managed_block
        state = "new file"
    elif not existing:
        rendered = managed_block
        state = "add block"
    else:
        rendered, replaced = replace_or_append_block(
            existing,
            config,
            managed_block,
        )
        if existing == rendered:
            state = "up to date"
        elif replaced:
            state = "update available"
        else:
            state = "add block"

    return RenderedConfig(
        spec=config,
        rendered_content=rendered,
        changed=existing != rendered,
        state=state,
    )


def read_config(path: Path) -> str | None:
    if not destination_exists(path):
        return None
    if path.is_dir():
        raise SetupError(f"destination is a directory: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise SetupError(f"could not read {path}: {error}") from error


def replace_or_append_block(
    existing: str,
    config: ConfigFile,
    managed_block: str,
) -> tuple[str, bool]:
    lines = existing.splitlines(keepends=True)
    begin_lines = marker_line_indexes(lines, config.begin_marker)
    end_lines = marker_line_indexes(lines, config.end_marker)

    if not begin_lines and not end_lines:
        separator = "\n" if existing.endswith(("\n", "\r")) else "\n\n"
        return f"{existing}{separator}{managed_block}", False

    if len(begin_lines) != 1 or len(end_lines) != 1:
        raise SetupError(
            f"{config.destination} must contain exactly one complete "
            f"{MARKER_TEXT!r} block"
        )

    begin_line = begin_lines[0]
    end_line = end_lines[0]
    if begin_line >= end_line:
        raise SetupError(
            f"{config.destination} has invalid {MARKER_TEXT!r} marker order"
        )

    rendered = (
        "".join(lines[:begin_line])
        + managed_block
        + "".join(lines[end_line + 1 :])
    )
    return rendered, True


def marker_line_indexes(lines: list[str], marker: str) -> list[int]:
    return [
        index
        for index, line in enumerate(lines)
        if line.rstrip("\r\n") == marker
    ]


def run_config_tui(configs: list[RenderedConfig]) -> list[RenderedConfig]:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise SetupError(
            "setup-devcontainer-configs requires an interactive terminal; "
            "pass --all for non-interactive use"
        )

    selected = {
        index
        for index, config in enumerate(configs)
        if config.changed
    }
    try:
        selected_indexes = curses.wrapper(config_tui, configs, selected)
    except curses.error as error:
        raise SetupError(f"could not open the terminal UI: {error}") from error
    return [config for index, config in enumerate(configs) if index in selected_indexes]


def config_tui(
    screen,
    configs: list[RenderedConfig],
    selected: set[int],
) -> set[int]:
    set_cursor_visible(False)
    screen.keypad(True)
    cursor = 0

    while True:
        draw_config_tui(screen, configs, selected, cursor)
        key = screen.getch()

        if key in (ord("q"), 27):
            raise KeyboardInterrupt
        if key in (curses.KEY_UP, ord("k")):
            cursor = max(0, cursor - 1)
            continue
        if key in (curses.KEY_DOWN, ord("j")):
            cursor = min(len(configs) - 1, cursor + 1)
            continue
        if key == ord(" "):
            if cursor in selected:
                selected.remove(cursor)
            else:
                selected.add(cursor)
            continue
        if key in (ord("a"), ord("A")):
            selected = (
                set()
                if len(selected) == len(configs)
                else set(range(len(configs)))
            )
            continue
        if key in (curses.KEY_ENTER, 10, 13):
            return selected


def draw_config_tui(
    screen,
    configs: list[RenderedConfig],
    selected: set[int],
    cursor: int,
) -> None:
    screen.erase()
    height, width = screen.getmaxyx()
    add_line(screen, 0, "setup-devcontainer-configs", width, curses.A_BOLD)
    add_line(
        screen,
        1,
        "Up/down or j/k moves, Space selects, a selects all, Enter applies, q quits",
        width,
    )

    for index, config in enumerate(configs):
        marker = "x" if index in selected else " "
        text = f"[{marker}] {config.spec.name} [{config.state}]"
        attr = curses.A_REVERSE if index == cursor else curses.A_NORMAL
        add_line(screen, 3 + index * 2, text, width, attr)
        add_line(screen, 4 + index * 2, f"    {config.spec.destination}", width)

    add_line(
        screen,
        height - 1,
        f"{len(selected)} of {len(configs)} config file(s) selected",
        width,
    )
    screen.refresh()


def add_line(screen, y: int, text: str, width: int, attr: int = 0) -> None:
    if y < 0 or y >= screen.getmaxyx()[0] or width <= 1:
        return
    try:
        screen.addnstr(y, 0, text.ljust(width), width - 1, attr)
    except curses.error:
        pass


def set_cursor_visible(visible: bool) -> None:
    try:
        curses.curs_set(1 if visible else 0)
    except curses.error:
        pass


def print_configs(configs: list[RenderedConfig]) -> None:
    for index, config in enumerate(configs):
        if index:
            print()
        print(f"destination: {config.spec.destination}")
        print(config.rendered_content, end="")


def destination_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def write_atomically(destination: Path, content: str) -> None:
    temporary_path: Path | None = None
    try:
        target = destination.resolve() if destination.is_symlink() else destination
        existing_mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else None
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        if existing_mode is not None:
            temporary_path.chmod(existing_mode)
        os.replace(temporary_path, target)
    except OSError as error:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise SetupError(f"could not write {destination}: {error}") from error


class SetupError(Exception):
    pass
