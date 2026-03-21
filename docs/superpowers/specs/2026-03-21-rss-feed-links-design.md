# RSS Feed Links UI — Design Spec

**Date:** 2026-03-21
**Status:** Approved

## Summary

Add a visible RSS subscription widget below the calendar sidebar card in `docs/index.html`, linking to the three existing feed files. No new files are created; this is a pure HTML/CSS addition.

## Context

`generate_rss.py` already produces three feed files into `docs/`:

| File | Feed |
|---|---|
| `feed.xml` | All Events |
| `feed-arts-culture.xml` | Arts & Culture |
| `feed-community.xml` | Community |

These feeds are deployed to GitHub Pages alongside the main page but are currently unreachable from the UI.

## Design

### Structure

A new `<div class="rss-widget">` is inserted in `<aside class="sidebar">`, immediately after the closing `</div>` of `.calendar-widget`. It contains:

- A heading: "RSS Feeds" (`<p class="rss-widget-title">`)
- Three `<a class="rss-link">` rows, each with:
  - A 14×14 inline SVG RSS icon (orange `#f26522`, the conventional RSS color)
  - Link text: "All Events", "Arts & Culture", "Community"
  - `href`: `./feed.xml`, `./feed-arts-culture.xml`, `./feed-community.xml`
  - `target="_blank"`, `rel="noopener noreferrer"`

### CSS

New rules added to the existing `<style>` block:

```css
.rss-widget {
  margin-top: 0.75rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 1rem;
}
.rss-widget-title {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
  margin-bottom: 0.5rem;
}
.rss-link {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.3rem 0.4rem;
  border-radius: 0.375rem;
  text-decoration: none;
  color: var(--text);
  font-size: 0.85rem;
  transition: background 0.15s ease;
}
.rss-link:hover { background: var(--bg); }
```

### Mobile

The `.sidebar` is already hidden at ≤720px (`display: none`), so the RSS widget is automatically hidden on mobile with no additional work required.

### No JavaScript changes

The widget is static HTML — no JS needed.

## Files Changed

- `docs/index.html` — add CSS rules + HTML widget (sidebar only)

## Out of Scope

- Adding more feed categories (a separate task dependent on `generate_rss.py` changes)
- Mobile RSS access (requires a separate design decision)
- Auto-detecting available feeds
