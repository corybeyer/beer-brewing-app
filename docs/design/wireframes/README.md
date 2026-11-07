# Wireframe go-bys

Status: design references supplied in the conversation, not implemented screens or exact visual specifications.

## Reference inventory

| Reference | Screen | Supplied views |
| --- | --- | --- |
| Brew Day | UI-01 | Tablet/desktop and phone |
| Recipe — Steps | UI-02 | Desktop and phone |
| Batch Review & Tasting | UI-03 | Desktop and phone; same image supplied twice |
| Recipe Library & Ingredient Entry | UI-04 | Library and ingredient editor |
| Recipe Overview & Style | UI-05 | Named in the project reference; image not supplied here |
| Batch Setup | UI-06 | Named in the project reference; image not supplied here |

The four unique supplied images are now available locally in `docs/images/`; the [linked image inventory](../../images/README.md) maps their supplied filenames to screen IDs. UI-05 and UI-06 remain absent. These images and [screen specifications](../screens.md) preserve development guidance. Do not substitute generated mockups and call them the originals.

## Visual direction

Teal primary actions, restrained status colors, light surfaces, readable cards, prominent temperatures/timers, and clear labels. Desktop uses multiple panels; mobile stacks primary tasks and uses compact navigation. Use the existing semantic tokens and shared components rather than sampling arbitrary colors from images. An approved icon library and final typography remain open decisions.

## Known corrections and interpretation

- The brewer has confirmed an insulated cooler mash tun with no mash recirculation. The dashboard's pot-shaped mash tun, HERMS coil/recirculation route, and instruction to check recirculation are outdated guidance; omit them from implementation.
- The dashboard header and step strip disagree on step numbering. Derive both from actual batch steps.
- The phone step list omits intermediate steps for illustration. The product must make every step accessible in order.
- Demo temperatures, charts, dates, ratings, and recipe quantities are sample data, not live readings or validated brewing advice.
- Manual readings cannot imply continuous monitoring between entries. Freshness must describe each input, not just dashboard fetch time.
- Route diagrams depict planned paths; pump/burner status is separately labeled brewer-confirmed.
- The tasting revision caption contains developer guidance. Implement history preservation and reviewed revisions; remove internal instructions from product copy.
- Correct the library's garbled import caption to: “Review extracted ingredients and steps before saving.”
- Import buttons do not establish parser/OCR/file support. Keep unsupported modes proposed.
- Draft/ready/published terminology must be reconciled with explicit state transitions before implementation; a mockup button cannot bypass publication/start validation.

See [source provenance](../../references/README.md) and [product scope](../../requirements/product-scope.md).
