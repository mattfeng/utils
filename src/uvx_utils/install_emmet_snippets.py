from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path


DEFAULT_OUTPUT = Path("~/.config/emmet/snippets.json")
SNIPPETS = {
    "html": {
        "snippets": {
            "tbl2": "table>thead>tr>th[scope=col]*2^^tbody>tr>td*2",
            "tbl3": "table>thead>tr>th[scope=col]*3^^tbody>tr>td*3",
            "tbl4": "table>thead>tr>th[scope=col]*4^^tbody>tr>td*4",
            "tblh": "table>thead>tr>th[scope=col]*3^^tbody>tr>th[scope=row]+td*2",
        }
    },
    "jsx": {"snippets": {}},
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return install_emmet_snippets(args)
    except InstallError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="install-emmet-snippets",
        description=(
            "Install custom table snippets for VS Code's built-in Emmet support."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Destination file. Defaults to {DEFAULT_OUTPUT}.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace a different snippets file that already exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the destination and snippets without writing files.",
    )
    return parser


def install_emmet_snippets(args: argparse.Namespace) -> int:
    destination = args.output.expanduser()
    content = json.dumps(SNIPPETS, indent=2) + "\n"

    if args.dry_run:
        print(f"destination: {destination}")
        print(content, end="")
        return 0

    if destination.exists():
        if destination.is_dir():
            raise InstallError(f"destination is a directory: {destination}")
        if file_contains_snippets(destination):
            print(f"Emmet snippets already installed at {destination}")
            print_vscode_next_step(destination.parent)
            return 0
        if not args.force:
            raise InstallError(
                f"{destination} already exists with different content; "
                "pass --force to replace it"
            )

    write_atomically(destination, content)
    print(f"installed Emmet snippets to {destination}")
    print_vscode_next_step(destination.parent)
    return 0


def file_contains_snippets(path: Path) -> bool:
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return existing == SNIPPETS


def write_atomically(destination: Path, content: str) -> None:
    temporary_path: Path | None = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, destination)
    except OSError as error:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise InstallError(f"could not write {destination}: {error}") from error


def print_vscode_next_step(extension_path: Path) -> None:
    print("next: add this to your VS Code settings.json:")
    settings = {
        "emmet.extensionsPath": [str(extension_path)],
        "emmet.includeLanguages": {"mdx": "javascriptreact"},
        "emmet.triggerExpansionOnTab": True,
    }
    print(json.dumps(settings, indent=2))


class InstallError(Exception):
    pass
