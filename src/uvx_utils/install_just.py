from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import stat
import sys
import tarfile
import tempfile
from collections.abc import Sequence
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GITHUB_API = "https://api.github.com/repos/casey/just"
DEFAULT_INSTALL_DIR = Path("~/.local/bin").expanduser()
USER_AGENT = "mattfeng-utils/install-just"


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return install_just(args)
    except InstallError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="install-just",
        description="Install the latest casey/just release on Ubuntu/Linux.",
    )
    parser.add_argument(
        "--install-dir",
        type=Path,
        default=DEFAULT_INSTALL_DIR,
        help=f"Directory to install `just` into. Defaults to {DEFAULT_INSTALL_DIR}.",
    )
    parser.add_argument(
        "--version",
        help=(
            "Install a specific release tag instead of the latest release. "
            "Example: 1.55.1"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be installed without downloading or writing files.",
    )
    return parser


def install_just(args: argparse.Namespace) -> int:
    require_linux()

    release = fetch_release(args.version)
    asset = select_linux_asset(release)
    install_dir = args.install_dir.expanduser()
    install_path = install_dir / "just"

    if args.dry_run:
        print(f"release: {release['tag_name']}")
        print(f"asset: {asset['name']}")
        print(f"install_path: {install_path}")
        print(f"url: {asset['browser_download_url']}")
        return 0

    install_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix=".install-just-",
        dir=install_dir,
    ) as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        archive_path = temp_dir / asset["name"]
        binary_path = temp_dir / "just"

        download_file(asset["browser_download_url"], archive_path)
        extract_just_binary(archive_path, binary_path)
        make_executable(binary_path)
        os.replace(binary_path, install_path)

    print(f"installed just {release['tag_name']} to {install_path}")
    warn_if_not_on_path(install_dir)
    return 0


def require_linux() -> None:
    if platform.system() != "Linux":
        raise InstallError("install-just currently supports Linux only")


def fetch_release(version: str | None) -> dict:
    if version:
        tag = version.removeprefix("v")
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
        raise InstallError(f"no Linux archive found for just {release['tag_name']}")

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
        lower_name.startswith("just-")
        and "unknown-linux" in lower_name
        and (lower_name.endswith(".tar.gz") or lower_name.endswith(".tgz"))
    )


def target_triples_for_machine(machine: str) -> list[str]:
    normalized = machine.lower()
    if normalized in {"x86_64", "amd64"}:
        return [
            "x86_64-unknown-linux-musl",
            "x86_64-unknown-linux-gnu",
            "x86_64-unknown-linux",
        ]
    if normalized in {"aarch64", "arm64"}:
        return [
            "aarch64-unknown-linux-musl",
            "aarch64-unknown-linux-gnu",
            "aarch64-unknown-linux",
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


def extract_just_binary(archive_path: Path, destination: Path) -> None:
    with tarfile.open(archive_path, mode="r:*") as archive:
        for member in archive.getmembers():
            if Path(member.name).name != "just" or not member.isfile():
                continue

            source = archive.extractfile(member)
            if source is None:
                continue

            with source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)
            return

    raise InstallError(f"archive did not contain a `just` binary: {archive_path.name}")


def make_executable(path: Path) -> None:
    current_mode = path.stat().st_mode
    path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def warn_if_not_on_path(directory: Path) -> None:
    path_entries = [
        Path(entry).expanduser() for entry in os.environ.get("PATH", "").split(":")
    ]
    if directory not in path_entries:
        print(f"warning: {directory} is not on PATH", file=sys.stderr)


class InstallError(Exception):
    pass
