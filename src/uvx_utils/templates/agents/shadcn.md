# shadcn/ui

## Project conventions
- Before changing UI, inspect `components.json`, Tailwind configuration, global CSS, and existing components under the configured aliases.
- Use the project's existing shadcn/ui components, wrappers, variants, icons, spacing, and naming conventions before introducing new primitives.
- Keep shared UI primitives small and composable. Put feature-specific composition in feature components instead of expanding generic shadcn wrappers.
- Preserve the project's styling approach: Tailwind utility classes, CSS variables, theme tokens, variant helpers, and dark-mode strategy should match the surrounding code.

## Components
- Do not try to initialize shadcn/ui yourself.
- Do not try to install shadcn components yourself. If a needed component is missing, ask the user to run the appropriate command and confirm that they have done so before importing it.
- For {% if javascript_package_manager == "yarn" %}Yarn, suggest `yarn dlx shadcn@latest add <component>`{% else %}npm, suggest `npx shadcn@latest add <component>`{% endif %} when the user needs to add a component.
- Prefer composing installed shadcn components over copying examples wholesale. Adapt examples to the project's data flow, accessibility patterns, and component boundaries.
- When editing generated shadcn component files, keep changes narrowly focused and consistent with the rest of the local `components/ui` implementation.

## Styling
- Use `cn` or the project's equivalent class merging helper for conditional classes.
- Prefer semantic design tokens such as `bg-background`, `text-foreground`, `border-border`, `text-muted-foreground`, `bg-primary`, and `text-primary-foreground` over hard-coded colors.
- Use `class-variance-authority` variants only where the project already uses them or where multiple meaningful variants are needed.
- Keep layout responsibility with the parent component. UI primitives should not bake in page-specific margins, widths, or positioning.

## Accessibility
- Preserve Radix and shadcn accessibility behavior when wrapping or composing components.
- Keep labels, descriptions, ARIA attributes, keyboard navigation, focus-visible styles, and disabled states intact.
- Use shadcn form patterns and existing validation message components when building forms.
