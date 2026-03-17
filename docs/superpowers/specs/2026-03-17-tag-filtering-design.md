# Tag Filtering Design

**Date:** 2026-03-17
**Status:** Approved

## Overview

Add a tag-based browsing row to the A2 Events site so users can filter events by content type (music, film, jazz, crafts, etc.) independently of the existing category tabs.

## UI Placement

A second row of pills appears in the sticky nav bar, directly below the existing category tabs. On mobile the category tabs are already hidden (replaced by a `<select>`); the tag row will be hidden on mobile as well (matching the existing `@media (max-width: 720px)` breakpoint behavior).

## Tag Discovery

Tags are derived dynamically from `events.json` at load time. Only tags with **5 or more events** are shown. This threshold naturally excludes scraper-artifact tags (`observer_editor`, `public_event`, `community_listing`) while surfacing meaningful content tags:

| Tag | Count |
|-----|-------|
| music | 113 |
| crafts | 53 |
| public_meeting | 50 |
| film | ~51 (film + film_video_events) |
| jazz | 22 |
| preschool_storytimes | 20 |
| baby_playgroups | 13 |
| writing_publishing | 6 |
| lectures_panel_discussions | 6 |
| performers | 5 |

Tags are sorted by event count descending so the most useful ones appear first.

## Interaction Model

- Clicking a tag **toggles** it on/off
- Multiple tags can be active simultaneously
- Events matching **any** active tag are shown (OR logic)
- Selecting a tag **resets the category tab to "All"** — tags are top-level filters, independent of categories
- Switching to any category tab **clears all active tags**
- When no tags are active, normal category filtering resumes

## Filtering Logic (`getFiltered`)

```
if activeTags is non-empty:
  show events where event.tags intersects activeTags (OR)
  (category filter is ignored)
else:
  apply category filter as today
```

## State

One new state variable: `activeTags` — a JS `Set` of currently selected tag strings.

## Styling

- Tag pills reuse the existing `.tag` badge visual (light gray background, muted text, subtle border)
- Active tag pill: accent green background and border (matches `.tab-btn.active` style)
- Row label: small "TAGS:" prefix in muted uppercase, matching existing nav typography

## Scope

Changes confined to `docs/index.html`:
- New CSS for the tag row and active pill state
- Tag row HTML rendered dynamically via JS (same `el()` builder pattern used throughout)
- `activeTags` Set in state
- Updated `getFiltered()` function
- Updated `initTabs()` to clear tags when a category is selected
- New `initTagRow()` function to build and wire the tag pills

No changes to scrapers, `events.json`, or GitHub Actions.
