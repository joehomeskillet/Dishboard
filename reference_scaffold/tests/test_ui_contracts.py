from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ROOT = ROOT / "reference_scaffold" / "cafeteria" / "templates"
STATIC_ROOT = ROOT / "reference_scaffold" / "cafeteria" / "static"

PATIENT_TEMPLATES = (
    "admin/patienten.html",
    "public/patient_today.html",
    "public/patient_week.html",
    "public/print_patient_week.html",
    "signage/patient_day.html",
    "signage/patient_week.html",
)

SIGNAGE_TEMPLATES = (
    "signage/cafeteria_day.html",
    "signage/cafeteria_week.html",
    "signage/patient_day.html",
    "signage/patient_week.html",
)


def _template(relative_path: str) -> str:
    return (TEMPLATE_ROOT / relative_path).read_text(encoding="utf-8")


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def test_templates_parse_and_base_has_accessible_document_contract() -> None:
    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATE_ROOT)), autoescape=True
    )
    for path in sorted(TEMPLATE_ROOT.rglob("*.html")):
        environment.parse(path.read_text(encoding="utf-8"))

    base = _template("base.html")
    assert 'name="theme-color"' in base
    assert 'name="color-scheme"' in base
    assert 'class="skip-link"' in base
    assert 'href="#main-content"' in base


def test_patient_templates_are_structurally_cost_free() -> None:
    forbidden = re.compile(
        r"\b(?:CHF|Rappen|Intern|Extern|0\.00|price|prices|pricing|preis|preise|currency)\b"
        r"|(?:internal|external)_rappen|price-row|signage-price|admin-price",
        re.IGNORECASE,
    )
    for relative_path in PATIENT_TEMPLATES:
        source = _template(relative_path)
        assert forbidden.search(source) is None, relative_path
        assert "{% include" not in source, relative_path


def test_signage_players_are_fixed_noninteractive_surfaces() -> None:
    interactive = re.compile(
        r"<(?:a|nav|form|button|input|select|textarea)\b", re.IGNORECASE
    )
    for relative_path in SIGNAGE_TEMPLATES:
        source = _template(relative_path)
        assert '<meta http-equiv="refresh" content="300">' in source, relative_path
        assert "{% block body_class %}signage" in source, relative_path
        assert "{% block skip_link %}{% endblock %}" in source, relative_path
        assert interactive.search(source) is None, relative_path
        assert "?date=" not in source and "?profil=" not in source, relative_path

    css = _compact((STATIC_ROOT / "app.css").read_text(encoding="utf-8"))
    assert re.search(r"body\.signage\s*\{[^}]*overflow:\s*hidden", css)
    assert re.search(
        r"\.signage-shell\s*\{[^}]*width:\s*100vw[^}]*height:\s*100vh", css
    )


def test_signage_grids_and_readability_are_explicit() -> None:
    css = _compact((STATIC_ROOT / "app.css").read_text(encoding="utf-8"))
    assert re.search(r"\.cafe-week-layout\s*\{[^}]*repeat\(5,", css)
    assert re.search(r"\.patient-week-layout\s*\{[^}]*repeat\(7,", css)
    assert re.search(r"\.patient-day-layout\s*\{[^}]*repeat\(2,", css)
    assert "@media (min-width: 3000px)" in css

    cafeteria_day = _template("signage/cafeteria_day.html")
    cafeteria_week = _template("signage/cafeteria_week.html")
    for source in (cafeteria_day, cafeteria_week):
        assert "Mitarbeitende CHF" in source
        assert "Externe CHF" in source

    patient_week = _template("signage/patient_week.html")
    assert "3840 × 2160" in patient_week
    assert "snapshot.days" in patient_week
    assert "day.services" in patient_week


def test_responsive_navigation_focus_and_motion_contracts() -> None:
    css = _compact((STATIC_ROOT / "app.css").read_text(encoding="utf-8"))
    assert ":focus-visible" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "touch-action: manipulation" in css
    mobile = re.search(r"@media \(max-width: 900px\)\s*\{(.+?)@media", css)
    assert mobile is not None
    assert ".site-nav { display: none" not in mobile.group(1)


def test_print_views_use_dedicated_print_surface() -> None:
    for relative_path in (
        "public/print_cafeteria_week.html",
        "public/print_patient_week.html",
    ):
        source = _template(relative_path)
        assert "{% block body_class %}print-body{% endblock %}" in source, relative_path
        assert 'class="print-header"' in source, relative_path
        assert 'class="print-footer"' in source, relative_path

    css = _compact((STATIC_ROOT / "app.css").read_text(encoding="utf-8"))
    assert "@page {" in css
    assert "size: A4 landscape" in css


def test_editor_grids_keep_profile_scope_visible_on_small_screens() -> None:
    patient = _template("admin/patienten.html")
    cafeteria = _template("admin/cafeteria.html")
    assert "7 Tage × 2 Mahlzeiten × 2 Menüarten" in patient
    assert "5 Tage × 2 Menüarten" in cafeteria
    assert "Samstag und Sonntag: Cafeteria geschlossen" in cafeteria

    css = _compact((STATIC_ROOT / "app.css").read_text(encoding="utf-8"))
    mobile = re.search(r"@media \(max-width: 900px\)\s*\{(.+?)@media", css)
    assert mobile is not None
    assert ".admin-sidebar { display: none" not in mobile.group(1)
    assert re.search(r"\.admin-dish\s+(?:input|textarea|select)", css)
