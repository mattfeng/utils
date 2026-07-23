# mattfeng-utils

Small stdlib-only utility CLIs designed to run directly with `uvx`.

## Install latest just

Install the latest release of [`casey/just`](https://github.com/casey/just) on Ubuntu/Linux:

```sh
uvx --from git+https://github.com/mattfeng/utils install-just
```

By default this installs `just` into `~/.local/bin/just`.

```sh
uvx --from git+https://github.com/mattfeng/utils install-just --install-dir ~/.local/bin
```

Install system-wide into `/usr/local/bin/just`:

```sh
uvx --from git+https://github.com/mattfeng/utils install-just --system
```

If `/usr/local/bin` is not writable, the installer uses `sudo install` for the
final copy.

Preview the release asset and install path without downloading:

```sh
uvx --from git+https://github.com/mattfeng/utils install-just --dry-run
```

Install a specific release tag:

```sh
uvx --from git+https://github.com/mattfeng/utils install-just --version 1.55.1
```

## Install latest jj

Install the latest release of [`jj-vcs/jj`](https://github.com/jj-vcs/jj) on
Ubuntu/Linux:

```sh
uvx --from git+https://github.com/mattfeng/utils install-jj
```

By default this installs `jj` into `~/.local/bin/jj`.

```sh
uvx --from git+https://github.com/mattfeng/utils install-jj --install-dir ~/.local/bin
```

Install system-wide into `/usr/local/bin/jj`:

```sh
uvx --from git+https://github.com/mattfeng/utils install-jj --system
```

If `/usr/local/bin` is not writable, the installer uses `sudo install` for the
final copy.

Preview the release asset and install path without downloading:

```sh
uvx --from git+https://github.com/mattfeng/utils install-jj --dry-run
```

Install a specific release tag:

```sh
uvx --from git+https://github.com/mattfeng/utils install-jj --version v0.43.0
```

## Set up .gitignore

Select templates from [`github/gitignore`](https://github.com/github/gitignore) and
write a generated block to `.gitignore` while preserving manual edits outside that
block:

```sh
uvx --from git+https://github.com/mattfeng/utils setup-gitignore
```

The TUI starts with common templates: macOS, Python, and Linux. Choose
`More templates...` or press `a` to browse the comprehensive list.

The selected templates are remembered in `.gitignore-templates.json` and are
preselected the next time you run the command. Manual `.gitignore` edits outside
the generated block are preserved every time.
