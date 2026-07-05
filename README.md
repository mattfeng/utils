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

Preview the release asset and install path without downloading:

```sh
uvx --from git+https://github.com/mattfeng/utils install-just --dry-run
```

Install a specific release tag:

```sh
uvx --from git+https://github.com/mattfeng/utils install-just --version 1.55.1
```
