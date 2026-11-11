# Deep learning

## Minimalism
- Implementations should prioritize minimalism and using few dependencies. The stack that should always be used is JAX, Equinox, einops, optax, jaxtyping, beartype, grain, and tqdm.

## Comments

- Add comments before semantically related chunks of code to explain both what the chunk does and why it is needed or designed that way.
- Focus on intent, assumptions, and non-obvious design choices rather than restating individual lines.
- Keep each comment paragraph on a single source line without hard line breaks; rely on editor word wrapping for readability.

## Python environment

- Use `uv` exclusively for Python dependencies and environments.
- Maintain dependencies in `pyproject.toml`; commit `uv.lock`.
- Support macOS (CPU) and Linux (CPU or NVIDIA CUDA GPU).
- Use Python 3.11+.
- Include `jax` and `equinox` as base dependencies.
- Provide CUDA support through a Linux-only optional extra:
  `[project.optional-dependencies] cuda = ["jax[cuda13]; sys_platform == 'linux'"]`
- Never require CUDA for the default installation or macOS.
- Let JAX resolve compatible `jaxlib` and CUDA packages.
