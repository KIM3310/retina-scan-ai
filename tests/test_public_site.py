from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES_ORIGIN = "https://retina-scan-ai.pages.dev/"


def test_public_site_uses_cloudflare_pages_canonical() -> None:
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    offer = json.loads((ROOT / "site" / "service-offer.json").read_text(encoding="utf-8"))
    llms = (ROOT / "site" / "llms.txt").read_text(encoding="utf-8")
    robots = (ROOT / "site" / "robots.txt").read_text(encoding="utf-8")
    sitemap = ET.parse(ROOT / "site" / "sitemap.xml").getroot()
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    assert f'<link rel="canonical" href="{PAGES_ORIGIN}" />' in html
    assert f'<meta property="og:url" content="{PAGES_ORIGIN}" />' in html
    assert f'"url":"{PAGES_ORIGIN}"' in html
    assert offer["canonical_url"] == PAGES_ORIGIN
    assert offer["structured_data"]["url"] == PAGES_ORIGIN
    assert offer["structured_data"]["offers"][0]["url"] == PAGES_ORIGIN
    assert f"Canonical URL: {PAGES_ORIGIN}" in llms
    assert "Sitemap: https://retina-scan-ai.pages.dev/sitemap.xml" in robots
    assert sitemap.findtext("s:url/s:loc", namespaces=namespace) == PAGES_ORIGIN
