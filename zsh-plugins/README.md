# zsh-plugins

## devcontainer-prompt

Install it with the interactive utility:

```bash
uvx --from git+https://github.com/mattfeng/utils install-zsh-plugin
```

Or copy the plugin manually:

```bash
plugin_dir="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/devcontainer-prompt"
mkdir -p "$plugin_dir"
cp devcontainer-prompt/devcontainer-prompt.plugin.zsh "$plugin_dir/"
```

```bash
# in ~/.zshrc, before sourcing Oh My Zsh

DEVCONTAINER_PROMPT_TEXT='⬢'
DEVCONTAINER_PROMPT_COLOR='cyan'

# Color used when the matching container exists but is not running.
DEVCONTAINER_PROMPT_WARNING_COLOR=214

# Time to live (TTL), in seconds, for repeated checks in the same directory.
DEVCONTAINER_PROMPT_CACHE_TTL=3

# Include the Docker container name in the segment.
DEVCONTAINER_PROMPT_SHOW_NAME=true

# Show the segment in workspace subdirectories.
DEVCONTAINER_PROMPT_MATCH_SUBDIRECTORIES=true

plugins+=(devcontainer-prompt)
```

```bash
# in ~/.zshrc, after sourcing Oh My Zsh
setopt prompt_subst
PROMPT='${DEVCONTAINER_PROMPT}'"$PROMPT"
```
