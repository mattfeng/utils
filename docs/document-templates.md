# Document templates

The `setup-agents-md` utility was imported from
[`mattfeng/agents-md` at `1d4e8ac`](https://github.com/mattfeng/agents-md/tree/1d4e8ac87f347ca0d2b1638cea3fdcd441e23645).
The command was renamed from `create-agents-md`; options, prompts, template
contents, ordering, and generated metadata remain compatible with the original
utility. The implementation lives in `src/uvx_utils/setup_agents_md.py`.

## Bundled AGENTS.md templates

Templates live in `src/uvx_utils/templates/agents/`. They render in this order,
regardless of selection order:

- General: `base`.
- Ecosystem: `python`, `fastapi`, `sqlalchemy-alembic`, `css`, `nextjs`, `shadcn`, `markdown-mdx`.
- Domain: `deep-learning`.
- Framework: `jax-equinox`, `pytorch`.

The first interactive run selects `base` by default. Later runs use the previous
selection as prompt defaults. Selecting nothing falls back to `base`. Explicit
`--template` options bypass template prompts and are deduplicated before rendering.
The `nextjs` and `shadcn` templates use the selected JavaScript package manager;
the initial default is `yarn`.

## Rendering context

Templates use Jinja2 with strict undefined variables and no HTML escaping. The
following variables are available:

| Variable | Value |
| --- | --- |
| `output_path` | Absolute path to the target `AGENTS.md`. |
| `project_dir` | Absolute path to the containing project directory. |
| `selected_templates` | Ordered list of selected template names. |
| `javascript_package_manager` | `npm` or `yarn`. |
| `template_name` | Name of the template being rendered, without `.md`. |

The managed block retains the original `agents-md-templates` markers, selection
metadata, and JavaScript package manager metadata. Older blocks without selection
metadata are recognized by their rendered template content or headings. Content
outside the block is preserved unless `--replace` is supplied.

## Adding templates

Add a Markdown file to `src/uvx_utils/templates/agents/`, such as `example.md`.
It automatically appears as `example` in prompts, `--template` choices, and `list`.
New names sort alphabetically after the known hierarchy; add a name to
`TEMPLATE_HIERARCHY` in `setup_agents_md.py` when a specific position is needed.
Files beneath `src/uvx_utils` are included by the existing wheel and source
distribution configuration, so templates require no separate download or manifest.

The `templates/agents/` directory reserves a namespace for this document type.
Future skills Markdown templates can live alongside it in `templates/skills/`,
with their own command and output conventions. Keeping them in a separate
directory prevents skill templates from appearing in the AGENTS.md selector.
Skills generation is not implemented yet.

## Local use

The generator requires `jinja2>=3.1.6`, declared in `pyproject.toml`. To install
the project's dependencies yourself, run `uv sync`. From this checkout, use:

```sh
uv run setup-agents-md list
uv run setup-agents-md --target /path/to/project --template base --template python
```

The second command writes the target file. Add `--javascript-package-manager npm`
or `--javascript-package-manager yarn` when selecting JavaScript templates in a
non-interactive workflow.
