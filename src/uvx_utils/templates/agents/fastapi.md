# FastAPI

## Application structure
- Keep routing, dependency wiring, persistence, and domain logic separated. Route handlers should stay thin and delegate non-HTTP work to services or focused helpers.
- Prefer `APIRouter` modules for feature areas and include routers from the application factory or main app module.
- Put startup and shutdown work in lifespan handlers when the project supports them. Avoid import-time connection setup, background workers, or other side effects.
- Preserve the project's existing sync or async style. Do not convert handlers, database access, or clients between sync and async unless the task requires it.

## Request and response models
- Use Pydantic models for request bodies and response contracts. Keep API schemas explicit instead of returning raw ORM objects or unstructured dictionaries from new endpoints.
- Separate create, update, read, and internal models when their fields or validation rules differ.
- Be deliberate about optional fields, nullable values, defaults, aliases, and serialization behavior so the OpenAPI schema matches runtime behavior.
- Use `response_model`, status codes, and documented error responses where they clarify the public API contract.

## Dependencies and state
- Use FastAPI dependencies for request-scoped concerns such as authentication, authorization, database sessions, tenant context, feature flags, and external clients.
- Keep dependency functions small, typed, and override-friendly for tests.
- Do not store request-specific state in globals. Use dependency injection, `request.state`, or context variables only when they match existing project conventions.
- Clean up yielded dependency resources reliably, especially database sessions, transactions, locks, files, and network clients.

## Database and I/O
- Do not block the event loop from async route handlers. Use async-compatible clients or move blocking work to the project's established worker/thread boundary.
- Keep transaction boundaries explicit. Avoid committing in route handlers if the project centralizes commits in service or unit-of-work layers.
- Watch for N+1 queries and lazy-loading surprises during response serialization.
- For file uploads, streaming responses, and large payloads, avoid reading everything into memory unless the size is known and intentionally bounded.

## API behavior
- Raise `HTTPException` or project-specific API errors with stable status codes and response shapes. Avoid leaking internal exception details to clients.
- Validate authorization at the boundary where the protected resource is known, not only at router inclusion time.
- Keep path operation names, tags, summaries, and deprecation markers consistent with the surrounding API.
- Preserve backwards compatibility for existing routes, response fields, status codes, and validation behavior unless the user asks for an API change.

## Verification
- Do not start `uvicorn`, `fastapi dev`, or other development servers unless the user explicitly asks.
- Prefer static checks and focused code review in this environment. If runtime API verification is needed, tell the user the exact command to run outside the restricted workflow.
