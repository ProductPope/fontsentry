# FontSentry UI — Design System

The UI is derived from this design system, not the other way around. The design
system is the source of truth; components are built from tokens.

## Philosophy

Quiet, document-like, trustworthy. This tool makes legal-adjacent risk estimates,
so the interface stays calm and legible: restrained palette, generous spacing,
strong typographic hierarchy, and colour used only to encode risk — never decoration.

## Token architecture (two layers)

`Primitive → Semantic → Component`

- **Primitive** — raw values (`#a5301f`, `8px`). Live only in `src/styles/tokens.css`
  as `--p-*` custom properties. Never referenced by components.
- **Semantic** — named roles exposed to Tailwind via `@theme`
  (`--color-ink`, `--color-canvas`, `--color-accent`, `--color-band-high`, …).
  Components use the generated utilities only.

| Semantic token | Utility | When to use |
| --- | --- | --- |
| `--color-canvas` | `bg-canvas` | Page background |
| `--color-surface` | `bg-surface` | Cards, tables, panels |
| `--color-ink` | `text-ink` | Primary text |
| `--color-muted` | `text-muted` | Secondary text (≥ 4.5:1 on canvas) |
| `--color-stroke` | `border-stroke` | Borders, dividers |
| `--color-accent` | `bg-accent` / `text-accent` | Primary actions, focus ring |
| `--color-band-low/medium/high` | `bg-band-*` | Risk bands only |
| `--radius-tk` | `rounded-tk` | Corner radius |

Never use raw Tailwind palette utilities (`text-gray-400`, `bg-[#fff]`) or inline
hex. If a value is missing, add a token — don't hardcode.

## Components

In `src/components/`. Each is a functional component, accepts `className`, and
extends it through `cn()`; props extend native HTML element types.

- `Button` — `primary | secondary | ghost`; native `<button>`, focus-visible ring.
- `Card` — surface container.
- `Badge` / `RiskBadge` — pill; `RiskBadge` maps a band to colour + `aria-label`.
- `Spinner` — `role="status"`, `aria-live="polite"`.

### Adding a component

1. Reuse before creating — check `src/components/` first.
2. Use only semantic utilities; accept and merge `className` via `cn()`.
3. Extend the relevant native HTML type; keep it under ~150 lines.
4. Prefer native elements over ARIA (`<button>`, `<label>`, `<table>`).

## Accessibility (WCAG 2.2)

- Native semantic HTML; labels tied to inputs; tables use `<th scope>`.
- Visible keyboard focus on everything (`:focus-visible` outline in `index.css`).
- Contrast ≥ 4.5:1 for text (band/muted tokens chosen for this).
- Modals trap focus on open and restore it on close.
- Animations respect `prefers-reduced-motion`.

## Stack

React 19 · TypeScript (strict) · Vite 7 · Tailwind CSS 4 (`@theme` tokens) ·
`clsx` + `tailwind-merge` for `cn()`.
