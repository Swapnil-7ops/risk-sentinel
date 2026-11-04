# GRC design system

The interface uses a navy/slate dark theme by default and a high-contrast light theme selected with the top-bar toggle. Theme preference is stored in `localStorage` under `grc-theme`.

Design tokens live in `public/static/src.css` as CSS custom properties:

- Surfaces: `--surface-0` page background, `--surface-1` cards/navigation, `--surface-2` controls and active states.
- Text: `--text-1` primary, `--text-2` secondary, `--text-muted` subdued.
- Accent: teal `--accent` and `--accent-strong`.
- Severity: `--low`, `--medium`, `--high`, and `--critical`; badges include text labels so severity is never conveyed by color alone.
- Shape: `--radius-sm`, `--radius-md`, `--radius-lg`.
- Elevation: `--shadow-card`.

Tailwind is compiled with `npm run build:css` from `public/static/src.css` to `public/static/app.css`. The compiled stylesheet, JavaScript, and fonts are self-hosted under `public/static/` and loaded under the application CSP.
