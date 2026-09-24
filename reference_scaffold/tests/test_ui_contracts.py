from __future__ import annotations

import re
from pathlib import Path

import pytest
from flask import Flask
from jinja2 import Environment, FileSystemLoader, StrictUndefined, nodes

from cafeteria.template_filters import register_template_filters
from cafeteria.ui import register_ui


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
    pending = [(path, False) for path in PATIENT_TEMPLATES]
    checked = set()

    def scan(node, prices_disabled, relative_path):
        # Only this explicit constant guard is proved unreachable; all other branches stay checked.
        if isinstance(node, nodes.With):
            scoped_disabled = prices_disabled
            for target, value in zip(node.targets, node.values):
                if isinstance(target, nodes.Name) and target.name == 'show_prices':
                    scoped_disabled = isinstance(value, nodes.Const) and value.value is False
                scan(value, prices_disabled, relative_path)
            for child in node.body:
                scan(child, scoped_disabled, relative_path)
            return
        if (prices_disabled and isinstance(node, nodes.If)
                and isinstance(node.test, nodes.Name) and node.test.name == 'show_prices'):
            for child in (*node.elif_, *node.else_):
                scan(child, prices_disabled, relative_path)
            return
        if isinstance(node, nodes.Name) and node.name == 'show_prices' and node.ctx != 'load':
            assert not prices_disabled, relative_path  # A rebind invalidates the constant proof.
        if isinstance(node, nodes.Include):
            assert isinstance(node.template, nodes.Const), relative_path
            assert isinstance(node.template.value, str), relative_path
            pending.append((node.template.value, prices_disabled and node.with_context))
        for _, value in node.iter_fields():
            for child in value if isinstance(value, list) else [value]:
                if isinstance(child, nodes.Node):
                    scan(child, prices_disabled, relative_path)
                elif isinstance(child, str):
                    assert forbidden.search(child) is None, relative_path

    while pending:
        relative_path, prices_disabled = pending.pop()
        if (relative_path, prices_disabled) in checked:
            continue
        checked.add((relative_path, prices_disabled))
        scan(Environment().parse(_template(relative_path)), prices_disabled, relative_path)


@pytest.mark.parametrize('included_source', ['<span>CHF</span>', "{% include unknown_template %}"])
def test_patient_include_guard_rejects_hidden_costs_and_dynamic_templates(monkeypatch, included_source):
    original = _template
    monkeypatch.setitem(globals(), '_template', lambda path: (
        included_source if path == '_menu_metadata.html' else original(path)
    ))
    with pytest.raises(AssertionError, match='_menu_metadata.html'):
        test_patient_templates_are_structurally_cost_free()


@pytest.mark.parametrize('binding', ['', 'show_prices=true', 'show_prices=unknown'])
@pytest.mark.parametrize('include_index', [0, 1])
def test_patient_cost_guard_requires_false_at_each_include(monkeypatch, binding, include_index):
    original = _template
    parts = original('admin/patienten.html').split('show_prices=false')
    assert len(parts) == 3
    changed = parts[0] + binding + parts[1] + 'show_prices=false' + parts[2] if include_index == 0 else (
        parts[0] + 'show_prices=false' + parts[1] + binding + parts[2]
    )
    monkeypatch.setitem(globals(), '_template', lambda path: (
        changed if path == 'admin/patienten.html' else original(path)
    ))
    with pytest.raises(AssertionError, match='admin/_week_menu_card.html'):
        test_patient_templates_are_structurally_cost_free()


@pytest.mark.parametrize('mutation', ['unguarded', 'true_guard', 'rebind', 'else_cost'])
def test_patient_shared_card_rejects_reachable_costs(monkeypatch, mutation):
    original = _template
    source = original('admin/_week_menu_card.html')
    if mutation == 'unguarded':
        source += '<span>CHF</span>'
    elif mutation == 'true_guard':
        source = source.replace('{% if show_prices %}', '{% if true %}')
    elif mutation == 'rebind':
        source = '{% set show_prices=true %}' + source
    else:
        source = source.replace('{% if show_prices %}', '{% if show_prices %}{% else %}CHF')
    monkeypatch.setitem(globals(), '_template', lambda path: (
        source if path == 'admin/_week_menu_card.html' else original(path)
    ))
    with pytest.raises(AssertionError, match='admin/_week_menu_card.html'):
        test_patient_templates_are_structurally_cost_free()


def test_patient_cost_guard_requires_include_context(monkeypatch):
    original = _template
    changed = original('admin/patienten.html').replace(
        "include 'admin/_week_menu_card.html'", "include 'admin/_week_menu_card.html' without context"
    )
    monkeypatch.setitem(globals(), '_template', lambda path: (
        changed if path == 'admin/patienten.html' else original(path)
    ))
    with pytest.raises(AssertionError, match='admin/_week_menu_card.html'):
        test_patient_templates_are_structurally_cost_free()


def test_signage_players_are_fixed_noninteractive_surfaces() -> None:
    interactive = re.compile(
        r"<(?:a|nav|form|button|input|select|textarea)\b", re.IGNORECASE
    )
    for relative_path in SIGNAGE_TEMPLATES:
        source = _template(relative_path)
        assert 'extends "signage/base_signage.html"' in source, relative_path
        assert 'http-equiv="refresh"' not in source, relative_path
        assert interactive.search(source) is None, relative_path
        assert "?date=" not in source and "?profil=" not in source, relative_path

    base = _template("signage/base_signage.html")
    assert 'signage.js' in base and 'defer' in base
    assert 'data-signage-root' in base
    assert 'data-signage-clock' in base

    css = _compact((STATIC_ROOT / "signage.css").read_text(encoding="utf-8"))
    assert re.search(r"html,body\{[^}]*overflow:\s*hidden", css)
    assert re.search(
        r"\.signage-shell\{[^}]*width:\s*100vw[^}]*height:\s*100vh", css
    )


def test_signage_grids_and_readability_are_explicit() -> None:
    css = _compact((STATIC_ROOT / "signage.css").read_text(encoding="utf-8"))
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
    assert "3840 × 2160" not in patient_week
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
        assert 'class="public-shell print-shell"' in source, relative_path
        assert 'class="week-list"' in source, relative_path

    css = _compact((STATIC_ROOT / "app.css").read_text(encoding="utf-8"))
    assert "@page {" in css
    assert "size: A4 landscape" in css


@pytest.mark.parametrize('day_count', [5, 7])
def test_editor_grids_keep_profile_scope_visible_on_small_screens(day_count: int) -> None:
    patient = _template("admin/patienten.html")
    cafeteria = _template("admin/cafeteria.html")
    weekdays = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    application = Flask(__name__)
    application.config.update(TESTING=True, UI_LOCALE='de')
    register_template_filters(application)
    # Shared macros resolve icons and labels through the semantic UI layer (t/sem).
    register_ui(application)
    environment = application.jinja_env
    environment.loader = FileSystemLoader(str(TEMPLATE_ROOT))
    environment.undefined = StrictUndefined
    # Render the real grids and their shared cards/services, without a database or page-shell fixture.
    for family, source, days, meals in (
        ('patienten', patient, 7, ('LUNCH', 'DINNER')),
        ('cafeteria', cafeteria, day_count, ('LUNCH',)),
    ):
        cells = [dict(day=f'2026-09-{14 + day}', day_label=weekdays[day], day_short=f'{14 + day}. September',
                      meal=meal, meal_label=meal, option=option, option_label=option, row_version=0,
                      title='', dish_template=None, components=[], description='', note='',
                      accompaniment_code='none', accompaniment_name='', allergens=[], labels=[], origins=[],
                      allergen_review_status='not_checked', review_open=True, edit_url='/edit',
                      service_state='open', notice='', service_start='', service_end='', service_row_version=0,
                      internal_chf='5.00', external_chf='10.00')
                 for day in range(days) for meal in meals for option in ('MENU_1', 'VEGGIE')]
        grid = re.search(
            r'<section class="[^"]*\b(?:patient-admin-table|admin-week-days)\b[^"]*".*?</section>',
            source,
            re.S,
        )
        assert grid is not None
        weekday_assignment = re.search(r'{% set weekdays = .*?%}', patient)
        assert weekday_assignment is not None
        fragment = ("{% from 'admin/_macros.html' import icon, field, form_errors %}"
                    "{% set declarations = namespace(options=[]) %}" + weekday_assignment.group() + grid.group())
        with application.test_request_context():
            rendered = environment.from_string(fragment).render(
                cells=cells, day_cells=cells, family=family, status='empty', week_value='2026-09-14',
                week_csrf='synthetic-contract-token',
            )
        slots = re.findall(r'data-day="([^"]+)" data-meal="([^"]+)" data-option="([^"]+)"', rendered)
        assert len(slots) == days * len(meals) * 2
        assert set(slots) == {(cell['day'], cell['meal'], cell['option']) for cell in cells}
        assert re.findall(r'<h2>(.*?)</h2>', rendered) == weekdays[:days]
        assert rendered.count('<strong>Mittag</strong>') == days
        assert rendered.count('<strong>Abend</strong>') == (days if family == 'patienten' else 0)
        assert rendered.count(f'von {len(meals) * 2} Menükarten erfasst') == days
        assert ('CHF' in rendered) == (family == 'cafeteria')

    weekend_hint = re.search(r"{% if last_cell.day_label == 'Sonntag' %}.*?{% endif %}", cafeteria, re.S)
    assert weekend_hint is not None
    rendered_hint = environment.from_string(weekend_hint.group()).render(last_cell={'day_label': weekdays[day_count - 1]})
    assert ('Wochenendbetrieb: Samstag und Sonntag sind im Raster.' in rendered_hint) == (day_count == 7)

    css = _compact((STATIC_ROOT / "app.css").read_text(encoding="utf-8"))
    mobile = re.search(r"@media \(max-width: 900px\)\s*\{(.+?)@media", css)
    assert mobile is not None
    assert ".admin-sidebar { display: none" not in mobile.group(1)

    base_styles = re.findall(
        r"filename=['\"]([^'\"]+\.css)['\"]", _template("admin/base_tabler.html")
    )
    assert base_styles == [
        "tokens.css",
        "vendor/tabler/tabler.min.css",
        "admin-tabler.css",
        "ui-semantic.css",
        # Sidebar supplement follows the adapter and shared semantic foundation.
        "admin-nav.css",
        "menu-images.css",
    ]
    for template in (patient, cafeteria):
        # Week plan core (WP21) adds its compact day layout after the week adapter.
        assert re.findall(r"filename=['\"]([^'\"]+\.css)['\"]", template) == [
            "admin-week-tabler.css", "admin-wochenplan-kern.css"
        ]

    admin_css = _compact(
        " ".join(
            (STATIC_ROOT / stylesheet).read_text(encoding="utf-8")
            for stylesheet in (*base_styles, "admin-week-tabler.css")
        )
    )
    assert re.search(r'class="[^"]*\bpatient-admin-day\b[^"]*"', patient)
    assert re.search(r'class="[^"]*\badmin-day-card\b[^"]*"', cafeteria)
    assert re.search(r"\.patient-admin-day\b", admin_css)
    assert re.search(r"\.admin-day-card\b", admin_css)
