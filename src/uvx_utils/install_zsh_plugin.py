from __future__ import annotations

import argparse
import curses
import os
import re
import shutil
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CUSTOM_DIR = Path("~/.oh-my-zsh/custom")
PLUGIN_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


@dataclass(frozen=True)
class Plugin:
    name: str
    source: Path
    summary: str


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return install_zsh_plugin(args)
    except InstallError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("cancelled", file=sys.stderr)
        return 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="install-zsh-plugin",
        description="Interactively install a bundled Oh My Zsh plugin.",
    )
    parser.add_argument(
        "--custom-dir",
        type=Path,
        default=None,
        help=(
            "Oh My Zsh custom directory. Defaults to $ZSH_CUSTOM or "
            f"{DEFAULT_CUSTOM_DIR}."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace the selected plugin directory if it already exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Select a plugin and print the destination without writing files.",
    )
    return parser


def install_zsh_plugin(args: argparse.Namespace) -> int:
    require_interactive_terminal()
    source_root = find_plugin_source_root()
    plugins = discover_plugins(source_root)
    custom_dir = resolve_custom_dir(args.custom_dir)
    plugins_dir = custom_dir / "plugins"
    selected = run_plugin_tui(plugins, plugins_dir)
    destination = plugins_dir / selected.name

    if args.dry_run:
        print(f"plugin: {selected.name}")
        print(f"source: {selected.source}")
        print(f"destination: {destination}")
        action = (
            "replace existing plugin"
            if destination_exists(destination)
            else "install plugin"
        )
        print(f"action: {action}")
        return 0

    if same_path(selected.source, destination):
        raise InstallError("the plugin source and destination are the same directory")
    if destination_exists(destination) and not args.force:
        raise InstallError(
            f"{destination} already exists; pass --force to replace it"
        )

    copy_plugin(selected.source, destination, replace=args.force)
    print(f"installed {selected.name} to {destination}")
    print(f"next: enable it in ~/.zshrc with `plugins+=({selected.name})`")
    print(
        "configuration: "
        "https://github.com/mattfeng/utils/tree/main/zsh-plugins"
    )
    return 0


def require_interactive_terminal() -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise InstallError("install-zsh-plugin requires an interactive terminal")


def find_plugin_source_root() -> Path:
    packaged = Path(__file__).with_name("zsh_plugins")
    repository = Path(__file__).resolve().parents[2] / "zsh-plugins"

    for candidate in (packaged, repository):
        if candidate.is_dir():
            return candidate
    raise InstallError("the packaged zsh-plugins directory could not be found")


def discover_plugins(source_root: Path) -> list[Plugin]:
    plugins = []
    for path in source_root.iterdir():
        if path.is_symlink() or not path.is_dir():
            continue
        if PLUGIN_NAME_PATTERN.fullmatch(path.name) is None:
            continue

        entrypoints = sorted(path.glob("*.plugin.zsh"))
        if not any(entrypoint.is_file() for entrypoint in entrypoints):
            continue
        plugins.append(
            Plugin(
                name=path.name,
                source=path,
                summary=read_summary(entrypoints[0]),
            )
        )

    if not plugins:
        raise InstallError(f"no Oh My Zsh plugins found in {source_root}")
    return sorted(plugins, key=lambda plugin: plugin.name.lower())


def read_summary(entrypoint: Path) -> str:
    try:
        lines = entrypoint.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""

    summary_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped and not summary_lines:
            continue
        if not stripped.startswith("#"):
            break
        text = stripped.removeprefix("#").strip()
        if not text:
            if summary_lines:
                break
            continue
        summary_lines.append(text)
    return " ".join(summary_lines)


def resolve_custom_dir(argument: Path | None) -> Path:
    if argument is not None:
        return argument.expanduser()

    configured = os.environ.get("ZSH_CUSTOM")
    if configured:
        return Path(configured).expanduser()
    return DEFAULT_CUSTOM_DIR.expanduser()


def run_plugin_tui(plugins: list[Plugin], plugins_dir: Path) -> Plugin:
    try:
        return curses.wrapper(tui_main, plugins, plugins_dir)
    except curses.error as error:
        raise InstallError(f"could not open the terminal UI: {error}") from error


def tui_main(screen, plugins: list[Plugin], plugins_dir: Path) -> Plugin:
    set_cursor_visible(False)
    screen.keypad(True)
    cursor = 0
    scroll = 0

    while True:
        draw(screen, plugins, plugins_dir, cursor, scroll)
        key = screen.getch()

        if key in (ord("q"), 27):
            raise KeyboardInterrupt
        if key in (curses.KEY_UP, ord("k")):
            cursor = max(0, cursor - 1)
            scroll = min(scroll, cursor)
            continue
        if key in (curses.KEY_DOWN, ord("j")):
            cursor = min(len(plugins) - 1, cursor + 1)
            list_height = max(1, screen.getmaxyx()[0] - 8)
            if cursor >= scroll + list_height:
                scroll = cursor - list_height + 1
            continue
        if key in (curses.KEY_ENTER, 10, 13):
            return plugins[cursor]


def draw(
    screen,
    plugins: list[Plugin],
    plugins_dir: Path,
    cursor: int,
    scroll: int,
) -> None:
    screen.erase()
    height, width = screen.getmaxyx()
    add_line(screen, 0, "install-zsh-plugin", width, curses.A_BOLD)
    add_line(screen, 1, f"Destination: {plugins_dir}", width)
    add_line(screen, 2, "Up/down or j/k moves, Enter installs, q quits", width)

    list_top = 4
    list_height = max(1, height - 8)
    for row, plugin in enumerate(plugins[scroll : scroll + list_height]):
        index = scroll + row
        marker = ">" if index == cursor else " "
        state = "installed" if destination_exists(plugins_dir / plugin.name) else "new"
        text = f"{marker} {plugin.name} [{state}]"
        attr = curses.A_REVERSE if index == cursor else curses.A_NORMAL
        add_line(screen, list_top + row, text, width, attr)

    selected = plugins[cursor]
    summary = selected.summary or "No description provided."
    add_line(screen, height - 2, summary, width)
    add_line(screen, height - 1, f"{len(plugins)} plugin(s) available", width)
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


def destination_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return False


def copy_plugin(source: Path, destination: Path, *, replace: bool) -> None:
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=f".{destination.name}-install-", dir=destination.parent
        ) as temporary_name:
            temporary = Path(temporary_name)
            staged = temporary / "plugin"
            previous = temporary / "previous"
            shutil.copytree(source, staged)

            moved_previous = False
            if destination_exists(destination):
                if not replace:
                    raise InstallError(f"{destination} already exists")
                destination.replace(previous)
                moved_previous = True

            try:
                staged.replace(destination)
            except BaseException:
                if moved_previous and not destination_exists(destination):
                    previous.replace(destination)
                raise
    except InstallError:
        raise
    except OSError as error:
        raise InstallError(f"could not install {destination.name}: {error}") from error


class InstallError(Exception):
    pass
