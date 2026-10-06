from __future__ import annotations

import argparse
import os
import stat
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


DEFAULT_VIM_CONFIG = Path("~/.vimrc")
DEFAULT_OMP_CONFIG = Path("~/.omp/agent/config.yml")
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
        "--dry-run",
        action="store_true",
        help="Print destinations and config content without writing files.",
    )
    return parser


def setup_devcontainer_configs(args: argparse.Namespace) -> int:
    configs = [
        ConfigFile("Vim", args.vim_config.expanduser(), VIM_CONFIG, '"'),
        ConfigFile("Oh My Pi", args.omp_config.expanduser(), OMP_CONFIG, "#"),
    ]
    ensure_distinct_destinations(configs)
    rendered = [render_config(config) for config in configs]

    if args.dry_run:
        print_configs(rendered)
        return 0

    pending = [config for config in rendered if config.changed]
    if not pending:
        print("devcontainer config files are already installed")
        return 0

    for config in pending:
        write_atomically(config.spec.destination, config.rendered_content)
        print(f"updated {config.spec.name} config at {config.spec.destination}")
    return 0


def ensure_distinct_destinations(configs: list[ConfigFile]) -> None:
    destinations = [config.destination.resolve() for config in configs]
    if len(destinations) != len(set(destinations)):
        raise SetupError("Vim and Oh My Pi configs must use different destinations")


@dataclass(frozen=True)
class RenderedConfig:
    spec: ConfigFile
    rendered_content: str
    changed: bool


def render_config(config: ConfigFile) -> RenderedConfig:
    existing = read_config(config.destination)
    managed_block = (
        f"{config.begin_marker}\n{config.content.rstrip()}\n{config.end_marker}\n"
    )

    if existing is None or not existing:
        rendered = managed_block
    else:
        rendered = replace_or_append_block(existing, config, managed_block)

    return RenderedConfig(
        spec=config,
        rendered_content=rendered,
        changed=existing != rendered,
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
) -> str:
    lines = existing.splitlines(keepends=True)
    begin_lines = marker_line_indexes(lines, config.begin_marker)
    end_lines = marker_line_indexes(lines, config.end_marker)

    if not begin_lines and not end_lines:
        separator = "\n" if existing.endswith(("\n", "\r")) else "\n\n"
        return f"{existing}{separator}{managed_block}"

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

    return "".join(lines[:begin_line]) + managed_block + "".join(lines[end_line + 1 :])


def marker_line_indexes(lines: list[str], marker: str) -> list[int]:
    return [
        index
        for index, line in enumerate(lines)
        if line.rstrip("\r\n") == marker
    ]


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
