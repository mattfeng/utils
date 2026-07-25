from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import secrets
import shlex
import string
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path


DEFAULT_OUTPUT_PATH = Path("compose.yaml")
DEFAULT_ENV_FILENAME = ".env.compose"
DEFAULT_POSTGRES_IMAGE = "postgres:18-alpine"
DEFAULT_MONGODB_IMAGE = "mongo:8.0"
GENERATED_PASSWORD_LENGTH = 32

SERVICE_ALIASES = {
    "1": "postgres",
    "postgres": "postgres",
    "postgresql": "postgres",
    "pg": "postgres",
    "2": "mongodb",
    "mongo": "mongodb",
    "mongodb": "mongodb",
}
SERVICE_ORDER = ("postgres", "mongodb")

IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,62}")
IMAGE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:@-]{0,254}")
PASSWORD_PATTERN = re.compile(r"[A-Za-z0-9._~-]{8,128}")
PASSWORD_ALPHABET = string.ascii_letters + string.digits + "._~-"


@dataclass(frozen=True)
class PostgresConfig:
    image: str
    host_port: int
    database: str
    username: str
    password: str


@dataclass(frozen=True)
class MongoDBConfig:
    image: str
    host_port: int
    database: str
    root_username: str
    root_password: str


@dataclass(frozen=True)
class ComposeConfig:
    bind_address: str
    postgres: PostgresConfig | None = None
    mongodb: MongoDBConfig | None = None


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return setup_compose(args)
    except SetupError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("cancelled", file=sys.stderr)
        return 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="setup-compose",
        description=(
            "Interactively generate a Docker Compose stack for backend services."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Compose file to write. Defaults to {DEFAULT_OUTPUT_PATH}.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help=(
            "Credential environment file to write. Defaults to .env.compose next "
            "to the Compose file."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing output files without asking for confirmation.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview both generated files without writing them.",
    )
    return parser


def setup_compose(args: argparse.Namespace) -> int:
    require_interactive_terminal()
    output_path, env_path = resolve_output_paths(args.output, args.env_file)

    selected = prompt_for_services()
    config = prompt_for_configuration(selected)
    env_reference = relative_env_reference(output_path, env_path)
    compose_content = render_compose(config, env_reference)
    env_content = render_env_file(config)

    if args.dry_run:
        print_preview(output_path, compose_content, env_path, env_content)
        return 0

    ensure_writable_targets((output_path, env_path))
    existing = [
        path
        for path in (output_path, env_path)
        if path.exists() or path.is_symlink()
    ]
    if existing and not args.force and not confirm_overwrite(existing):
        print("cancelled")
        return 0

    atomic_write(env_path, env_content, mode=0o600)
    atomic_write(output_path, compose_content, mode=0o644)

    print(f"created {output_path}")
    print(f"created {env_path} (credentials; file mode 0600)")
    print(f"next: {compose_up_command(output_path)}")
    print(f"remember to add {env_path} to .gitignore")
    return 0


def resolve_output_paths(output_path: Path, env_path: Path | None) -> tuple[Path, Path]:
    output = output_path.expanduser()
    env = env_path.expanduser() if env_path else output.parent / DEFAULT_ENV_FILENAME

    if os.path.abspath(output) == os.path.abspath(env):
        raise SetupError("the Compose file and credential environment file must differ")
    return output, env


def require_interactive_terminal() -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise SetupError("setup-compose requires an interactive terminal")


def prompt_for_services() -> list[str]:
    print("Select backend services (comma-separated):")
    print("  1. PostgreSQL")
    print("  2. MongoDB")

    while True:
        raw = ask("Services [1,2]: ").strip()
        if not raw:
            return list(SERVICE_ORDER)

        tokens = [token for token in re.split(r"[\s,]+", raw.lower()) if token]
        selected: set[str] = set()
        unknown = []
        for token in tokens:
            service = SERVICE_ALIASES.get(token)
            if service is None:
                unknown.append(token)
            else:
                selected.add(service)

        if unknown:
            print(f"Unknown service selection: {', '.join(unknown)}")
            continue
        if not selected:
            print("Select at least one service.")
            continue
        return [service for service in SERVICE_ORDER if service in selected]


def prompt_for_configuration(selected: list[str]) -> ComposeConfig:
    local_only = ask_yes_no("Bind published ports to localhost only?", default=True)
    bind_address = "127.0.0.1" if local_only else "0.0.0.0"
    used_ports: set[int] = set()

    postgres = None
    if "postgres" in selected:
        print("\nPostgreSQL")
        postgres = PostgresConfig(
            image=prompt_value(
                "Image",
                DEFAULT_POSTGRES_IMAGE,
                validate_image,
                "a valid image reference",
            ),
            host_port=prompt_port("Host port", 5432, used_ports),
            database=prompt_identifier("Database", "app"),
            username=prompt_identifier("Username", "app"),
            password=prompt_password("Password"),
        )
        used_ports.add(postgres.host_port)

    mongodb = None
    if "mongodb" in selected:
        print("\nMongoDB")
        mongodb = MongoDBConfig(
            image=prompt_value(
                "Image",
                DEFAULT_MONGODB_IMAGE,
                validate_image,
                "a valid image reference",
            ),
            host_port=prompt_port("Host port", 27017, used_ports),
            database=prompt_identifier("Initial database", "app"),
            root_username=prompt_identifier("Root username", "root"),
            root_password=prompt_password("Root password"),
        )

    return ComposeConfig(
        bind_address=bind_address,
        postgres=postgres,
        mongodb=mongodb,
    )


def ask(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError as error:
        raise SetupError("interactive input ended unexpectedly") from error


def ask_yes_no(question: str, *, default: bool) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = ask(f"{question} {suffix}: ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Enter yes or no.")


def prompt_value(
    label: str,
    default: str,
    validator: Callable[[str], bool],
    expectation: str,
) -> str:
    while True:
        value = ask(f"{label} [{default}]: ").strip() or default
        if validator(value):
            return value
        print(f"Enter {expectation}.")


def prompt_identifier(label: str, default: str) -> str:
    return prompt_value(
        label,
        default,
        validate_identifier,
        "1-63 letters, digits, or underscores, starting with a letter or underscore",
    )


def prompt_port(label: str, default: int, used_ports: set[int]) -> int:
    while True:
        value = ask(f"{label} [{default}]: ").strip()
        if not value:
            port = default
        else:
            try:
                port = int(value)
            except ValueError:
                print("Enter a port number from 1 to 65535.")
                continue

        if not 1 <= port <= 65535:
            print("Enter a port number from 1 to 65535.")
            continue
        if port in used_ports:
            print(f"Port {port} is already assigned to another selected service.")
            continue
        return port


def prompt_password(label: str) -> str:
    while True:
        try:
            value = getpass.getpass(f"{label} [generate securely]: ").strip()
        except EOFError as error:
            raise SetupError("interactive input ended unexpectedly") from error

        if not value:
            return generate_password()
        if validate_password(value):
            return value
        print(
            "Use 8-128 letters, digits, or URL-safe punctuation characters: . _ ~ -"
        )


def validate_identifier(value: str) -> bool:
    return IDENTIFIER_PATTERN.fullmatch(value) is not None


def validate_image(value: str) -> bool:
    return IMAGE_PATTERN.fullmatch(value) is not None


def validate_password(value: str) -> bool:
    return PASSWORD_PATTERN.fullmatch(value) is not None


def generate_password() -> str:
    return "".join(
        secrets.choice(PASSWORD_ALPHABET) for _ in range(GENERATED_PASSWORD_LENGTH)
    )


def render_compose(config: ComposeConfig, env_reference: str) -> str:
    lines = [
        "# Generated by setup-compose.",
        f"# Credentials are stored in {env_reference}.",
        "services:",
    ]

    if config.postgres:
        postgres = config.postgres
        healthcheck = [
            "CMD-SHELL",
            'pg_isready -U "$${POSTGRES_USER}" -d "$${POSTGRES_DB}"',
        ]
        lines.extend(
            [
                "  postgres:",
                f"    image: {yaml_string(postgres.image)}",
                "    restart: unless-stopped",
                "    env_file:",
                f"      - {yaml_string(env_reference)}",
                "    ports:",
                "      - "
                + yaml_string(f"{config.bind_address}:{postgres.host_port}:5432"),
                "    volumes:",
                f"      - postgres_data:{postgres_volume_target(postgres.image)}",
                "    healthcheck:",
                f"      test: {json.dumps(healthcheck)}",
                "      interval: 5s",
                "      timeout: 5s",
                "      retries: 10",
                "      start_period: 10s",
            ]
        )

    if config.mongodb:
        mongodb = config.mongodb
        healthcheck_command = (
            "mongosh --quiet --eval \"db.adminCommand('ping').ok\" "
            '--username "$${MONGO_INITDB_ROOT_USERNAME}" '
            '--password "$${MONGO_INITDB_ROOT_PASSWORD}" '
            "--authenticationDatabase admin"
        )
        lines.extend(
            [
                "  mongodb:",
                f"    image: {yaml_string(mongodb.image)}",
                "    restart: unless-stopped",
                "    env_file:",
                f"      - {yaml_string(env_reference)}",
                "    ports:",
                "      - "
                + yaml_string(f"{config.bind_address}:{mongodb.host_port}:27017"),
                "    volumes:",
                "      - mongodb_data:/data/db",
                "    healthcheck:",
                f"      test: {json.dumps(['CMD-SHELL', healthcheck_command])}",
                "      interval: 5s",
                "      timeout: 5s",
                "      retries: 10",
                "      start_period: 10s",
            ]
        )

    lines.extend(["", "volumes:"])
    if config.postgres:
        lines.append("  postgres_data:")
    if config.mongodb:
        lines.append("  mongodb_data:")
    return "\n".join(lines) + "\n"


def postgres_volume_target(image: str) -> str:
    tag = image.rsplit("/", 1)[-1].partition(":")[2].partition("@")[0]
    if not tag or tag == "latest":
        return "/var/lib/postgresql"

    match = re.match(r"(\d+)", tag)
    if match and int(match.group(1)) < 18:
        return "/var/lib/postgresql/data"
    return "/var/lib/postgresql"


def render_env_file(config: ComposeConfig) -> str:
    lines = [
        "# Generated by setup-compose. Keep this file out of version control.",
    ]
    if config.postgres:
        postgres = config.postgres
        lines.extend(
            [
                f"POSTGRES_USER={postgres.username}",
                f"POSTGRES_PASSWORD={postgres.password}",
                f"POSTGRES_DB={postgres.database}",
            ]
        )
    if config.mongodb:
        if config.postgres:
            lines.append("")
        mongodb = config.mongodb
        lines.extend(
            [
                f"MONGO_INITDB_ROOT_USERNAME={mongodb.root_username}",
                f"MONGO_INITDB_ROOT_PASSWORD={mongodb.root_password}",
                f"MONGO_INITDB_DATABASE={mongodb.database}",
            ]
        )
    return "\n".join(lines) + "\n"


def yaml_string(value: str) -> str:
    return json.dumps(value)


def relative_env_reference(output_path: Path, env_path: Path) -> str:
    output_parent = os.path.abspath(output_path.parent)
    absolute_env = os.path.abspath(env_path)
    try:
        relative = os.path.relpath(absolute_env, start=output_parent)
    except ValueError:
        return Path(absolute_env).as_posix()
    return Path(relative).as_posix()


def ensure_writable_targets(paths: Sequence[Path]) -> None:
    for path in paths:
        if path.exists() and path.is_dir():
            raise SetupError(f"output target is a directory: {path}")


def confirm_overwrite(paths: list[Path]) -> bool:
    print("The following file(s) already exist:")
    for path in paths:
        print(f"  {path}")
    return ask_yes_no("Replace them?", default=False)


def atomic_write(path: Path, content: str, *, mode: int) -> None:
    temp_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as output:
            output.write(content)
            temp_path = Path(output.name)
        temp_path.chmod(mode)
        os.replace(temp_path, path)
    except OSError as error:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise SetupError(f"could not write {path}: {error}") from error


def print_preview(
    output_path: Path,
    compose_content: str,
    env_path: Path,
    env_content: str,
) -> None:
    print(f"# --- {output_path} ---")
    print(compose_content, end="")
    print(f"\n# --- {env_path} ---")
    print(env_content, end="")


def compose_up_command(output_path: Path) -> str:
    if output_path == DEFAULT_OUTPUT_PATH:
        return "docker compose up -d"
    return f"docker compose -f {shlex.quote(str(output_path))} up -d"


class SetupError(Exception):
    pass
