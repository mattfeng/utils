from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Sequence
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GITHUB_API = "https://api.github.com/repos/jj-vcs/jj"
DEFAULT_INSTALL_DIR = Path("~/.local/bin").expanduser()
SYSTEM_INSTALL_DIR = Path("/usr/local/bin")
USER_AGENT = "mattfeng-utils/install-jj"


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return install_jj(args)
    except InstallError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="install-jj",
        description="Install the latest jj-vcs/jj release on Ubuntu/Linux.",
    )
    parser.add_argument(
        "--install-dir",
        type=Path,
        default=None,
        help=f"Directory to install `jj` into. Defaults to {DEFAULT_INSTALL_DIR}.",
    )
    parser.add_argument(
        "--system",
        action="store_true",
        help=f"Install system-wide into {SYSTEM_INSTALL_DIR}/jj.",
    )
    parser.add_argument(
        "--version",
        help=(
            "Install a specific release tag instead of the latest release. "
            "Example: v0.43.0"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be installed without downloading or writing files.",
    )
    return parser


def install_jj(args: argparse.Namespace) -> int:
    require_linux()

    release = fetch_release(args.version)
    asset = select_linux_asset(release)
    install_dir = resolve_install_dir(args)
    install_path = install_dir / "jj"

    if args.dry_run:
        print(f"release: {release['tag_name']}")
        print(f"asset: {asset['name']}")
        print(f"install_path: {install_path}")
        print(f"url: {asset['browser_download_url']}")
        return 0

    with tempfile.TemporaryDirectory(prefix="install-jj-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        archive_path = temp_dir / asset["name"]
        binary_path = temp_dir / "jj"

        download_file(asset["browser_download_url"], archive_path)
        extract_jj_binary(archive_path, binary_path)
        make_executable(binary_path)
        install_binary(binary_path, install_path, system=args.system)

    print(f"installed jj {release['tag_name']} to {install_path}")
    if not args.system:
        warn_if_not_on_path(install_dir)
    return 0


def resolve_install_dir(args: argparse.Namespace) -> Path:
    if args.system and args.install_dir is not None:
        raise InstallError("use either --system or --install-dir, not both")
    if args.system:
        return SYSTEM_INSTALL_DIR
    if args.install_dir is not None:
        return args.install_dir.expanduser()
    return DEFAULT_INSTALL_DIR


def require_linux() -> None:
    if platform.system() != "Linux":
        raise InstallError("install-jj currently supports Linux only")


def fetch_release(version: str | None) -> dict:
    if version:
        tag = version if version.startswith("v") else f"v{version}"
        url = f"{GITHUB_API}/releases/tags/{tag}"
    else:
        url = f"{GITHUB_API}/releases/latest"

    with http_get(url) as response:
        payload = response.read().decode("utf-8")

    release = json.loads(payload)
    if "tag_name" not in release or "assets" not in release:
        raise InstallError("GitHub returned an unexpected release response")
    return release


def select_linux_asset(release: dict) -> dict:
    candidates = [
        asset
        for asset in release.get("assets", [])
        if is_linux_archive(asset.get("name", ""))
    ]
    if not candidates:
        raise InstallError(f"no Linux archive found for jj {release['tag_name']}")

    target_order = target_triples_for_machine(platform.machine())
    for target in target_order:
        for asset in candidates:
            if target in asset["name"].lower():
                return asset

    names = ", ".join(asset["name"] for asset in candidates)
    raise InstallError(
        f"no supported Linux archive found for architecture "
        f"{platform.machine()!r}; available Linux archives: {names}"
    )


def is_linux_archive(name: str) -> bool:
    lower_name = name.lower()
    return (
        lower_name.startswith("jj-")
        and "linux" in lower_name
        and not lower_name.endswith(".sha256")
        and (lower_name.endswith(".tar.gz") or lower_name.endswith(".tgz"))
    )


def target_triples_for_machine(machine: str) -> list[str]:
    normalized = machine.lower()
    if normalized in {"x86_64", "amd64"}:
        return [
            "x86_64-unknown-linux-musl",
            "x86_64-unknown-linux-gnu",
            "x86_64-unknown-linux",
            "x86_64-linux",
        ]
    if normalized in {"aarch64", "arm64"}:
        return [
            "aarch64-unknown-linux-musl",
            "aarch64-unknown-linux-gnu",
            "aarch64-unknown-linux",
            "aarch64-linux",
        ]
    raise InstallError(f"unsupported architecture: {machine}")


def download_file(url: str, destination: Path) -> None:
    with http_get(url) as response:
        with destination.open("wb") as output:
            shutil.copyfileobj(response, output)


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
        raise InstallError(f"request failed for {url}: HTTP {error.code}") from error
    except URLError as error:
        raise InstallError(f"request failed for {url}: {error.reason}") from error


def extract_jj_binary(archive_path: Path, destination: Path) -> None:
    with tarfile.open(archive_path, mode="r:*") as archive:
        for member in archive.getmembers():
            if Path(member.name).name != "jj" or not member.isfile():
                continue

            source = archive.extractfile(member)
            if source is None:
                continue

            with source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)
            return

    raise InstallError(f"archive did not contain a `jj` binary: {archive_path.name}")


def make_executable(path: Path) -> None:
    current_mode = path.stat().st_mode
    path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def install_binary(source: Path, destination: Path, *, system: bool) -> None:
    if not system:
        install_direct(source, destination)
        return

    if can_write_to_directory(destination.parent):
        try:
            install_direct(source, destination)
            return
        except InstallError:
            pass

    install_with_sudo(source, destination)


def install_direct(source: Path, destination: Path) -> None:
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)
    except OSError as error:
        raise InstallError(f"could not install to {destination}: {error}") from error


def install_with_sudo(source: Path, destination: Path) -> None:
    command = ["sudo", "install", "-D", "-m", "755", str(source), str(destination)]
    try:
        completed = subprocess.run(command, check=False)
    except FileNotFoundError as error:
        raise InstallError("sudo is required for --system but was not found") from error

    if completed.returncode != 0:
        raise InstallError("system-wide install failed")


def can_write_to_directory(directory: Path) -> bool:
    if directory.exists():
        return os.access(directory, os.W_OK)

    parent = directory.parent
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    return os.access(parent, os.W_OK)


def warn_if_not_on_path(directory: Path) -> None:
    path_entries = [
        Path(entry).expanduser() for entry in os.environ.get("PATH", "").split(":")
    ]
    if directory not in path_entries:
        print(f"warning: {directory} is not on PATH", file=sys.stderr)


class InstallError(Exception):
    pass
