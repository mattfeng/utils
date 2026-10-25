# Base instructions

## Documentation policy
- Do not modify README.md unless explicitly requested or essential to document a user-facing change.
- Keep README.md short, factual, and focused on installation, usage, and essential project information.
- Never append implementation logs, progress summaries, debugging notes, speculative features, or task histories.
- Put detailed technical documentation in docs/.
- Put agent instructions in AGENTS.md.
- Prefer deleting outdated content over accumulating additions.
- Before editing README.md, verify that the information is accurate, necessary, and unavailable elsewhere.
- Preserve the existing structure and writing style.
- Long lines/paragraphs are allowed. Do not use hard breaks to control line width when writing documentation into Markdown files.

## Planning
- Always prefer to construct general solutions that can be proven to work in all the expected cases, rather than implementing a series of "hacks" or special cases. Always be suspicious when something appears to require special cases.
- Address problems at the root cause, rather than patching over the symptoms.
- Before adding complexity for a speculative or vanishingly unlikely race or security edge case, explain the concrete failure mode, likelihood, and complexity cost to the user and get their buy-in. Do not silently expand scope for theoretical robustness.

## Files
- Before attempting to remove or modify a file/folder, check its file permissions. Furthermore, verify that its effective containing filesystem is writable: `target="$(readlink -f -- <path>)"; findmnt -no OPTIONS --target "$target" | tail -n 1`. `findmnt` can report multiple stacked mounts from outermost to innermost, so only the last line governs access to the target. If those comma-separated mount options contain `ro`, treat the filesystem as read-only and do not attempt the edit. An outer mount being `ro` does not override an inner mount being `rw`; in that case the target is on a writable filesystem, subject to its normal file permissions. Report a genuine read-only limitation instead of attempting the edit.
    - For a file that does not yet exist, run the check against its nearest existing parent directory.
- Do not try to remove or edit read-only files and folders.

## Networking
- For testing/exploration, access apps running on the host (e.g. Docker Compose) with `host.docker.internal` as the hostname.
- Actual applications in development, however, will be running on the host, and should access services via `localhost`.

## Verification
- Do not run applications, services, scripts, examples, demos, test suites, or other project code just to verify work unless the user explicitly asks.
- Static checks such as linting, formatting/style checks, and type checks are allowed.
