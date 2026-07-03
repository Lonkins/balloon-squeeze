"""The committed demo site: drift-locked to (records + renderer), fully offline."""

from __future__ import annotations

from pathlib import Path

from bsq.gallery import write_demo_site

_DEMO = Path(__file__).parent.parent / "docs" / "demo"


def test_committed_demo_site_matches_regeneration(tmp_path: Path) -> None:
    regenerated = {p.name: p.read_text(encoding="utf-8") for p in write_demo_site(tmp_path)}
    committed = {p.name: p.read_text(encoding="utf-8") for p in _DEMO.glob("*.html")}
    assert sorted(committed) == sorted(regenerated)
    for name, payload in regenerated.items():
        assert committed[name] == payload, f"docs/demo/{name} drifted from regeneration"


def test_demo_site_references_no_external_resources() -> None:
    for page in _DEMO.glob("*.html"):
        html = page.read_text(encoding="utf-8")
        assert "http://" not in html, f"{page.name} loads an external resource"
        assert "https://" not in html, f"{page.name} loads an external resource"


def test_demo_index_links_every_arm_replay() -> None:
    index = (_DEMO / "index.html").read_text(encoding="utf-8")
    for arm in ("A0_off", "A1_announced", "A1_implicit", "A2_silent", "A3_placebo"):
        assert f'href="{arm}.html"' in index
        assert (_DEMO / f"{arm}.html").is_file()
