# Base instructions

## General rules
- Do not use promotional/marketing language ANYWHERE unless explicitly asked to.

## Documentation policy
- Do not modify READMEs unless explicitly requested or required to keep critical project information accurate. A user-facing change alone does not justify a README update.
- Keep READMEs short and limited to critical information needed to understand, install, configure, or use the project. Omit information whose absence would not prevent those tasks.
- Never add preferences, UI changes, styling/layout details, cosmetic choices, or minor behavior details to READMEs, even when they describe the final, desired state. Desired-state accuracy is necessary but does not make information README-worthy.
- Never append implementation logs, progress summaries, debugging notes, speculative features, or task histories.
- READMEs and code comments describe the final, desired behavior, usage, design, or constraints. Include non-obvious rationale only when it remains relevant to that state.
- Do not copy conversation instructions, user requests/corrections, implementation history, or abandoned approaches into READMEs or code comments. Keep task history in chat.
- Prefer deleting outdated content over accumulating additions.
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
- Do not write tests unless explicitly asked to do so.
