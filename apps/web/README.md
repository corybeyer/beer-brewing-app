# Browser application

This Vite/React/TypeScript application owns routes, screen composition, and React state. Install Node 24 LTS and run `npm ci`, `npm run dev`, `npm run build`, or `npm test` from the repository root.

Import reusable components from `@brewery/ui`, tokens/icons from `@brewery/design-system`, and the readiness adapter from `@brewery/communications`. Feature CSS only arranges components. Shared visual examples live in `packages/ui/src/examples/` and are exposed through `/component-examples.html` during development.

The first UI-04 Recipe Library view is a preview with disabled recipe operations; no recipes are fetched or invented. Service readiness is separate from recipe data availability. See [development and browser checks](../../docs/development/README.md) and [package ownership](../../docs/development/repository-layout.md).
