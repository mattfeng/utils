# PyTorch

## Implementation
- Keep tensor shapes and dtypes explicit at module boundaries.
- Prefer vectorized tensor operations over Python loops in hot paths.
- Move tensors and modules to devices deliberately; do not rely on implicit CPU/GPU behavior.
- Use `model.train()` and `model.eval()` intentionally, especially around dropout, batch norm, validation, and inference code.

## Autograd
- Do not detach tensors, call `.item()`, use `torch.no_grad()`, or mutate `.data` in code that must remain differentiable.
- Use `optimizer.zero_grad(set_to_none=True)` unless existing project conventions require otherwise.
- Check for NaNs/Infs in losses, gradients, and parameters when debugging unstable training.
- Preserve gradient accumulation semantics when changing batch size, loss scaling, or distributed training code.

## Performance
- Avoid unnecessary device transfers, synchronizing operations, and repeated tensor allocations inside training loops.
- Use mixed precision only when the project already has a clear precision policy or the user asks for it.
- Treat `torch.compile`, distributed training, and dataloader worker changes as behavior-affecting changes that need focused verification.
