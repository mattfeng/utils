from __future__ import annotations

import argparse
import json
import sys
from importlib import resources
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


START_MARKER = "<!-- agents-md-templates:start -->"
END_MARKER = "<!-- agents-md-templates:end -->"
SELECTION_MARKER_PREFIX = "<!-- agents-md-templates:selected "
OPTIONS_MARKER_PREFIX = "<!-- agents-md-templates:options "
COMMENT_MARKER_SUFFIX = " -->"
TEMPLATE_SUFFIX = ".md"
BASE_TEMPLATE = "base"
COMMAND_NAME = "create-agents-md"
JAVASCRIPT_PACKAGE_MANAGERS = ("npm", "yarn")
JAVASCRIPT_TEMPLATES = {"nextjs", "shadcn"}
DEFAULT_JAVASCRIPT_PACKAGE_MANAGER = "yarn"
TEMPLATE_HIERARCHY = (
    ("general", (BASE_TEMPLATE,)),
    (
        "ecosystem",
        (
            "python",
            "fastapi",
            "sqlalchemy-alembic",
            "css",
            "nextjs",
            "shadcn",
            "markdown-mdx",
        ),
    ),
    ("domain", ("deep-learning",)),
    ("framework", ("jax-equinox", "pytorch")),
)
TEMPLATE_ORDER = {
    name: (level, position)
    for level, (_category, names) in enumerate(TEMPLATE_HIERARCHY)
    for position, name in enumerate(names)
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=COMMAND_NAME,
        description="Generate and update AGENTS.md files from bundled templates.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path.cwd(),
        help="project directory or AGENTS.md path to write (default: current directory)",
    )
    parser.add_argument(
        "--template",
        action="append",
        choices=template_names(),
        help="template to include; repeat for multiple templates (skips template prompt)",
    )
    parser.add_argument(
        "--javascript-package-manager",
        choices=JAVASCRIPT_PACKAGE_MANAGERS,
        help="JavaScript package manager to use in JavaScript templates",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="replace the entire AGENTS.md file instead of updating the managed block",
    )
    parser.set_defaults(func=write_command)

    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="list bundled templates")
    list_parser.set_defaults(func=list_command)

    return parser


def list_command(_args: argparse.Namespace) -> int:
    for name in template_names():
        print(name)
    return 0


def write_command(args: argparse.Namespace) -> int:
    target = args.target.resolve()
    output_path = target if target.name == "AGENTS.md" else target / "AGENTS.md"
    project_dir = output_path.parent
    current = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    context = {
        "output_path": str(output_path),
        "project_dir": str(project_dir),
        "javascript_package_manager": DEFAULT_JAVASCRIPT_PACKAGE_MANAGER,
    }

    previous = previous_selected_templates(current, context=context)
    previous_options = previous_options_from_metadata(current_managed_block(current) or "")
    selected = select_templates(explicit=args.template, defaults=previous)
    context["javascript_package_manager"] = select_javascript_package_manager(
        selected=selected,
        explicit=args.javascript_package_manager,
        default=previous_options.get("javascript_package_manager"),
    )
    generated = render_managed_block(
        selected,
        context=context,
    )

    if args.replace:
        next_content = generated + "\n"
    else:
        next_content = upsert_managed_block(current, generated)

    print(next_content, end="")
    sys.stdout.flush()

    project_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(next_content, encoding="utf-8")
    print(f"\nWrote {output_path} with templates: {', '.join(selected)}", file=sys.stderr)
    return 0


def select_templates(
    *,
    explicit: list[str] | None,
    defaults: list[str] | None = None,
) -> list[str]:
    selected: list[str] = []

    def add(name: str) -> None:
        if name not in selected:
            selected.append(name)

    if explicit:
        for name in explicit:
            add(name)

    if not explicit:
        selected = prompt_for_templates(defaults=defaults)

    if not selected:
        add(BASE_TEMPLATE)

    return order_templates(selected)


def prompt_for_templates(*, defaults: list[str] | None) -> list[str]:
    selected: list[str] = []
    default_templates = set(defaults) if defaults is not None else {BASE_TEMPLATE}

    print("Select templates to include in AGENTS.md:", file=sys.stderr)
    for name in template_names():
        default = name in default_templates
        if confirm(f"Include {name}?", default=default):
            selected.append(name)

    return selected


def select_javascript_package_manager(
    *,
    selected: list[str],
    explicit: str | None,
    default: str | None,
) -> str:
    if explicit is not None:
        return explicit

    default = (
        default
        if default in JAVASCRIPT_PACKAGE_MANAGERS
        else DEFAULT_JAVASCRIPT_PACKAGE_MANAGER
    )

    if not JAVASCRIPT_TEMPLATES.intersection(selected):
        return default

    return prompt_for_choice(
        "Which JavaScript package manager are you using?",
        choices=JAVASCRIPT_PACKAGE_MANAGERS,
        default=default,
    )


def prompt_for_choice(prompt: str, *, choices: tuple[str, ...], default: str) -> str:
    choices_text = "/".join(choices)

    while True:
        print(
            f"{prompt} ({choices_text}) [{default}] ",
            end="",
            file=sys.stderr,
            flush=True,
        )
        answer = sys.stdin.readline().strip().lower()
        if not answer:
            return default
        if answer in choices:
            return answer
        print(f"Please answer one of: {choices_text}.", file=sys.stderr)


def confirm(prompt: str, *, default: bool) -> bool:
    suffix = " [Y/n] " if default else " [y/N] "

    while True:
        print(prompt + suffix, end="", file=sys.stderr, flush=True)
        answer = sys.stdin.readline().strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer y or n.", file=sys.stderr)


def render_managed_block(selected: list[str], *, context: dict[str, object]) -> str:
    selected = order_templates(selected)
    context = {**context, "selected_templates": selected}
    chunks = [
        START_MARKER,
        f"<!-- Generated by `{COMMAND_NAME}`; edit templates or content outside this block. -->",
        selected_templates_comment(selected),
    ]
    options_comment = selected_options_comment(selected, context)
    if options_comment is not None:
        chunks.append(options_comment)
    chunks.extend(render_template(name, context=context) for name in selected)
    chunks.append(END_MARKER)
    return "\n\n".join(chunks).strip()


def render_template(name: str, *, context: dict[str, object]) -> str:
    template = template_environment().get_template(template_filename(name))
    return template.render({**context, "template_name": name}).strip()


def upsert_managed_block(current: str, generated: str) -> str:
    start = current.find(START_MARKER)
    end = current.find(END_MARKER)

    if start != -1 and end != -1 and start < end:
        end += len(END_MARKER)
        return current[:start] + generated + current[end:]

    if not current:
        return generated + "\n"

    return f"{current}\n\n{generated}\n"


def selected_templates_comment(selected: list[str]) -> str:
    return f"{SELECTION_MARKER_PREFIX}{json.dumps(selected)}{COMMENT_MARKER_SUFFIX}"


def selected_options_comment(
    selected: list[str],
    context: dict[str, object],
) -> str | None:
    if not JAVASCRIPT_TEMPLATES.intersection(selected):
        return None

    options = {
        "javascript_package_manager": context["javascript_package_manager"],
    }
    return f"{OPTIONS_MARKER_PREFIX}{json.dumps(options, sort_keys=True)}{COMMENT_MARKER_SUFFIX}"


def previous_selected_templates(
    current: str,
    *,
    context: dict[str, object],
) -> list[str] | None:
    managed = current_managed_block(current)
    if managed is None:
        return None

    metadata_selection = selected_templates_from_metadata(managed)
    if metadata_selection is not None:
        return metadata_selection

    inferred_selection = infer_selected_templates(managed, context=context)
    if inferred_selection:
        return inferred_selection

    return None


def previous_options_from_metadata(managed: str) -> dict[str, str]:
    for line in managed.splitlines():
        line = line.strip()
        if not line.startswith(OPTIONS_MARKER_PREFIX):
            continue
        if not line.endswith(COMMENT_MARKER_SUFFIX):
            continue

        payload = line[len(OPTIONS_MARKER_PREFIX) : -len(COMMENT_MARKER_SUFFIX)]
        try:
            options = json.loads(payload)
        except json.JSONDecodeError:
            return {}

        if not isinstance(options, dict):
            return {}

        javascript_package_manager = options.get("javascript_package_manager")
        if javascript_package_manager not in JAVASCRIPT_PACKAGE_MANAGERS:
            return {}

        return {"javascript_package_manager": javascript_package_manager}

    if "Assume the user is using npm." in managed:
        return {"javascript_package_manager": "npm"}
    if "Assume the user is using Yarn" in managed:
        return {"javascript_package_manager": "yarn"}

    return {}


def current_managed_block(current: str) -> str | None:
    start = current.find(START_MARKER)
    end = current.find(END_MARKER)

    if start == -1 or end == -1 or start >= end:
        return None

    end += len(END_MARKER)
    return current[start:end]


def selected_templates_from_metadata(managed: str) -> list[str] | None:
    available = set(template_names())

    for line in managed.splitlines():
        line = line.strip()
        if not line.startswith(SELECTION_MARKER_PREFIX):
            continue
        if not line.endswith(COMMENT_MARKER_SUFFIX):
            continue

        payload = line[len(SELECTION_MARKER_PREFIX) : -len(COMMENT_MARKER_SUFFIX)]
        try:
            names = json.loads(payload)
        except json.JSONDecodeError:
            return None

        if not isinstance(names, list):
            return None

        selected = [name for name in names if isinstance(name, str) and name in available]
        return order_templates(selected)

    return None


def infer_selected_templates(
    managed: str,
    *,
    context: dict[str, object],
) -> list[str]:
    selected: list[str] = []

    for name in template_names():
        rendered = render_template(name, context=context)
        heading = template_heading(rendered)
        if rendered and (rendered in managed or heading in managed):
            selected.append(name)

    return order_templates(selected)


def template_heading(rendered: str) -> str:
    for line in rendered.splitlines():
        if line.startswith("# "):
            return line
    return rendered


def template_names() -> list[str]:
    names: list[str] = []
    for path in templates_dir().iterdir():
        if path.is_file() and path.name.endswith(TEMPLATE_SUFFIX):
            names.append(path.name.removesuffix(TEMPLATE_SUFFIX))
    return order_templates(names)


def order_templates(names: list[str]) -> list[str]:
    return sorted(names, key=template_sort_key)


def template_sort_key(name: str) -> tuple[int, int, str]:
    level, position = TEMPLATE_ORDER.get(name, (len(TEMPLATE_HIERARCHY), 0))
    return (level, position, name)


def template_filename(name: str) -> str:
    return f"{name}{TEMPLATE_SUFFIX}"


def template_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(templates_dir()),
        autoescape=False,
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )


def templates_dir() -> Path:
    return Path(str(resources.files("uvx_utils") / "templates" / "agents"))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
