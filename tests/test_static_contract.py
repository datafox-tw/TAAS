import re
from pathlib import Path


STATIC = Path("src/taas/static")


def test_frontend_references_existing_assets() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    asset_paths = re.findall(r'(?:src|href)="/assets/([^"]+)"', html)
    assert asset_paths
    assert all((STATIC / path).is_file() for path in asset_paths)


def test_javascript_element_ids_exist_in_html() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")
    html_ids = set(re.findall(r'id="([^"]+)"', html))
    javascript_ids = set(re.findall(r'\$\("([^"]+)"\)', javascript))
    assert javascript_ids <= html_ids, sorted(javascript_ids - html_ids)


def test_vendor_assets_are_pinned_leaflet_release() -> None:
    leaflet = (STATIC / "vendor" / "leaflet.js").read_text(encoding="utf-8")
    assert "1.9.4" in leaflet[:1_000]

