# Deep learning

## Type annotations

- Fully annotate every function, method, and constructor: all parameters except `self` and `cls`, plus return values. Annotate `__init__` with `-> None`.
- Use `jaxtyping` annotations for all tensor and array parameters and return values, specifying both dtype and shape (e.g. `Float[Array, "batch sequence features"]`). Use meaningful, consistent dimension names and express fixed dimensions or shape relationships wherever applicable.

## Minimalism

- - When creating deep learning implementations, use JAX, equinox, einops, jaxtyping, beartype, optax, grain, tqdm, and trackio as the dependency stack. Try to minimize use of any other libraries.
- Implementations should prioritize minimalism, readability, and hackability.

## Comments

- Add comments before semantically related chunks of code to explain both what the chunk does and why it is needed or designed that way.
    - A good rule of thumb is a comment every 5-10 lines of code.
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
