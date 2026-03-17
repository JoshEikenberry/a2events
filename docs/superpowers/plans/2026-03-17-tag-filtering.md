# Tag Filtering Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a multi-select tag filter row to the nav bar so users can browse events by content type (music, film, jazz, etc.) independently of the category tabs.

**Architecture:** All changes are confined to `docs/index.html`. Tags are derived dynamically from `events.json` at load time. A new `activeTags` Set drives filtering alongside the existing `activeCategory` and `selectedDay` state variables.

**Tech Stack:** Vanilla JS (ES5), CSS custom properties, no build tools. Open `docs/index.html` via a local HTTP server to test (e.g. `python -m http.server 8080` from the `docs/` directory).

---

## Chunk 1: CSS + State + Helpers

### Task 1: Fix nav gap and add tag-row CSS

**Files:**
- Modify: `docs/index.html` — CSS section, `<nav>` rule (~line 27) and mobile breakpoint `nav` rule (~line 123)

- [ ] **Step 1: Update nav gap at desktop**

In the `nav` CSS rule (around line 27-29), change `gap: 1.5rem` to:
```css
column-gap: 1.5rem; row-gap: 0;
```

- [ ] **Step 2: Update nav gap at mobile breakpoint**

In the `@media (max-width: 720px)` block, the `nav` rule currently has `gap: 0.75rem`. Change to:
```css
column-gap: 0.75rem; row-gap: 0;
```

- [ ] **Step 3: Add tag-row, tag-row-label, and tag-pill CSS**

After the `.clear-day-btn.visible` rule (~line 78), insert:
```css
.tag-row {
  flex-basis: 100%; width: 100%;
  display: flex; align-items: center; flex-wrap: wrap;
  gap: 0.35rem; padding: 0.4rem 0;
  border-top: 1px solid var(--border);
}
.tag-row-label {
  font-size: 0.65rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.05em; color: var(--muted); white-space: nowrap;
  align-self: center; margin-right: 0.25rem;
}
.tag-pill {
  background: none; border: 1px solid var(--border); border-radius: 2rem;
  padding: 0.2rem 0.6rem; font-size: 0.72rem; font-weight: 600;
  cursor: pointer; color: var(--muted); transition: all 0.15s ease;
}
.tag-pill:hover { background: var(--bg); color: var(--text); }
.tag-pill.active { background: var(--accent); border-color: var(--accent); color: #fff; }
@media (max-width: 720px) { .tag-row { display: none; } }
```

- [ ] **Step 4: Verify visually**

Open `http://localhost:8080` (serve `docs/` with `python -m http.server 8080`). The nav should look the same as before — no tag row yet (it'll be empty until JS adds pills), just no unwanted gap between the category tabs and where the tag row will go.

- [ ] **Step 5: Commit**

```bash
git add docs/index.html
git commit -m "feat: add tag-row CSS to nav"
```

---

### Task 2: Add activeTags state variable

**Files:**
- Modify: `docs/index.html` — JS state declarations (~line 193)

- [ ] **Step 1: Declare activeTags**

After `var selectedDay = null;` (~line 195), add:
```js
var activeTags = new Set();
```

- [ ] **Step 2: Commit**

```bash
git add docs/index.html
git commit -m "feat: add activeTags state variable"
```

---

### Task 3: Add humanizeTag helper

**Files:**
- Modify: `docs/index.html` — JS helpers section, after `categoryClass()` (~line 242)

- [ ] **Step 1: Add humanizeTag function**

After the `categoryClass` function, insert:
```js
var HUMANIZE_MAP = {
  "writing_publishing": "Writing & Publishing",
  "lectures_panel_discussions": "Lectures & Panels"
};

function humanizeTag(tag) {
  if (HUMANIZE_MAP[tag]) return HUMANIZE_MAP[tag];
  return tag.split("_").map(function(w) {
    return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
  }).join(" ");
}
```

- [ ] **Step 2: Verify in browser console**

Open browser console and run:
```js
humanizeTag("music")               // → "Music"
humanizeTag("preschool_storytimes") // → "Preschool Storytimes"
humanizeTag("writing_publishing")   // → "Writing & Publishing"
```

- [ ] **Step 3: Commit**

```bash
git add docs/index.html
git commit -m "feat: add humanizeTag helper"
```

---

### Task 4: Add buildTagCounts helper

**Files:**
- Modify: `docs/index.html` — JS helpers section, after `humanizeTag`

- [ ] **Step 1: Add buildTagCounts function**

After `humanizeTag`, insert:
```js
function buildTagCounts() {
  var counts = {};
  allEvents.forEach(function(ev) {
    (ev.tags || []).forEach(function(t) {
      counts[t] = (counts[t] || 0) + 1;
    });
  });
  return Object.keys(counts)
    .filter(function(t) { return counts[t] >= 5; })
    .sort(function(a, b) {
      if (counts[b] !== counts[a]) return counts[b] - counts[a];
      return a < b ? -1 : a > b ? 1 : 0;
    });
}
```

- [ ] **Step 2: Verify in browser console (after page loads events)**

```js
buildTagCounts()
// Should return array starting with: ["music", "crafts", "public_meeting", "film", ...]
```

- [ ] **Step 3: Commit**

```bash
git add docs/index.html
git commit -m "feat: add buildTagCounts helper"
```

---

## Chunk 2: initTagRow + Filtering + Tab Integration

### Task 5: Add initTagRow function

**Files:**
- Modify: `docs/index.html` — JS, after `initCalNav()` (~line 437)

- [ ] **Step 1: Add initTagRow function**

After `initCalNav`, insert:
```js
function initTagRow() {
  var nav = document.querySelector("nav");
  var row = el("div", {className: "tag-row"});
  row.appendChild(el("span", {className: "tag-row-label", textContent: "Tags:"}));

  buildTagCounts().forEach(function(tag) {
    var btn = el("button", {
      className: "tag-pill",
      textContent: humanizeTag(tag),
      "aria-pressed": "false"
    });
    btn.addEventListener("click", function() {
      var isActive = activeTags.has(tag);
      if (isActive) {
        activeTags.delete(tag);
        btn.classList.remove("active");
        btn.setAttribute("aria-pressed", "false");
        if (activeTags.size === 0) {
          activeCategory = "all";
          document.querySelectorAll(".tab-btn").forEach(function(b) {
            b.classList[b.dataset.category === "all" ? "add" : "remove"]("active");
          });
          var sel = document.getElementById("tab-select");
          if (sel) sel.value = "all";
        }
      } else {
        activeTags.add(tag);
        btn.classList.add("active");
        btn.setAttribute("aria-pressed", "true");
        activeCategory = "all";
        document.querySelectorAll(".tab-btn").forEach(function(b) { b.classList.remove("active"); });
        var sel = document.getElementById("tab-select");
        if (sel) sel.value = "all";
      }
      renderEvents();
    });
    row.appendChild(btn);
  });

  nav.appendChild(row);

  if (window.ResizeObserver) {
    new ResizeObserver(function() {
      var sidebar = document.querySelector(".sidebar");
      if (sidebar) sidebar.style.top = nav.offsetHeight + "px";
    }).observe(nav);
  }
}
```

- [ ] **Step 2: Wire initTagRow into fetch callback**

In the fetch `.then()` callback (~line 452), change:
```js
allEvents = events.slice().sort(function(a, b) {
  return a.date < b.date ? -1 : a.date > b.date ? 1 : 0;
});
renderCalendar();
renderEvents();
```
to:
```js
allEvents = events.slice().sort(function(a, b) {
  return a.date < b.date ? -1 : a.date > b.date ? 1 : 0;
});
initTagRow();
renderCalendar();
renderEvents();
```

- [ ] **Step 3: Verify tag pills appear**

Refresh the page. The nav should now show a "Tags:" row below the category tabs with pills: Music, Crafts, Public Meeting, Film, Jazz, Preschool Storytimes, Baby Playgroups, Lectures & Panels, Writing & Publishing, Performers.

Click a pill — it should turn green. Click it again — it should go back to gray. No filtering yet (that's next task).

- [ ] **Step 4: Commit**

```bash
git add docs/index.html
git commit -m "feat: add initTagRow with pill rendering and ResizeObserver"
```

---

### Task 6: Update getFiltered to apply tag logic

**Files:**
- Modify: `docs/index.html` — `getFiltered()` function (~line 261)

- [ ] **Step 1: Rewrite getFiltered**

Replace the existing `getFiltered` function body:
```js
function getFiltered() {
  return allEvents.filter(function(ev) {
    if (activeCategory !== "all" && ev.category !== activeCategory) return false;
    if (selectedDay && ev.date !== selectedDay) return false;
    return true;
  });
}
```
with:
```js
function getFiltered() {
  return allEvents.filter(function(ev) {
    if (activeTags.size > 0) {
      var evTags = ev.tags || [];
      var hasMatch = false;
      activeTags.forEach(function(t) { if (evTags.indexOf(t) !== -1) hasMatch = true; });
      if (!hasMatch) return false;
    } else {
      if (activeCategory !== "all" && ev.category !== activeCategory) return false;
    }
    if (selectedDay && ev.date !== selectedDay) return false;
    return true;
  });
}
```

- [ ] **Step 2: Verify tag filtering works**

Refresh. Click "Music" — only music-tagged events should show. Click "Jazz" in addition — events tagged music OR jazz should show. Click "Music" again to deselect — only jazz events. Deselect "Jazz" — all events return, "All" category tab re-activates.

- [ ] **Step 3: Commit**

```bash
git add docs/index.html
git commit -m "feat: update getFiltered to apply activeTags OR logic"
```

---

### Task 7: Update initTabs to clear tags on category switch

**Files:**
- Modify: `docs/index.html` — `initTabs()` function (~line 397)

- [ ] **Step 1: Update tab button click handler**

In `initTabs()`, the click handler currently sets `activeCategory` and re-renders. Add tag cleanup at the top of that handler:
```js
document.querySelectorAll(".tab-btn").forEach(function(btn) {
  btn.addEventListener("click", function() {
    // NEW: clear tags
    activeTags.clear();
    document.querySelectorAll(".tag-pill.active").forEach(function(p) {
      p.classList.remove("active");
      p.setAttribute("aria-pressed", "false");
    });
    // existing logic unchanged below
    activeCategory = btn.dataset.category;
    document.querySelectorAll(".tab-btn").forEach(function(b) { b.classList.remove("active"); });
    btn.classList.add("active");
    var sel = document.getElementById("tab-select");
    if (sel) sel.value = activeCategory;
    renderEvents();
  });
});
```

- [ ] **Step 2: Update select change handler**

The `tabSelect` change handler similarly needs tag cleanup prepended:
```js
tabSelect.addEventListener("change", function() {
  // NEW: clear tags
  activeTags.clear();
  document.querySelectorAll(".tag-pill.active").forEach(function(p) {
    p.classList.remove("active");
    p.setAttribute("aria-pressed", "false");
  });
  // existing logic unchanged below
  activeCategory = tabSelect.value;
  document.querySelectorAll(".tab-btn").forEach(function(b) {
    b.classList[b.dataset.category === activeCategory ? "add" : "remove"]("active");
  });
  renderEvents();
});
```

- [ ] **Step 3: Verify category↔tag mutual exclusion**

Click "Music" tag (turns green, All tab goes inactive). Then click "Arts & Culture" tab — Music pill should clear, Arts tab becomes active, events filter to arts category. Works in both directions.

- [ ] **Step 4: Commit**

```bash
git add docs/index.html
git commit -m "feat: clear activeTags when switching category tab"
```

---

### Task 8: Update empty state messages

**Files:**
- Modify: `docs/index.html` — `renderEvents()` function (~line 274)

- [ ] **Step 1: Update empty state message logic**

The current empty state block is:
```js
if (filtered.length === 0) {
  list.appendChild(el("div", {className: "state-message"}, [
    el("h2", {textContent: "No events found"}),
    el("p", {textContent: "Try changing the category or selecting a different day."})
  ]));
  return;
}
```

Replace with:
```js
if (filtered.length === 0) {
  var emptyMsg;
  if (activeTags.size > 0 && selectedDay) {
    emptyMsg = "No events found for the selected tags on this day.";
  } else if (activeTags.size > 0) {
    emptyMsg = "No events found for the selected tags.";
  } else {
    emptyMsg = "Try changing the category or selecting a different day.";
  }
  list.appendChild(el("div", {className: "state-message"}, [
    el("h2", {textContent: "No events found"}),
    el("p", {textContent: emptyMsg})
  ]));
  return;
}
```

- [ ] **Step 2: Verify empty state**

Click the "Performers" tag (5 events). Then click a calendar day that has no performer events — the message should read "No events found for the selected tags on this day."

- [ ] **Step 3: Final commit**

```bash
git add docs/index.html
git commit -m "feat: tag-aware empty state messages"
```

- [ ] **Step 4: Push**

```bash
git push
```
