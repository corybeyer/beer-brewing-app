# Shared presentation components

The source of truth is `packages/design-system/src/tokens/tokens.css`. Features consume semantic variables; use system fonts and Lucide icons without external font/image requests. Responsive breakpoints are 36rem (phone) and 48rem (single-column content). Touch controls are at least 3rem high.

`src/index.tsx` and `src/components.css` own repeatable presentation: buttons, cards, badges, page headings, empty states, search/select fields, card footers, icon lists/tiles, and inline notes. Feature CSS may arrange those components with semantic layout/spacing tokens; shared control styling, colors, typography, and visual states belong here. `docs/images/` holds visual references, not executable styling. Future reusable charts should consume the design-system package and live with shared UI; images are reference material, not executable presentation.

The repeatable visual examples live in `src/examples/Gallery.tsx`. With Vite running, visit `/component-examples.html` to inspect enabled, disabled, busy, invalid, and empty states. Browser tests exercise this gallery and export screenshots per viewport. The gallery is a development test entrypoint, has no product navigation link, and is excluded from the production build.

```tsx
<Button onClick={retry}><Icon name="refresh" />Check again</Button>
<Button variant="secondary" busy={checking}>Checking…</Button>
<Button disabled aria-describedby="availability">New recipe</Button>
<Card aria-labelledby="title"><h2 id="title">Your recipes</h2></Card>
<Badge tone="positive">Local companion</Badge>
<SearchField label="Search recipes" placeholder="Search recipes…" disabled />
<SelectField label="Filter by style" disabled><option>All styles</option></SelectField>
<EmptyState badge="Coming soon" title="Room for your recipes" description="Keep the details that matter." />
```

Buttons retain native keyboard behavior. Busy buttons are disabled and expose `aria-busy`; disabled actions must have a nearby visible explanation. Text plus icons communicate status without relying on color. Icons are decorative and hidden from assistive technology; controls need text or an explicit accessible name. Focus rings, contrast, reduced-motion behavior, and touch targets are shared styles.

`tests/e2e/foundation.spec.ts` exercises loading/disabled/ready/error/retry button states in a real browser, keyboard focus and skip navigation, phone/tablet/desktop layouts, and WCAG A/AA checks through axe. The recipe-preview test exports a full-page screenshot for each viewport into ignored `tests/e2e/test-results/` for visual review. These screenshots are review artifacts, not automatic pixel-regression baselines or proof that future components are accessible.
