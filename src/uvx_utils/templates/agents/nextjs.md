# NextJS

## Versions
- This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.

## Package manager
- Assume the user is using {% if javascript_package_manager == "yarn" %}Yarn v4{% else %}npm{% endif %}.

## Instructions
- Do not try to install any packages on your own. Inform the user what commands to run and then check that the user has done so.
- If the project already has shadcn/ui configured, use its existing components and conventions for UI work.
- Do not try to install shadcn components yourself. If a needed shadcn component is not installed yet, ask the user to add it and confirm that they have done so before importing or using it.
- Do not run any development servers.
- Do not try to build the project.
