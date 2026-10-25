# JAX and Equinox

## JAX
- Keep JAX code functional: pass state explicitly and avoid hidden mutation inside transformed functions.
- Split and thread PRNG keys deliberately; never reuse a key for independent random operations.
- Be explicit about `jit`, `vmap`, `grad`, `value_and_grad`, and `pmap` boundaries.
- Avoid Python side effects, data-dependent Python control flow, and shape-changing behavior inside `jit`-compiled functions.

## Equinox
- Use `eqx.Module` fields deliberately and mark non-array/static fields clearly when needed.
- Use `eqx.filter_jit`, `eqx.filter_grad`, and `eqx.filter_value_and_grad` for PyTrees that contain non-array leaves.
- Preserve PyTree structure when changing models, optimizers, checkpointing, or serialization.
- Be careful with `eqx.partition`, `eqx.combine`, and filtered transformations so trainable and static leaves stay in the intended groups.

## Debugging and performance
- Check shapes, dtypes, and PyTree structure before blaming XLA compilation.
- Separate first-call compilation time from steady-state runtime when reporting performance.
- Use small deterministic inputs for smoke tests, and verify gradients before scaling up experiments.
