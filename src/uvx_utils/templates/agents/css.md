# CSS, SCSS, and Sass

## Formatting
- Write stylesheets for people to read. Do not collapse selectors, declarations, or nested rules onto a single line, and do not produce minified CSS, SCSS, or Sass unless the user explicitly requests it.
- In CSS and SCSS, put each declaration on its own indented line and each closing brace on its own line. Leave a blank line between rule blocks.
- In indented Sass syntax, put selectors, declarations, and nested rules on separate lines with consistent indentation.
- Follow the project's existing formatter and style conventions. When none are present, use consistent two-space indentation.
- Split long selector lists and complex values across lines when doing so makes them easier to scan.

## Maintainability
- Keep nesting shallow and organize related rules together so selector scope and overrides remain easy to understand.
- Use descriptive names for classes, custom properties, variables, mixins, and placeholders.
- Add comments only when they explain intent, constraints, or a non-obvious workaround; do not narrate self-explanatory declarations.
- Keep formatting changes focused on the rules being edited unless the user asks for broader cleanup.
