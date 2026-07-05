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
| `--color-surface2` | `bg-surface2` | Insets, chips, footers, hover fills |
| `--color-sunken` | `bg-sunken` | Progress tracks, code blocks |
| `--color-ink` | `text-ink` | Primary text |
| `--color-muted` | `text-muted` | Secondary text (≥ 4.5:1 on canvas) |
| `--color-faint` | `text-faint` | Tertiary text, labels |
| `--color-stroke` | `border-stroke` | Borders, dividers |
| `--color-stroke2` | `border-stroke2` | Stronger/dashed borders |
| `--color-accent` | `bg-accent` / `text-accent` | Primary actions, links, focus ring (slate-blue) |
| `--color-accent-fg` | `text-accent-fg` | Text/icon ON an accent fill |
| `--color-accent-soft` | `bg-accent-soft` | Accent tint backgrounds, `::selection` |
| `--color-band-{low,medium,high}` | `text-band-*` | Verdict/risk foreground; low=OK, medium=Need check, high=Violation |
| `--color-band-{low,medium,high}-bg` | `bg-band-*-bg` | Verdict/risk pill/chip fill |
| `--color-band-{low,medium,high}-line` | `border-band-*-line` | Verdict/risk pill/chip border |
| `--shadow-tk` / `--shadow-tk-lg` | `shadow-tk` / `shadow-tk-lg` | Card / modal-toast elevation |
| `--radius-tk` | `rounded-tk` | Buttons, inputs (8px) |
| `--radius-card` | `rounded-card` | Cards, tables, modals (12px) |
| `--radius-chip` | `rounded-chip` | Chips, small badges (6px) |
| `--font-sans` | `font-sans` | UI text (IBM Plex Sans) |
| `--font-mono` | `font-mono` | Numerics, IDs, domains, embeddings, formats, timestamps (IBM Plex Mono) |

Never use raw Tailwind palette utilities (`text-gray-400`, `bg-[#fff]`) or inline
hex. If a value is missing, add a token — don't hardcode.

## Theming (light / dark)

Both themes ship. `@theme` in `tokens.css` defines the **light** semantics; a
`:root[data-theme="dark"]` block remaps the same `--color-*` tokens to the dark
primitives. Because every utility resolves to `var(--color-…)`, components
re-theme at runtime with **no `dark:` variants** — just use the semantic
utilities and both themes work.

- `<html data-theme>` is set **before first paint** by an inline script in
  `index.html` (reads `localStorage["fontsentry.theme"]`, else
  `prefers-color-scheme`) to avoid a flash.
- `useTheme()` (`src/lib/useTheme.ts`) reads/toggles it and persists; the
  `ThemeToggle` component is the UI. `color-scheme` is set per theme so native
  controls (scrollbars, form widgets) follow.

## Fonts

**IBM Plex Sans** (400/500/600/700) and **IBM Plex Mono** (400/500/600), both
**self-hosted** via `@fontsource/*` and bundled by Vite — no external font fetch
at runtime (offline/CSP constraint). Weights are imported in `styles/index.css`.

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
