from __future__ import annotations

import argparse
import base64
import binascii
import curses
import os
import stat
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher, unified_diff
from importlib import resources
from pathlib import Path


DEFAULT_VIM_CONFIG = Path("~/.vimrc")
DEFAULT_OMP_CONFIG = Path("~/.omp/agent/config.yml")
DEFAULT_OMP_KEYBINDINGS = Path("~/.omp/agent/keybindings.yml")
DEFAULT_OMP_SYSTEM_PROMPT = Path("~/.omp/agent/SYSTEM.md")
MARKER_TEXT = "mattfeng-utils devcontainer config"
BASELINE_LABEL = "generated baseline v1 (base64): "
BLOCK_GUIDANCE = (
    "Generated defaults + your edits; setup merges future updates.",
    "Edit the content below; keep the baseline and markers intact.",
)


@dataclass(frozen=True)
class ConfigFile:
    name: str
    destination: Path
    content: str
    comment_prefix: str

    @property
    def begin_marker(self) -> str:
        return f"{self.comment_prefix} {MARKER_TEXT}: begin -->"

    @property
    def end_marker(self) -> str:
        return f"{self.comment_prefix} {MARKER_TEXT}: end -->"

    def comment(self, text: str) -> str:
        return f"{self.comment_prefix} {text} -->\n"


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
        "--omp-system-prompt",
        type=Path,
        default=DEFAULT_OMP_SYSTEM_PROMPT,
        help=(
            "Oh My Pi system prompt file. "
            f"Defaults to {DEFAULT_OMP_SYSTEM_PROMPT}."
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
    templates = resources.files("uvx_utils") / "templates" / "devcontainer"
    configs = [
        ConfigFile(
            "Vim",
            args.vim_config.expanduser(),
            (templates / "vimrc").read_text(encoding="utf-8"),
            '" <--',
        ),
        ConfigFile(
            "Oh My Pi",
            args.omp_config.expanduser(),
            (templates / "config.yml").read_text(encoding="utf-8"),
            "# <--",
        ),
        ConfigFile(
            "Oh My Pi keybindings",
            args.omp_keybindings.expanduser(),
            (templates / "keybindings.yml").read_text(encoding="utf-8"),
            "# <--",
        ),
        ConfigFile(
            "Oh My Pi system prompt",
            args.omp_system_prompt.expanduser(),
            (templates / "SYSTEM.md").read_text(encoding="utf-8"),
            "<!--",
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

    # Resolve every selected conflict before writing any destination.
    pending = [resolve_conflict(config) for config in selected if config.changed]
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
    conflict: bool = False
    local_content: str = ""
    prefix: str = ""
    suffix: str = ""


def template_content(config: ConfigFile) -> str:
    return config.content.rstrip() + "\n"


def managed_block(config: ConfigFile, content: str) -> str:
    baseline = base64.b64encode(template_content(config).encode("utf-8")).decode("ascii")
    return (
        f"{config.begin_marker}\n"
        + "".join(config.comment(line) for line in BLOCK_GUIDANCE)
        + config.comment(BASELINE_LABEL + baseline)
        + content
        + f"{config.end_marker}\n"
    )


def render_config(config: ConfigFile) -> RenderedConfig:
    existing = read_config(config.destination)
    block = managed_block(config, template_content(config))

    if existing is None:
        rendered = block
        state = "new file"
    elif not existing:
        rendered = block
        state = "add block"
    else:
        parts = split_managed_block(existing, config)
        if parts is None:
            separator = "\n" if existing.endswith(("\n", "\r")) else "\n\n"
            rendered = existing + separator + block
            replaced = False
        else:
            prefix, installed, suffix = parts
            baseline, local = read_baseline(installed, config)
            incoming = template_content(config)
            merged = merge_content(baseline, local, incoming)
            if merged is None:
                return RenderedConfig(
                    config, existing, True, "conflict: review required", True,
                    local, prefix, suffix,
                )
            rendered = prefix + managed_block(config, merged) + suffix
            replaced = True
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


def split_managed_block(
    existing: str,
    config: ConfigFile,
) -> tuple[str, str, str] | None:
    lines = existing.splitlines(keepends=True)
    begin_lines = marker_line_indexes(lines, config.begin_marker)
    end_lines = marker_line_indexes(lines, config.end_marker)

    if not begin_lines and not end_lines:
        return None

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

    return (
        "".join(lines[:begin_line]),
        "".join(lines[begin_line + 1 : end_line]),
        "".join(lines[end_line + 1 :]),
    )


def read_baseline(installed: str, config: ConfigFile) -> tuple[str | None, str]:
    lines = installed.splitlines(keepends=True)
    label = f"{config.comment_prefix} {BASELINE_LABEL}"
    indexes = [i for i, line in enumerate(lines) if line.startswith(label)]
    if not indexes:
        if any("generated baseline" in line for line in lines):
            raise SetupError(f"{config.destination} has unrecognized baseline metadata")
        return None, installed  # Legacy block: never guess which lines were user edits.
    index = indexes[0]
    if len(indexes) != 1 or index != 2:
        raise SetupError(f"{config.destination} has invalid baseline metadata")
    if [line.rstrip("\r\n") for line in lines[:2]] != [
        config.comment(line).rstrip("\n") for line in BLOCK_GUIDANCE
    ]:
        raise SetupError(f"{config.destination} has modified baseline header comments")
    encoded = lines[index][len(label):].rstrip("\r\n")
    if not encoded.endswith(" -->"):
        raise SetupError(f"{config.destination} has incomplete baseline metadata")
    try:
        baseline = base64.b64decode(encoded[:-4], validate=True).decode("utf-8")
    except (ValueError, binascii.Error, UnicodeError) as error:
        raise SetupError(f"{config.destination} has invalid baseline metadata") from error
    return baseline, "".join(lines[index + 1 :])


def merge_content(base: str | None, local: str, incoming: str) -> str | None:
    """Merge independent line edits; return None when a user decision is needed."""
    if local == incoming or local == base:
        return incoming
    if incoming == base:
        return local
    if base is None:
        return None

    original = base.splitlines(keepends=True)

    def edits(content: str) -> list[tuple[int, int, list[str]]]:
        lines = content.splitlines(keepends=True)
        return [
            (start, end, lines[new_start:new_end])
            for tag, start, end, new_start, new_end in SequenceMatcher(
                None, original, lines, autojunk=False,
            ).get_opcodes()
            if tag != "equal"
        ]

    local_edits = edits(local)
    incoming_edits = edits(incoming)
    for start, end, replacement in local_edits:
        for other_start, other_end, other_replacement in incoming_edits:
            if (start, end, replacement) == (other_start, other_end, other_replacement):
                continue
            overlap = max(start, other_start) < min(end, other_end)
            insertion_overlap = (
                start == end and other_start <= start < other_end
                or other_start == other_end and start <= other_start < end
                or start == end == other_start == other_end
            )
            if overlap or insertion_overlap:
                return None

    combined = local_edits + [edit for edit in incoming_edits if edit not in local_edits]
    result = original[:]
    for start, end, replacement in sorted(combined, key=lambda edit: edit[:2], reverse=True):
        result[start:end] = replacement
    return "".join(result)


def conflict_diff(config: RenderedConfig) -> str:
    return "".join(unified_diff(
        config.local_content.splitlines(keepends=True),
        template_content(config.spec).splitlines(keepends=True),
        fromfile="your installed content",
        tofile="new generated defaults",
    ))


def resolve_conflict(config: RenderedConfig) -> RenderedConfig:
    if not config.conflict:
        return config
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise SetupError(
            f"{config.spec.destination} needs conflict review; no files were written. "
            "Run in an interactive terminal (use --all to skip the selector), "
            "or inspect --all --dry-run."
        )
    print(f"\nConflict or missing baseline in {config.spec.destination}")
    print(conflict_diff(config), end="")
    print("Keep retains the entire installed block; generated replaces it with new defaults.")
    print("Either choice records the new defaults as the baseline for future merges.")
    while True:
        try:
            choice = input("[k]eep your content / use [g]enerated defaults / [a]bort (default): ")
        except EOFError as error:
            raise SetupError("conflict review cancelled; no files were written") from error
        choice = choice.strip().lower()
        if choice in ("", "a"):
            raise SetupError("conflict review cancelled; no files were written")
        if choice in ("k", "g"):
            content = config.local_content if choice == "k" else template_content(config.spec)
            rendered = config.prefix + managed_block(config.spec, content) + config.suffix
            return RenderedConfig(config.spec, rendered, True, "conflict resolved")


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
        if config.conflict:
            print("CONFLICT: installed file preserved; interactive review required.")
            print(conflict_diff(config), end="")
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
