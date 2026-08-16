# Grandma Chen Care Coordinator — Design System v2

Synthesized from three Instagram design.md references (Messages, main app, docs site),
adapted for a caregiving context. Instagram's structural discipline is kept — spacing
rhythm, message-bubble chat pattern, two-surface navigation, strict state coverage.
Instagram's dark palette is intentionally NOT carried over — replaced with a light,
high-legibility palette appropriate for a healthcare context and older readers.

## Mission

Two focused pages instead of one dense screen: a **Chat** page (conversation + retrieval
receipts) and a **Care Log** page (log a note + live memory stream). Judges and family
members should immediately understand what they're looking at without scrolling past
three simultaneous panels.

## Design Tokens

### Color (light, high-contrast, WCAG 2.2 AA)
- `color.surface.base = #ffffff`
- `color.surface.muted = #f7f8fa`
- `color.surface.raised = #ffffff` (cards, shadow-elevated)
- `color.surface.strong = #eef1f5` (subtle section backgrounds)
- `color.border.default = #e2e5ea`
- `color.border.strong = #c7cdd6`
- `color.text.primary = #1a1d23`
- `color.text.secondary = #5b6270`
- `color.text.tertiary = #8a919e`
- `color.text.inverse = #ffffff`
- `color.accent.primary = #3b6fe0` (Direct SQL mode)
- `color.accent.secondary = #9b4de0` (MCP Server mode)
- `color.accent.success = #1f9d55`
- `color.accent.warning = #d98e04`
- `color.accent.danger = #dc3545`

### Typography
- `font.family.stack = -apple-system, system-ui, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`
- `font.size.xs = 12px` / `font.size.sm = 14px` / `font.size.md = 16px` / `font.size.lg = 20px` / `font.size.xl = 28px`
- `font.weight.regular = 400` / `font.weight.medium = 500` / `font.weight.bold = 700`
- `font.lineHeight.base = 1.5`

### Spacing (8px rhythm, Instagram-style tight-but-breathable)
- `space.1 = 4px` / `space.2 = 8px` / `space.3 = 12px` / `space.4 = 16px` / `space.5 = 24px` / `space.6 = 32px`

### Radius & Motion
- `radius.sm = 8px` (inputs, chips) / `radius.md = 16px` (cards) / `radius.lg = 24px` (chat bubbles) / `radius.pill = 999px` (toggle, tabs)
- `motion.duration.fast = 150ms` / `motion.duration.base = 250ms`
- `shadow.card = 0px 1px 3px rgba(16, 24, 40, 0.08)`

## Navigation

Two top-level tabs, pill-style, Instagram-nav-inspired, sticky at top:
`[ 💬 Chat ]  [ 📋 Care Log ]`
- Active tab: `color.accent.primary` background, white text, `radius.pill`.
- Inactive tab: transparent, `color.text.secondary`, hover → `color.surface.strong`.
- Keyboard: arrow-key navigable, `Enter`/`Space` activates, visible focus ring (`2px solid color.accent.primary`, 2px offset).

## Page 1 — Chat

- Full-height single column, max-width 720px, centered.
- Message bubbles: assistant = `color.surface.strong` background, left-aligned, `radius.lg` with flat top-left corner. User = `color.accent.primary` background, white text, right-aligned, `radius.lg` with flat top-right corner. (Direct Instagram DM pattern.)
- Retrieval receipt: collapsed pill under each assistant bubble, accent-colored border matching the mode used (blue/purple), expands on click/tap — not auto-expanded.
- Composer: sticky bottom bar, input + Send button + mode toggle inline, `radius.pill` input.
- **Warm-up state — made genuinely prominent this time**: a full-width banner (not a small inline note) appears above the composer the moment a request exceeds 3 seconds, with an animated pulse dot, reading "Warming up the AI models — this can take up to a minute on the first question." Dismissible only when the response arrives.

## Page 2 — Care Log

- Two-column on desktop (stacks on mobile): left = "Log a Caregiver Note" form, right = "Live Memory Stream" feed.
- Form fields: Caregiver name, Note type (chip-select: Medication / Observation / General), Content (textarea). Submit button disabled until all required fields are valid; shows inline success toast on save, auto-scrolls the feed to the new entry.
- Feed cards: avatar-initial circle, name, relative timestamp, type badge (color-coded), content — same visual language as today's Live Memory Stream, just given its own dedicated page instead of competing for space.

## Required States (every interactive component)

Every button, input, toggle, and tab must define: `default`, `hover`, `focus-visible`
(visible ring, never suppressed), `active`, `disabled` (reduced opacity, no pointer),
`loading` (spinner replaces label, control disabled), `error` (red border + inline
message below field, `aria-invalid="true"`).

## Accessibility Acceptance Criteria

- All text meets 4.5:1 contrast minimum against its background (pass/fail testable with any contrast checker against the tokens above).
- Every interactive element reachable via Tab key in visual order; focus ring never hidden.
- Loading and error states are announced via `aria-live="polite"` regions, not color alone.
- Tap targets minimum 44x44px on mobile.

## QA Checklist

- [ ] Both tabs keyboard-navigable, correct active/focus states
- [ ] Chat bubbles render correctly for both long and one-word messages
- [ ] Retrieval receipt collapses/expands correctly, correct accent per mode
- [ ] Warm-up banner appears at 3s, persists until response, never overlaps composer
- [ ] Care Log form validates before submit, shows success toast, feed updates live
- [ ] All contrast ratios pass WCAG AA against the token values above
- [ ] No regressions to existing /api/ask, /api/notes, /api/simulate behavior — this is a visual/structural change only
