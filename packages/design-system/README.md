# Design system

Owns semantic colors, typography, spacing, sizing, icons, global foundations, and responsive conventions. System fonts and MIT-licensed Lucide icons require no external font/image requests.

Exported as `@brewery/design-system`; `packages/ui` and applications consume its named exports. Never import UI components, app features, database code, or brewing rules here. Repeatable component examples belong to `packages/ui/src/examples/`.
