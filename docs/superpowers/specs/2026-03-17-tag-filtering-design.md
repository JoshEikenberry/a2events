# Tag Filtering Design

**Date:** 2026-03-17
**Status:** Approved

## Overview

Add a tag-based browsing row to the A2 Events site so users can filter events by content type (music, film, jazz, crafts, etc.) independently of the existing category tabs.

## UI Placement

A second row of pills appears in the sticky nav bar, directly below the existing category tabs. The nav uses `display: flex; align-items: center; flex-wrap: wrap; gap: 1.5rem`. The tag row is a `<div class="tag-row">` inserted as the last child of `<nav>`, after the `.nav-tabs` div. With `flex-basis: 100%; width: 100%` it occupies its own full-width row.

Change the nav's gap to `column-gap: 1.5rem; row-gap: 0` (desktop). The mobile breakpoint currently overrides `nav { gap: 0.75rem }` — change that to `column-gap: 0.75rem; row-gap: 0`.

The tag row itself should have `padding: 0.4rem 0`.

**The tag row is hidden on mobile:**
```css
@media (max-width: 720px) {
  .tag-row { display: none; }
}
```

**Known limitation:** `activeTags` is not cleared when the viewport crosses the mobile breakpoint. If a user resizes from desktop (tags active) to mobile, events remain filtered with no visible explanation. This is accepted as a minor edge case — the site is not designed for interactive viewport resizing, and the tag row reappears if the viewport is widened again.

### Sidebar top offset

The sidebar uses `position: sticky; top: 60px`. Fix it with a `ResizeObserver` set up **inside `initTagRow()`**, after the tag row has been appended to the DOM. `initTagRow()` is called exactly once, so the observer is created exactly once.

Use `nav.offsetHeight` (not `contentRect.height`) to include the nav's 1px `border-bottom` in the measurement:

```js
if (window.ResizeObserver) {
  var navEl = document.querySelector('nav');
  new ResizeObserver(function() {
    document.querySelector('.sidebar').style.top = navEl.offsetHeight + 'px';
  }).observe(navEl);
}
```

The `window.ResizeObserver` guard provides graceful degradation (sidebar keeps its CSS default of `60px`).

## Tag Discovery

Tags are derived dynamically from `events.json` inside the fetch `.then()` callback, after `allEvents` is populated. Each raw tag string is counted separately — no merging. Only tags with **5 or more events** are shown. Tags are sorted by count descending; ties broken alphabetically ascending (A→Z) using `<`/`>` string comparison, matching the existing codebase's sort pattern.

`buildTagCounts()` must guard against missing/non-array `tags` fields: `(ev.tags || [])`.

Expected visible tags at current data levels:

| Tag (raw) | Display label | Count |
|-----------|--------------|-------|
| music | Music | 113 |
| crafts | Crafts | 53 |
| public_meeting | Public Meeting | 50 |
| film | Film | 49 |
| jazz | Jazz | 22 |
| preschool_storytimes | Preschool Storytimes | 20 |
| baby_playgroups | Baby Playgroups | 13 |
| lectures_panel_discussions | Lectures & Panels | 6 |
| writing_publishing | Writing & Publishing | 6 |
| performers | Performers | 5 |

## Display Label Formatting

`humanizeTag(tag)`:
1. Check special-case lookup map first: `writing_publishing` → "Writing & Publishing", `lectures_panel_discussions` → "Lectures & Panels"
2. Fallback: split on `_`, then for each word uppercase the first character and lowercase the rest (`word[0].toUpperCase() + word.slice(1).toLowerCase()`), join with spaces.

The lookup map is the designated place to add future overrides.

Event cards continue to display raw tag text in `.badge.tag` elements — no change.

## State

`activeTags` is declared at the top of the IIFE alongside `allEvents`, `activeCategory`, `selectedDay`:

```js
var activeTags = new Set();
```

Always mutate via `activeTags.clear()` / `activeTags.add()` / `activeTags.delete()` — never reassign. Both `initTagRow()` and `initTabs()` close over this variable.

## Interaction Model

**Selecting a tag (inactive → active):**
- `activeTags.add(tag)`
- `activeCategory = "all"`; remove `.active` from all `.tab-btn`; `tab-select.value = "all"`
- Update pill: set `aria-pressed="true"`, add `.active` class
- Re-render events

**Deselecting a tag (active → inactive):**
- `activeTags.delete(tag)`
- Update pill: set `aria-pressed="false"`, remove `.active` class
- If `activeTags.size === 0`: `activeCategory = "all"` (defensive); re-add `.active` to the "All" `.tab-btn`; `tab-select.value = "all"`
- Re-render events

**Visual state while tags are active:** no category tab has `.active`. This is intentional — tags act as a parallel filter mode. A developer should not treat this as a bug.

**Switching category (tab button click OR `<select>` change):**

Both paths must prepend this cleanup before existing category logic:
```
activeTags.clear()
document.querySelectorAll(".tag-pill.active")   // live query at invocation time
  → forEach: remove "active" class, set aria-pressed="false"
```
Note: at the time `initTabs()` runs (synchronously in `init()`), no `.tag-pill` elements exist yet. The live `querySelectorAll` at invocation time is correct. Calling `activeTags.clear()` before `allEvents` is populated is a harmless no-op (the Set is already empty).

**Calendar interactions:** do not modify `activeTags`. No changes to `initCalNav` or the calendar click handler.

## Filtering Logic (`getFiltered`)

Use `(ev.tags || [])` guard throughout. Both branches apply `selectedDay`:

```
if activeTags.size > 0:
  show events where:
    ((ev.tags || []) has at least one element in activeTags)
    AND (selectedDay === null OR ev.date === selectedDay)

else:
  show events where:
    (activeCategory === "all" OR ev.category === activeCategory)
    AND (selectedDay === null OR ev.date === selectedDay)
```

By construction, when `activeTags.size > 0`, `activeCategory` is always "all". There is no "tag + non-all category" state.

## Fetch Callback Call Order

Inside the fetch `.then()`, after `allEvents` is assigned:
```
allEvents = events.slice().sort(...);
initTagRow();       // builds pills + starts ResizeObserver
renderCalendar();
renderEvents();
```

`initTagRow()` must come before `renderCalendar()`/`renderEvents()` so the ResizeObserver is registered (and fires its initial callback) before the layout settles.

## Empty State

Both existing and new empty states use the two-element structure: `<h2>No events found</h2>` + `<p>{message}</p>`.

| Condition | `<p>` message |
|-----------|--------------|
| `activeTags.size > 0 && selectedDay` | "No events found for the selected tags on this day." |
| `activeTags.size > 0 && !selectedDay` | "No events found for the selected tags." |
| `activeTags.size === 0` (any) | "Try changing the category or selecting a different day." |

## Styling

### Tag row label

The "Tags:" prefix is a `<span class="tag-row-label">`, first child of `.tag-row`. Hidden automatically since it's inside `.tag-row` which is `display:none` on mobile.

```css
.tag-row-label {
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
  white-space: nowrap;
  align-self: center;
  margin-right: 0.25rem;
}
```

### Tag pills

Nav tag pills use a new **`.tag-pill`** CSS class (distinct from `.badge.tag` on event cards):

```css
.tag-pill {
  background: none;
  border: 1px solid var(--border);
  border-radius: 2rem;
  padding: 0.2rem 0.6rem;
  font-size: 0.72rem;
  font-weight: 600;
  cursor: pointer;
  color: var(--muted);
  transition: all 0.15s ease;
}
.tag-pill:hover { background: var(--bg); color: var(--text); }
.tag-pill.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
```

## Accessibility

Tag pills are rendered as **`<button>`** elements via `el("button", ...)`. Each pill has `aria-pressed="false"` initially, toggled to `"true"` when active. This communicates toggle state to screen readers. Click handlers are attached via `addEventListener` after the element is constructed (the `el()` helper does not support event handler props).

## Implementation Scope

Changes confined to `docs/index.html`:

1. **CSS** — nav gap fix, `.tag-row` (hidden on mobile), `.tag-row-label`, `.tag-pill`, `.tag-pill.active`
2. **State** — `var activeTags = new Set();` declared at top of IIFE
3. **`humanizeTag(tag)`** — special-case map + generic fallback
4. **`buildTagCounts()`** — derives tag counts from `allEvents` with `(ev.tags || [])` guard, filters to ≥5, sorts by count desc then alpha asc
5. **`initTagRow()`** — renders `<button class="tag-pill" aria-pressed="false">` pills using `el()` + `addEventListener`, appends to nav, sets up `ResizeObserver` (with guard); called first inside fetch `.then()` after `allEvents` is assigned
6. **`getFiltered()`** — updated per the filtering pseudocode above
7. **`initTabs()`** — both button click and `<select>` change handlers prepend `activeTags.clear()` + live-query pill cleanup (with `aria-pressed` reset)
8. **`renderEvents()`** — empty state message updated per the table above

No changes to scrapers, `events.json`, or GitHub Actions.
