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
    assert "".join(titles[0].itertext()).strip() != ""
