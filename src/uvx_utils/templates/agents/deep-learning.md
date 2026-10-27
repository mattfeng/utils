# Deep learning

## Minimalism
- Implementations should prioritize minimalism and using few dependencies. The stack that should always be used is JAX, Equinox, einops, optax, jaxtyping, beartype, grain, and tqdm.

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
- Use `uv sync` for CPU and `uv sync --extra cuda` for Linux CUDA.
- Use matching `uv run` commands (with `--extra cuda` when needed).
- Verify installations with `jax.devices()` and an Equinox import.

## Experiment discipline
- Keep data preprocessing, model architecture, loss functions, optimizer settings, and evaluation metrics explicit and reproducible.
- Do not change random seeds, dataset splits, precision settings, or augmentation policy while also changing model logic unless the user asks for a broad experiment.
- Preserve checkpoint compatibility unless the task explicitly requires a breaking architecture or state-dict change.

## Correctness testing
- Prefer small, fast smoke runs before long training jobs.

## Training and evaluation
- Report the exact command, config, dataset split, seed, hardware assumptions, and key metrics for any training or evaluation run.
- Watch for silent failures: constant loss, NaNs/Infs, degenerate predictions, empty batches, train/eval mode mistakes, and metric leakage.
- For performance work, distinguish data-loading bottlenecks, host/device transfer overhead, compilation time, and model compute time.

## Data and metrics
- Avoid inspecting or using test labels during development.
- Keep train, validation, and test metrics separate in code, logs, and summaries.
- When changing metrics, preserve the old metric path long enough to compare before and after behavior.
- Document any class weighting, masking, padding, truncation, or sample filtering that affects reported results.
