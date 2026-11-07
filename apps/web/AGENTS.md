# Frontend instructions

- Consume design-system tokens and components; never hardcode visual constants in a feature.
- Import repeatable UI from `@brewery/ui` and tokens/icons from `@brewery/design-system`; feature CSS owns page arrangement only. Shared examples live in `packages/ui/src/examples/`. Reference images in `docs/images/` guide reviews but do not replace shared components or tokens.
- Ensure layouts work on phone, tablet, and desktop; target outdoor, gloved, and wet-hand operation.
- Every interactive component requires keyboard, focus, disabled, loading, error, and touch states where applicable.
- Never display stale sensor values as fresh; label units and last-updated times.
- Require explicit brewer confirmation for brewing stage changes and physical actions.
- Add accessibility and component tests for new shared controls.
