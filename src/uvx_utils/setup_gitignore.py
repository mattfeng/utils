from __future__ import annotations

import argparse
import curses
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


GITIGNORE_REPO = "github/gitignore"
GITIGNORE_BRANCH = "main"
TREE_URL = (
    f"https://api.github.com/repos/{GITIGNORE_REPO}/git/trees/"
    f"{GITIGNORE_BRANCH}?recursive=1"
)
RAW_BASE_URL = f"https://raw.githubusercontent.com/{GITIGNORE_REPO}/{GITIGNORE_BRANCH}"
CONFIG_PATH = Path(".gitignore-templates.json")
GITIGNORE_PATH = Path(".gitignore")
USER_AGENT = "mattfeng-utils/setup-gitignore"

BEGIN_MARKER = "# <-- mattfeng-utils gitignore templates: begin -->"
END_MARKER = "# <-- mattfeng-utils gitignore templates: end -->"

COMMON_TEMPLATES = [
    ("macOS", "Global/macOS.gitignore"),
    ("Python", "Python.gitignore"),
    ("Linux", "Global/Linux.gitignore"),
]


@dataclass(frozen=True)
class Template:
    label: str
    path: str


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return setup_gitignore(args)
    except SetupError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("cancelled", file=sys.stderr)
        return 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="setup-gitignore",
        description="Create or update a generated .gitignore block from github/gitignore.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=CONFIG_PATH,
        help=f"Selection file to read and write. Defaults to {CONFIG_PATH}.",
    )
    parser.add_argument(
        "--gitignore",
        type=Path,
        default=GITIGNORE_PATH,
        help=f".gitignore file to update. Defaults to {GITIGNORE_PATH}.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated .gitignore content without writing files.",
    )
    return parser


def setup_gitignore(args: argparse.Namespace) -> int:
    remembered = load_selection(args.config)
    templates = fetch_templates()
    selected_paths = run_template_tui(templates, remembered)
    if not selected_paths:
        raise SetupError("no templates selected")

    generated_block = build_generated_block(selected_paths)
    updated_gitignore = render_gitignore(args.gitignore, generated_block)

    if args.dry_run:
        print(updated_gitignore, end="")
        return 0

    args.gitignore.write_text(updated_gitignore, encoding="utf-8")
    save_selection(args.config, selected_paths)
    print(f"updated {args.gitignore} with {len(selected_paths)} template(s)")
    print(f"remembered selection in {args.config}")
    return 0


def load_selection(path: Path) -> list[str]:
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SetupError(f"{path} is not valid JSON") from error

    templates = data.get("templates")
    if not isinstance(templates, list) or not all(
        isinstance(template, str) for template in templates
    ):
        raise SetupError(f"{path} must contain a string array named `templates`")
    return templates


def save_selection(path: Path, selected_paths: list[str]) -> None:
    data = {
        "source": f"https://github.com/{GITIGNORE_REPO}",
        "branch": GITIGNORE_BRANCH,
        "templates": selected_paths,
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def fetch_templates() -> list[Template]:
    tree = request_json(TREE_URL)
    if tree.get("truncated"):
        raise SetupError("GitHub tree response was truncated; cannot list all templates")

    entries = tree.get("tree")
    if not isinstance(entries, list):
        raise SetupError("GitHub returned an unexpected tree response")

    templates = []
    for entry in entries:
        path = entry.get("path")
        if entry.get("type") == "blob" and isinstance(path, str):
            if path.endswith(".gitignore") and not path.startswith(".github/"):
                templates.append(Template(label=label_for_path(path), path=path))

    if not templates:
        raise SetupError("no .gitignore templates found in github/gitignore")

    return sorted(templates, key=lambda template: template.label.lower())


def label_for_path(path: str) -> str:
    stem = Path(path).name.removesuffix(".gitignore")
    if path.startswith("Global/"):
        return f"{stem} (Global)"
    if path.startswith("community/"):
        category = path.split("/", 2)[1]
        return f"{stem} (community/{category})"
    return stem


def run_template_tui(templates: list[Template], remembered: list[str]) -> list[str]:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise SetupError("setup-gitignore requires an interactive terminal")

    common_templates = [
        Template(label=label, path=path) for label, path in COMMON_TEMPLATES
    ]
    selected = set(remembered)

    return curses.wrapper(tui_main, common_templates, templates, selected)


def tui_main(
    screen,
    common_templates: list[Template],
    all_templates: list[Template],
    selected: set[str],
) -> list[str]:
    set_cursor_visible(False)
    screen.keypad(True)
    mode = "common"
    cursor = 0
    scroll = 0
    query = ""
    status = ""

    while True:
        visible = visible_items(mode, common_templates, all_templates, query)
        if cursor >= len(visible):
            cursor = max(0, len(visible) - 1)
        if scroll > cursor:
            scroll = cursor
        draw(screen, mode, visible, selected, cursor, scroll, query, status)
        key = screen.getch()
        status = ""

        if key in (ord("q"), 27):
            raise KeyboardInterrupt
        if key in (curses.KEY_UP, ord("k")):
            cursor = max(0, cursor - 1)
            scroll = min(scroll, cursor)
            continue
        if key in (curses.KEY_DOWN, ord("j")):
            if not visible:
                continue
            cursor = min(len(visible) - 1, cursor + 1)
            height = max(1, screen.getmaxyx()[0] - 8)
            if cursor >= scroll + height:
                scroll = cursor - height + 1
            continue
        if key in (curses.KEY_NPAGE,):
            if not visible:
                continue
            height = max(1, screen.getmaxyx()[0] - 8)
            cursor = min(len(visible) - 1, cursor + height)
            scroll = min(cursor, scroll + height)
            continue
        if key in (curses.KEY_PPAGE,):
            if not visible:
                continue
            height = max(1, screen.getmaxyx()[0] - 8)
            cursor = max(0, cursor - height)
            scroll = max(0, scroll - height)
            continue
        if key == ord(" "):
            if not visible:
                continue
            item = visible[cursor]
            if item.path == "__more__":
                mode = "all"
                cursor = 0
                scroll = 0
                continue
            toggle(selected, item.path)
            continue
        if key in (curses.KEY_ENTER, 10, 13):
            if mode == "common" and visible and visible[cursor].path == "__more__":
                mode = "all"
                cursor = 0
                scroll = 0
                continue
            return sorted(selected)
        if key == ord("/"):
            mode = "all"
            query = prompt(screen, "Filter templates: ")
            cursor = 0
            scroll = 0
            continue
        if key in (ord("c"), ord("C")):
            mode = "common"
            query = ""
            cursor = 0
            scroll = 0
            continue
        if key in (ord("a"), ord("A")):
            mode = "all"
            cursor = 0
            scroll = 0
            continue
        if key in (ord("r"), ord("R")):
            selected.clear()
            status = "Selection cleared"


def visible_items(
    mode: str,
    common_templates: list[Template],
    all_templates: list[Template],
    query: str,
) -> list[Template]:
    if mode == "common":
        return common_templates + [Template(label="More templates...", path="__more__")]

    normalized_query = query.strip().lower()
    if not normalized_query:
        return all_templates
    return [
        template
        for template in all_templates
        if normalized_query in template.label.lower()
        or normalized_query in template.path.lower()
    ]


def draw(
    screen,
    mode: str,
    visible: list[Template],
    selected: set[str],
    cursor: int,
    scroll: int,
    query: str,
    status: str,
) -> None:
    screen.erase()
    height, width = screen.getmaxyx()
    title = "setup-gitignore"
    subtitle = "Common templates" if mode == "common" else "All github/gitignore templates"
    if query:
        subtitle = f"{subtitle} | filter: {query}"

    add_line(screen, 0, 0, title, width, curses.A_BOLD)
    add_line(screen, 1, 0, subtitle, width)
    add_line(
        screen,
        2,
        0,
        "Space toggles, Enter writes, / filters, a all, c common, r reset, q quit",
        width,
    )
    add_line(screen, 3, 0, f"Selected: {len(selected)}", width)

    list_top = 5
    list_height = max(1, height - list_top - 2)
    for row, item in enumerate(visible[scroll : scroll + list_height]):
        index = scroll + row
        marker = ">" if index == cursor else " "
        checked = "*" if item.path in selected else " "
        if item.path == "__more__":
            checked = ">"
        text = f"{marker} [{checked}] {item.label}"
        attr = curses.A_REVERSE if index == cursor else curses.A_NORMAL
        add_line(screen, list_top + row, 0, text, width, attr)

    footer = status or f"{len(visible)} item(s)"
    add_line(screen, height - 1, 0, footer, width)
    screen.refresh()


def add_line(screen, y: int, x: int, text: str, width: int, attr: int = 0) -> None:
    if y >= screen.getmaxyx()[0] or width <= x + 1:
        return
    screen.addnstr(y, x, text.ljust(width), width - x - 1, attr)


def prompt(screen, label: str) -> str:
    curses.echo()
    set_cursor_visible(True)
    height, width = screen.getmaxyx()
    screen.move(height - 1, 0)
    screen.clrtoeol()
    screen.addnstr(height - 1, 0, label, width - 1)
    value = screen.getstr(height - 1, len(label), max(1, width - len(label) - 1))
    curses.noecho()
    set_cursor_visible(False)
    return value.decode("utf-8", errors="ignore")


def set_cursor_visible(visible: bool) -> None:
    try:
        curses.curs_set(1 if visible else 0)
    except curses.error:
        pass


def toggle(selected: set[str], path: str) -> None:
    if path in selected:
        selected.remove(path)
    else:
        selected.add(path)


def build_generated_block(selected_paths: list[str]) -> str:
    sections = [
        BEGIN_MARKER,
        "# Generated by setup-gitignore. Manual edits inside this block will be replaced.",
        f"# Source: https://github.com/{GITIGNORE_REPO}",
        "# Templates: " + ", ".join(selected_paths),
        "",
    ]

    for path in selected_paths:
        content = fetch_template_content(path).rstrip()
        sections.extend(
            [
                f"# ---- {path} ----",
                content,
                "",
            ]
        )

    sections.append(END_MARKER)
    return "\n".join(sections).rstrip() + "\n"


def fetch_template_content(path: str) -> str:
    quoted_path = quote(path)
    url = f"{RAW_BASE_URL}/{quoted_path}"
    with http_get(url) as response:
        return response.read().decode("utf-8")


def render_gitignore(path: Path, generated_block: str) -> str:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if not existing:
        return generated_block

    begin = existing.find(BEGIN_MARKER)
    end = existing.find(END_MARKER)
    if begin == -1 and end == -1:
        separator = "" if existing.endswith("\n\n") else "\n"
        if not existing.endswith("\n"):
            separator = "\n\n"
        return existing + separator + generated_block

    if begin == -1 or end == -1 or end < begin:
        raise SetupError(
            f"{path} contains incomplete setup-gitignore markers; fix them manually"
        )

    end += len(END_MARKER)
    before = existing[:begin].rstrip()
    after = existing[end:].lstrip("\n")
    parts = []
    if before:
        parts.append(before + "\n")
    parts.append(generated_block)
    if after:
        parts.append("\n" + after)
    return "".join(parts)


def request_json(url: str) -> dict:
    with http_get(url) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise SetupError("GitHub returned an unexpected JSON response")
    return data


def http_get(url: str):
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        return urlopen(request, timeout=60)
    except HTTPError as error:
        raise SetupError(f"request failed for {url}: HTTP {error.code}") from error
    except URLError as error:
        raise SetupError(f"request failed for {url}: {error.reason}") from error


class SetupError(Exception):
    pass
