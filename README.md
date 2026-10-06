# mattfeng-utils

Small stdlib-only utility CLIs designed to run directly with `uvx`.

## Install custom Emmet snippets

Install the table snippets into `~/.config/emmet/snippets.json`:

```sh
uvx --from git+https://github.com/mattfeng/utils install-emmet-snippets
```

The installer does not replace a different existing `snippets.json` by default.
Inspect and back up that file if needed, then pass `--force` to replace it. To
preview the destination and generated JSON without writing anything, use
`--dry-run`.

In VS Code, open the Command Palette, run **Preferences: Open User Settings
(JSON)**, and add these settings to the top-level settings object:

```jsonc
{
  "emmet.extensionsPath": [
    "/home/mattfeng/.config/emmet"
  ],
  "emmet.includeLanguages": {
    "mdx": "javascriptreact"
  },
  "emmet.triggerExpansionOnTab": true
}
```

If your home directory is not `/home/mattfeng`, replace that path with the
absolute path printed by the installer. Reload the VS Code window after changing
the setting. In an HTML file, type `tbl2`, `tbl3`, `tbl4`, or `tblh` and press
Tab to expand the snippet. The `emmet.includeLanguages` mapping also enables
Emmet's JavaScript React behavior in MDX files. See the
[VS Code Emmet documentation](https://code.visualstudio.com/docs/languages/emmet)
for more about custom snippets and language mappings.

## Install an Oh My Zsh plugin

Choose a plugin from this repository's `zsh-plugins` directory in an interactive
terminal UI and copy it into your Oh My Zsh custom plugins directory:

```sh
uvx --from git+https://github.com/mattfeng/utils install-zsh-plugin
```

Use the arrow keys (or `j`/`k`) to select a plugin and Enter to install it. The
destination defaults to `$ZSH_CUSTOM/plugins`, or
`~/.oh-my-zsh/custom/plugins` when `ZSH_CUSTOM` is unset. The installer prints
the line to add to `~/.zshrc`; plugin-specific configuration remains documented
in [`zsh-plugins/README.md`](zsh-plugins/README.md).

Choose a different Oh My Zsh custom directory:

```sh
uvx --from git+https://github.com/mattfeng/utils install-zsh-plugin \
  --custom-dir ~/.config/oh-my-zsh/custom
```

Preview the source and destination without writing files:

```sh
uvx --from git+https://github.com/mattfeng/utils install-zsh-plugin --dry-run
```

Existing plugin directories are not changed by default. Pass `--force` to
replace the selected plugin with the bundled version.

## Set up devcontainer config files

Install an opinionated Vim config and Oh My Pi config into the current user's
home directory:

```sh
uvx --from git+https://github.com/mattfeng/utils setup-devcontainer-configs
```

An interactive selector lists the three files and their status. New files,
missing managed blocks, and blocks with an available template update are
selected by default; up-to-date files are left unselected. Toggle individual
files with Space, then press Enter to apply the selection. Re-running the
command compares each installed block with the template bundled in the current
utility version and labels changed templates as `update available`.

The command writes `~/.vimrc`, which copies yanked text to the host clipboard
with OSC 52, and `~/.omp/agent/config.yml`, which configures the preferred Oh My
Pi models, theme, status line, and Codex web search provider. It also writes
`~/.omp/agent/keybindings.yml`, disabling the temporary model selector shortcut
and assigning `Alt+P` to cycle role models forward. The terminal used to connect
to the devcontainer must permit OSC 52 clipboard writes.

Each file uses a clearly marked `mattfeng-utils devcontainer config` block.
Existing content outside that block is preserved, so any file can contain
additional personal configuration. If a file has incomplete or duplicate
markers, the command stops without changing any file.

Preview the resulting content for selected files without writing it:

```sh
uvx --from git+https://github.com/mattfeng/utils \
  setup-devcontainer-configs --dry-run
```

For non-interactive devcontainer setup, select every file with `--all`:

```sh
uvx --from git+https://github.com/mattfeng/utils \
  setup-devcontainer-configs --all
```

Use `--vim-config`, `--omp-config`, or `--omp-keybindings` to choose different
destinations.

## Set up Docker Compose backend services

Interactively generate a `compose.yaml` for PostgreSQL, MongoDB, or both:

```sh
uvx --from git+https://github.com/mattfeng/utils setup-compose
```

Both services are preselected. The prompts let you change each image, host port,
database, username, and password. Leaving a password blank generates a secure
32-character value.

The generated stack includes:

- PostgreSQL 18 Alpine and MongoDB 8.0 defaults
- named volumes for persistent data
- container health checks and `unless-stopped` restart policies
- ports bound to `127.0.0.1` by default
- credentials in `.env.compose`, written with file mode `0600`

Add `.env.compose` to your project's `.gitignore`, then start the services:

```sh
docker compose up -d
```

The credentials initialize new database volumes. Changing the environment file
later does not update users or passwords inside an already initialized volume.

Choose other output locations:

```sh
uvx --from git+https://github.com/mattfeng/utils setup-compose \
  --output docker/compose.yaml \
  --env-file docker/.env.compose
```

Preview the generated Compose and environment files without writing either one:

```sh
uvx --from git+https://github.com/mattfeng/utils setup-compose --dry-run
```

Existing files require confirmation before replacement. Pass `--force` to replace
them without a confirmation prompt.

## Install latest just

Install the latest release of [`casey/just`](https://github.com/casey/just) on
Ubuntu/Linux:

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
