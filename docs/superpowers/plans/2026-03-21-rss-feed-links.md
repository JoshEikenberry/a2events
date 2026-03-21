# RSS Feed Links UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a styled RSS subscription widget below the calendar sidebar in `docs/index.html` linking to the three existing feed files.

**Architecture:** Pure HTML/CSS addition to the single-file frontend. A new `.rss-widget` card is inserted inside `<aside class="sidebar">` after the existing `.calendar-widget`. New CSS rules are added to the inline `<style>` block. No JavaScript, no new files.

**Tech Stack:** Vanilla HTML/CSS, inline SVG for RSS icon. No build step — edit the file directly.

---

## File Map

| File | Change |
|---|---|
| `docs/index.html` | Add CSS rules to `<style>` block; add `.rss-widget` HTML in sidebar |
| `tests/test_index_html.py` | New test file: verify widget HTML is present and correct |

---

## Task 1: Write failing tests for the RSS widget

**Files:**
- Create: `tests/test_index_html.py`

- [ ] **Step 1: Create the test file**

```python
"""Tests for RSS feed links widget in docs/index.html."""
from pathlib import Path
from lxml import etree

INDEX = Path("docs/index.html")


def _parse():
    parser = etree.HTMLParser()
    return etree.fromstring(INDEX.read_bytes(), parser)


def test_rss_widget_exists():
    """The .rss-widget div must be present inside .sidebar."""
    tree = _parse()
    widgets = tree.cssselect(".sidebar .rss-widget")
    assert len(widgets) == 1, "Expected exactly one .rss-widget inside .sidebar"


def test_rss_widget_has_three_links():
    """There must be exactly three .rss-link anchors inside the widget."""
    tree = _parse()
    links = tree.cssselect(".rss-widget .rss-link")
    assert len(links) == 3, f"Expected 3 .rss-link elements, got {len(links)}"


def test_rss_link_hrefs():
    """Each feed link must point to the correct relative URL."""
    tree = _parse()
    hrefs = {a.get("href") for a in tree.cssselect(".rss-widget .rss-link")}
    assert hrefs == {"./feed.xml", "./feed-arts-culture.xml", "./feed-community.xml"}


def test_rss_links_open_new_tab():
    """All feed links must have target=_blank and rel=noopener noreferrer."""
    tree = _parse()
    for a in tree.cssselect(".rss-widget .rss-link"):
        assert a.get("target") == "_blank", f"Missing target=_blank on {a.get('href')}"
        assert "noopener" in (a.get("rel") or ""), f"Missing noopener on {a.get('href')}"
        assert "noreferrer" in (a.get("rel") or ""), f"Missing noreferrer on {a.get('href')}"


def test_rss_link_labels():
    """Each link must contain recognizable label text."""
    tree = _parse()
    texts = set()
    for a in tree.cssselect(".rss-widget .rss-link"):
        # Concatenate all text nodes inside the anchor
        texts.add("".join(a.itertext()).strip())
    assert "All Events" in texts
    assert "Arts & Culture" in texts
    assert "Community" in texts


def test_rss_widget_title_present():
    """The widget must have a .rss-widget-title element with non-empty text."""
    tree = _parse()
    titles = tree.cssselect(".rss-widget .rss-widget-title")
    assert len(titles) == 1
    assert titles[0].text_content().strip() != ""
```

- [ ] **Step 2: Run tests to confirm they all fail**

```bash
pytest tests/test_index_html.py -v
```

Expected: all 6 tests FAIL (`cssselect` not found or assertions fail because the widget doesn't exist yet). If `cssselect` is unavailable, install with `pip install cssselect`.

---

## Task 2: Add CSS rules for the RSS widget

**Files:**
- Modify: `docs/index.html` (inside `<style>` block, after `.clear-day-btn.visible` rule ~line 78)

- [ ] **Step 1: Add CSS after the `.clear-day-btn.visible` rule**

Find this line in the `<style>` block:
```css
    .clear-day-btn.visible { display: block; }
```

Insert immediately after it:
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

No tests needed for this step — CSS is verified visually and by the structural tests in Task 1.

---

## Task 3: Add RSS widget HTML to the sidebar

**Files:**
- Modify: `docs/index.html` (inside `<aside class="sidebar">`, after `.calendar-widget` closing `</div>`)

- [ ] **Step 1: Insert the widget HTML**

Find the sidebar section (around line 186):
```html
  <aside class="sidebar">
    <div class="calendar-widget">
      ...
      <button class="clear-day-btn" id="clear-day-btn">Clear day filter</button>
    </div>
  </aside>
```

Insert the new widget between `</div>` (end of `.calendar-widget`) and `</aside>`:

```html
    <div class="rss-widget">
      <p class="rss-widget-title">RSS Feeds</p>
      <a class="rss-link" href="./feed.xml" target="_blank" rel="noopener noreferrer">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <rect width="14" height="14" rx="2.5" fill="#f26522"/>
          <circle cx="3.5" cy="10.5" r="1.5" fill="white"/>
          <path d="M2 6.5A5.5 5.5 0 0 1 7.5 12" stroke="white" stroke-width="1.5" stroke-linecap="round" fill="none"/>
          <path d="M2 3A9 9 0 0 1 11 12" stroke="white" stroke-width="1.5" stroke-linecap="round" fill="none"/>
        </svg>
        All Events
      </a>
      <a class="rss-link" href="./feed-arts-culture.xml" target="_blank" rel="noopener noreferrer">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <rect width="14" height="14" rx="2.5" fill="#f26522"/>
          <circle cx="3.5" cy="10.5" r="1.5" fill="white"/>
          <path d="M2 6.5A5.5 5.5 0 0 1 7.5 12" stroke="white" stroke-width="1.5" stroke-linecap="round" fill="none"/>
          <path d="M2 3A9 9 0 0 1 11 12" stroke="white" stroke-width="1.5" stroke-linecap="round" fill="none"/>
        </svg>
        Arts &amp; Culture
      </a>
      <a class="rss-link" href="./feed-community.xml" target="_blank" rel="noopener noreferrer">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <rect width="14" height="14" rx="2.5" fill="#f26522"/>
          <circle cx="3.5" cy="10.5" r="1.5" fill="white"/>
          <path d="M2 6.5A5.5 5.5 0 0 1 7.5 12" stroke="white" stroke-width="1.5" stroke-linecap="round" fill="none"/>
          <path d="M2 3A9 9 0 0 1 11 12" stroke="white" stroke-width="1.5" stroke-linecap="round" fill="none"/>
        </svg>
        Community
      </a>
    </div>
```

- [ ] **Step 2: Run all tests**

```bash
pytest tests/test_index_html.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 3: Run full test suite to confirm no regressions**

```bash
pytest --ignore=reticulumnewsnet -v
```

Expected: all existing tests continue to pass.

- [ ] **Step 4: Commit**

```bash
rtk git add docs/index.html tests/test_index_html.py
rtk git commit -m "feat: add RSS feed links widget to sidebar"
```
