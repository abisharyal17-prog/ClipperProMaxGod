# Clipper UI — Design System & Guidelines (v1)

Follow these rules exactly. The goal is a **restrained, professional, product-grade**
interface — the opposite of "AI slop". When in doubt: less decoration, more clarity.

---

## 0. Anti-patterns (do NOT do these)
- No purple→pink gradients, no glassmorphism/blur, no neon glows on chrome.
- No emoji as UI iconography, no all-caps shouting labels, no drop-shadow soup.
- No rounded-3xl pills everywhere; radius is a scale, not a personality.
- No large hero sections inside an app shell. No marketing copy in the tool.
- No more than one accent colour. No mixed corner radii on sibling elements.
- No layout shift on load: reserve space, use skeletons of the correct size.

---

## 1. Foundations

### 1.1 Colour (OKLCH preferred; hex fallbacks given)
| Token | Dark | Light | Use |
|---|---|---|---|
| `bg` | `#0B0E14` | `#FFFFFF` | app background |
| `surface` | `#11151D` | `#F8FAFC` | cards, panels |
| `surface-2` | `#161B25` | `#F1F5F9` | inputs, nested |
| `border` | `#232A36` | `#E2E8F0` | 1px hairlines |
| `text` | `#E6EAF2` | `#0F172A` | primary text |
| `muted` | `#8A94A6` | `#64748B` | secondary text |
| `accent` | `#6366F1` | `#4F46E5` | primary actions, focus |
| `success` | `#22C55E` | same | done/ok |
| `warning` | `#F59E0B` | same | expiring/attention |
| `danger` | `#EF4444` | same | errors/delete |

Rules: exactly one accent; state colours only for state. Status is communicated by
a small dot + text, never colour alone.

### 1.2 Typography
- Family: **Inter** (UI) + system fallback. Mono: `ui-monospace, "JetBrains Mono"`.
- Scale (px / line-height / weight / tracking):
  - `display` 28/34/600/-0.02em — page titles
  - `title` 20/28/600/-0.01em — section headers
  - `body` 14/20/400 — default
  - `label` 12/16/500/0.01em — field labels, table headers
  - `mono` 12.5/18/400 — ids, params, timecodes (use tabular numbers)
- Never more than 3 sizes on one screen. Numeric data uses `font-variant-numeric: tabular-nums`.

### 1.3 Space, radius, elevation
- Space scale (px): 4, 8, 12, 16, 24, 32, 48. Layouts are built from 8/12/16/24.
- Radius: `sm 6`, `md 8`, `lg 12`. Buttons/inputs `sm`; cards `lg`; never mixed within a group.
- Borders: always 1px `border`. Prefer borders over shadows.
- Shadow: only for overlays (dialog, popover): `0 10px 30px rgba(0,0,0,.35)`.
- Focus: 2px `accent` ring with 2px offset, always visible on keyboard focus (`:focus-visible`).

### 1.4 Motion
- 150ms `ease-out` for hover/press; 200ms for enter; 120ms for exit.
- Motion only for: enter/exit, progress, state change. Respect `prefers-reduced-motion`.
- Progress must be real (driven by WS), never a fake indeterminate spinner when a % exists.

---

## 2. App shell
- **Top bar** (56px): left = wordmark + primary nav (`Projects`, `Settings`);
  right = global job indicator (current node + %), theme toggle, cookies health dot.
- **Content**: max-width 1200px, centred, padding 24px. Two-column only where it helps.
- **Workspace** = header row (title, source, primary actions) + tab bar + tab body.
- Tabs are text + optional count badge, underline indicator, 40px tall. Persist tab in URL `?tab=`.

## 3. Components (required states)
Every component must implement: **default, hover, active, focus-visible, disabled, loading, error**.
- `Button` — variants: `primary` (accent bg), `secondary` (surface + border), `ghost`, `danger`. Sizes sm/md. Icon+label; icon-only only with a tooltip + aria-label.
- `Card` — surface, 1px border, radius lg, padding 16-20, optional header (title + actions).
- `Input`/`Textarea`/`Select` — label above, help text below, error text in danger. 32-36px tall.
- `Tabs`, `Badge` (neutral/accent/success/warning/danger), `Progress` (thin 6px, accent), `Dialog` (overlay + focus trap + Esc), `Table` (sticky header, zebra off, row hover), `Switch`, `Toast` (bottom-right stack, auto-dismiss 4s), `Tooltip`, `Skeleton`.
- Data-dense values (params, clips, timecodes) render in `mono`.

## 4. Screens

### 4.1 Dashboard `/`
- Page title + one-line purpose, then a toolbar (search + New project button) then a
  responsive card grid (min 280px). Card = 16:9 thumb, title (1 line, truncate),
  meta badges (clips / renders), relative modified time, `Delete` on hover/menu.
- Empty state: bordered panel, one sentence, primary action. No illustrations beyond a simple glyph.

### 4.2 Workspace `/p/:id`
- **Pipeline**: React Flow canvas, dot grid background, `fitView` on load. Custom node:
  category dot + title, status chip (idle/running/done/cached/error), thin per-node
  progress. Edge = smoothstep, `animated` only while running. `Controls` + `MiniMap`
  bottom corners. Right inspector panel (320px) shows selected node: status,
  params (mono), ports (in/out), and Run buttons. `Run analysis` / `Run render`.
- **Transcript**: segmented control (Transcript / Payload / Prompt / SRT), mono viewer
  in a bordered scroll panel (max-height 60vh), Copy button top-right. Import-clips
  textarea with Validate → shows normalized result or a red error list.
- **Clips**: table. Columns: include (switch), score (bar + number, tabular), title
  (inline editable), range `mm:ss–mm:ss` (mono), duration, hook. Sort by score desc
  default. Bulk enable/disable + Save (dirty-state indicator).
- **Editor**: two columns — left = list of clips; right = controls for the selected
  clip (caption style, reframe, LUT, music, title text, exclude ranges row editor).
  "Render selected" is primary. Show a small live summary of resolved options.
- **Renders**: responsive video grid (`<video controls preload="metadata">`), card meta
  (title, duration, camera), Download, and the publish pack (title, hashtags, filename)
  with a copy-all button.

### 4.3 Settings `/settings`
Sections in cards: **Performance/Encoding** (encoder, crf, resolution, loudness),
**Transcription** (model, device, language), **Defaults** (caption style, reframe),
**Cookies** (see §5).

## 5. Cookies panel (required)
- Status row: dot (green/amber/red) + "18 cookies · authenticated · expires in 10.7 days".
- Primary: textarea "Paste cookie JSON or Netscape cookies.txt" + `Import`.
- Secondary: "Use browser profile" select (chrome/firefox/edge/brave) + `Save`.
- Actions: `Verify` (calls `/api/cookies/verify`, shows ok/message + detail), `Clear`.
- Warnings from `GET /api/cookies` render as inline amber/red alerts (expired, expiring soon,
  unauthenticated). If `expired` or `!authenticated`, show a persistent banner in the
  app shell top bar linking to Settings.
- Never display cookie values. Show counts and dates only.

## 6. Accessibility & quality bar
- Contrast ≥ 4.5:1 for text, ≥ 3:1 for UI borders/icons on their surface.
- Full keyboard operation; visible focus; dialogs trap focus and restore on close.
- Every async view has loading (skeleton), empty, and error states.
- No layout shift; reserve dimensions. Tables/panels scroll, not the page, where sensible.
- TypeScript strict; no `any` in props; components typed and reusable.
