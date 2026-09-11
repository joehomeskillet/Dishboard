"""Discover Flask url_map + templates and write ui-route-matrix.json.

Read-only source imports. Does not start a database or weaken auth.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import re
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = ROOT / 'reference_scaffold'
TEMPLATE_ROOT = SCAFFOLD / 'cafeteria' / 'templates'
MATRIX_PATH = ROOT / 'docs' / 'superpowers' / 'backlog-0909' / 'ui-route-matrix.json'
SOURCE_COMMIT = '5f5f6cb535922db8453c68d871279d6b2e203391'

sys.path.insert(0, str(SCAFFOLD))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault('DEMO_MODE', 'true')
os.environ.setdefault('SESSION_REDIS_URL', '')
os.environ.setdefault('FLASK_SECRET_KEY', 'ui-inventory-discovery')
os.environ.setdefault('APP_ENV', 'development')

import cafeteria  # type: ignore[import-not-found]  # noqa: E402
from capture import capture_provenance  # noqa: E402

cafeteria.init_app_database = lambda _app: None  # type: ignore[method-assign]


ROLE_CAPS = {
    'anonymous': [],
    'Cafeteria.Editor': [
        'draft.read', 'draft.write', 'csv.validate', 'csv.import', 'csv.export',
        'preview.read', 'masterdata.write', 'recipe.write',
    ],
    'Cafeteria.Publisher': [
        'draft.read', 'draft.write', 'csv.validate', 'csv.import', 'csv.export',
        'preview.read', 'publication.validate', 'publication.publish',
        'publication.withdraw', 'audit.read', 'masterdata.write', 'recipe.write',
        'recipe.import',
    ],
    'Cafeteria.Admin': ['*'],
}

# Statically discovered method-level restrictions where a handler body requires
# a capability that excludes one or more roles carried by the route.
METHOD_RESTRICTIONS: dict[str, dict[str, dict[str, str]]] = {
    'admin.screen_template_assignment': {
        'POST': {
            'capability': 'settings.write',
            'evidence': 'reference_scaffold/cafeteria/admin/screen_template_routes.py:96-97',
        },
    },
}


def method_roles_for(endpoint: str) -> dict[str, list[str]]:
    restrictions = METHOD_RESTRICTIONS.get(endpoint)
    if not restrictions:
        return {}
    allowed_by_method: dict[str, list[str]] = {}
    for method, info in restrictions.items():
        cap = info['capability']
        allowed_by_method[method] = [
            role for role, caps in ROLE_CAPS.items()
            if role != 'anonymous' and ('*' in caps or cap in caps)
        ]
    return allowed_by_method


NAV_CONDITIONALS = {
    'can_browse_recipes': {
        'predicate': "capabilities() & {'*', 'draft.read'}",
        'visible_for': ['Cafeteria.Editor', 'Cafeteria.Publisher', 'Cafeteria.Admin'],
        'items': ['Rezepte', 'Kochbücher'],
    },
    'can_manage_users': {
        'predicate': "'*' in allowed or 'users.manage' in allowed",
        'visible_for': ['Cafeteria.Admin'],
        'items': ['Benutzer & Zugriff'],
    },
    'can_configure_display': {
        'predicate': "'*' in capabilities()  # Admin wildcard only",
        'visible_for': ['Cafeteria.Admin'],
        'items': ['Design & Marke', 'Bereiche & Zeiten'],
    },
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unwrap(fn):
    current = fn
    seen = set()
    while hasattr(current, '__wrapped__') and id(current) not in seen:
        seen.add(id(current))
        current = current.__wrapped__
    return current


def view_source(fn) -> str:
    try:
        return inspect.getsource(unwrap(fn))
    except (OSError, TypeError):
        return ''


_CAP_RE = re.compile(r"require_capability\(\s*['\"]([^'\"]+)['\"]")
_KNOWN_CAPS = {
    cap for caps in ROLE_CAPS.values() for cap in caps if cap != '*'
} | {'users.manage', 'settings.write', 'api.keys.manage'}


def capability_of(source: str, view=None, rule_args: tuple[str, ...] = ()) -> str | None:
    """Capability from view source, wrappers, closures, or a unique helper."""
    found = _CAP_RE.findall(source)
    if found:
        return found[0]
    if view is None:
        return None
    collected: list[str] = []
    seen: set[int] = set()

    def take(obj) -> None:
        if obj is None or not callable(obj) or id(obj) in seen:
            return
        seen.add(id(obj))
        try:
            collected.extend(_CAP_RE.findall(inspect.getsource(obj)))
        except (OSError, TypeError):
            pass
        code = getattr(obj, '__code__', None)
        freevars = code.co_freevars if code is not None else ()
        for name, cell in zip(freevars, getattr(obj, '__closure__', None) or ()):
            try:
                value = cell.cell_contents
            except ValueError:
                continue
            if name == 'capability' and isinstance(value, str) and value in _KNOWN_CAPS:
                collected.append(value)
            else:
                take(value)
        take(getattr(obj, '__wrapped__', None))

    take(view)
    inner = unwrap(view)
    module = inspect.getmodule(inner)
    try:
        inner_src = inspect.getsource(inner)
    except (OSError, TypeError):
        inner_src = ''
    if module is not None:
        for name in re.findall(r'^@(\w+)', inner_src, re.M):
            take(getattr(module, name, None))
        branch = re.search(r'(\w+)\(family\) if family else (\w+)\(\)', inner_src)
        if branch is not None:
            chosen = branch.group(1) if 'family' in rule_args else branch.group(2)
            take(getattr(module, chosen, None))
    unique = list(dict.fromkeys(collected))
    return unique[0] if len(unique) == 1 else None


ENDPOINT_TEMPLATES = json.loads(
    Path(__file__).with_name('endpoint_templates.json').read_text(encoding='utf-8')
)

FRAGMENT_ENDPOINTS = {'admin.header_get', 'admin.service_get'}
FORCE_DOWNLOAD = {
    'admin.print_week', 'admin.recipe_asset', 'admin.export_csv',
    'admin.recipe_revision_pdf', 'admin.print_template_preview',
    'admin.recipe_print_template_preview', 'admin.branding_preview_css',
    'admin.branding_logo', 'branding.stylesheet', 'branding.logo',
}


def templates_in(endpoint: str, source: str) -> list[str]:
    found = re.findall(r"['\"]((?:admin|public|signage|auth|api)/[^'\"]+\.html)['\"]", source)
    found += re.findall(r"['\"](_[a-z0-9_]+\.html)['\"]", source)
    found += ENDPOINT_TEMPLATES.get(endpoint, [])
    if endpoint in {'admin.cafeteria', 'admin.patienten'}:
        found.append(f"admin/{endpoint.split('.')[-1]}.html")
    return sorted(set(found))


def classify(endpoint: str, rule: str, methods: set[str], templates: list[str], source: str) -> str:
    if endpoint == 'static':
        return 'static'
    if endpoint in FORCE_DOWNLOAD or rule.endswith(('.csv', '.pdf', '.png', '.css')):
        return 'download'
    if endpoint == 'auth.frontchannel_logout':
        return 'empty_response'
    if endpoint in FRAGMENT_ENDPOINTS:
        return 'html_fragment'
    if endpoint.startswith(('api.', 'api_v1.', 'fhir.', 'health.')) and endpoint != 'api_docs.docs':
        return 'json'
    if 'jsonify' in source and 'render_template' not in source and not templates:
        return 'json'
    if methods <= {'POST'} and not templates:
        if 'redirect(' in source:
            return 'redirect'
        return 'post_only'
    if templates or 'render_template' in source or endpoint in ENDPOINT_TEMPLATES:
        return 'html'
    if 'redirect(' in source and 'render_template' not in source:
        return 'redirect'
    if methods <= {'POST'}:
        return 'post_only'
    return 'html'


def owning_mp(endpoint: str, classification: str) -> str:
    mapping = (
        ('static', 'unmapped'),
        ('health.', 'unmapped'),
        ('fhir.', 'MP-API-REGRESSION'),
        ('api_v1.', 'MP-API-REGRESSION'),
        ('api.', 'MP-API-REGRESSION'),
        ('api_docs.', 'MP-UI-API'),
        ('branding.', 'MP-UI-BRAND-OPS'),
        ('public.', 'MP-UI-SPECIAL-OUTPUTS'),
        ('signage.', 'MP-UI-SPECIAL-OUTPUTS'),
        ('auth.', 'MP-UI-AUTH'),
        ('admin.api_', 'MP-UI-API'),
        ('admin.local_user', 'MP-UI-LOCAL-USERS'),
        ('admin.access_history', 'MP-UI-ACCESS-HISTORY'),
        ('admin.screen_template', 'MP-UI-OUTPUT-HUBS'),
        ('admin.branding', 'MP-UI-BRAND-OPS'),
        ('admin.operations', 'MP-UI-BRAND-OPS'),
        ('admin.schedule_defaults', 'MP-UI-BRAND-OPS'),
        ('admin.display', 'MP-UI-REF-SETTINGS'),
        ('admin.screens', 'MP-UI-OUTPUT-HUBS'),
        ('admin.vorlagen', 'MP-UI-OUTPUT-HUBS'),
        ('admin.screen_', 'MP-UI-OUTPUT-HUBS'),
        ('admin.print_template', 'MP-UI-PRINT-EDITOR'),
        ('admin.recipe_print', 'MP-UI-PRINT-EDITOR'),
        ('admin.recipe_template', 'MP-UI-PRINT-EDITOR'),
        ('admin.print_week', 'MP-TPL-PAPER'),
        ('admin.master_data', 'MP-UI-FOUNDATIONS'),
        ('admin.recipes_', 'MP-UI-RECIPE-LISTS'),
        ('admin.recipe_new', 'MP-UI-RECIPE-FORMS'),
        ('admin.recipe_edit', 'MP-UI-RECIPE-FORMS'),
        ('admin.recipe_form', 'MP-UI-RECIPE-FORMS'),
        ('admin.recipe_status', 'MP-UI-RECIPE-FORMS'),
        ('admin.recipe_rev', 'MP-UI-REF-DETAIL'),
        ('admin.recipe_freeze', 'MP-UI-RECIPE-TOOLS'),
        ('admin.recipe_scale', 'MP-UI-RECIPE-TOOLS'),
        ('admin.recipe_image', 'MP-UI-RECIPE-TOOLS'),
        ('admin.recipe_asset', 'MP-UI-RECIPE-TOOLS'),
        ('admin.cookbook', 'MP-UI-COOKBOOKS'),
        ('admin.menu_collection', 'MP-UI-REF-LIST'),
        ('admin.week_management', 'MP-UI-WEEKS'),
        ('admin.week_create', 'MP-UI-WEEKS'),
        ('admin.week_review', 'MP-UI-WEEKS'),
        ('admin.import', 'MP-UI-COPY-IMPORT'),
        ('admin.export_csv', 'MP-UI-COPY-IMPORT'),
        ('admin.copy', 'MP-UI-COPY-IMPORT'),
        ('admin.menu', 'MP-UI-MENU-EDITOR'),
        ('admin.component', 'MP-UI-COMPONENTS'),
        ('admin.preview', 'MP-UI-PREVIEW'),
        ('admin.publish', 'MP-UI-WEEKS'),
        ('admin.header', 'MP-UI-WEEKS'),
        ('admin.service', 'MP-UI-WEEKS'),
        ('admin.cafeteria', 'MP-UI-REF-WORKSPACE'),
        ('admin.patienten', 'MP-UI-REF-WORKSPACE'),
        ('admin.dashboard', 'MP-UI-SHELL'),
    )
    for prefix, mp in mapping:
        if endpoint == prefix.rstrip('.') or endpoint.startswith(prefix):
            return mp
    if classification in {'json', 'static', 'download'} and endpoint.startswith('admin.'):
        return 'unmapped'
    return 'unmapped'


def roles_for(capability: str | None, classification: str, endpoint: str) -> list[str]:
    if classification == 'static' or endpoint.startswith(('public.', 'signage.', 'health.', 'branding.')):
        return ['anonymous']
    if endpoint.startswith(('api.', 'api_v1.', 'fhir.', 'api_docs.')):
        return ['anonymous']  # keyed separately; HTML docs public
    if endpoint.startswith('auth.'):
        return ['anonymous']
    if capability is None:
        return ['Cafeteria.Editor', 'Cafeteria.Publisher', 'Cafeteria.Admin']
    if capability == 'users.manage' or capability == 'api.keys.manage' or capability == 'settings.write':
        return ['Cafeteria.Admin']
    allowed = []
    for role, caps in ROLE_CAPS.items():
        if role == 'anonymous':
            continue
        if '*' in caps or capability in caps:
            allowed.append(role)
    return allowed or ['Cafeteria.Admin']


def layout_variant(endpoint: str, templates: list[str]) -> str:
    joined = ' '.join(templates)
    if endpoint.startswith('signage.') or 'signage/' in joined:
        return 'signage'
    if 'print_' in joined or endpoint.endswith('print_week') or '/druck/' in endpoint:
        return 'print'
    if endpoint.startswith('auth.') or 'auth/' in joined:
        return 'auth'
    if endpoint.startswith('public.') or 'public/' in joined:
        return 'public'
    if 'api/docs' in joined:
        return 'api_docs'
    if endpoint.startswith('admin.'):
        return 'admin_tabler'
    return 'none'


def template_kind(rel: str) -> str:
    name = Path(rel).name
    if name.startswith('_') or rel in {
        'admin/base_tabler.html', 'public/base_public.html', 'signage/base_signage.html', 'base.html',
    }:
        if name.startswith('_'):
            return 'partial'
        return 'layout'
    return 'page'


def template_graph() -> dict[str, dict]:
    graph: dict[str, dict] = {}
    for path in sorted(TEMPLATE_ROOT.rglob('*.html')):
        rel = str(path.relative_to(TEMPLATE_ROOT)).replace('\\', '/')
        text = path.read_text(encoding='utf-8')
        extends = re.findall(r"\{\%\s*extends\s+['\"]([^'\"]+)['\"]", text)
        includes = re.findall(r"\{\%\s*include\s+['\"]([^'\"]+)['\"]", text)
        macros = re.findall(r"\{\%\s*from\s+['\"]([^'\"]+)['\"]", text)
        graph[rel] = {
            'path': rel,
            'kind': template_kind(rel),
            'extends': extends,
            'includes': sorted(set(includes + macros)),
            'sha256': sha256_file(path),
            'used_by_endpoints': [],
            'owning_mp': 'unmapped',
        }
    return graph


def attach_templates(graph: dict[str, dict], endpoint: str, names: list[str], mp: str) -> None:
    pending = list(names)
    seen: set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen or name not in graph:
            continue
        seen.add(name)
        row = graph[name]
        if endpoint not in row['used_by_endpoints']:
            row['used_by_endpoints'].append(endpoint)
        if row['owning_mp'] == 'unmapped':
            row['owning_mp'] = mp
        pending.extend(row['extends'])
        pending.extend(row['includes'])


def family_note(rule: str) -> list[str]:
    if '<any(cafeteria, patienten):family>' in rule or '<any(cafeteria,patienten):family>' in rule:
        return ['cafeteria', 'patienten']
    if '<any(cafeteria, patienten):channel>' in rule:
        return ['cafeteria', 'patienten']
    return []


def build(identity: Mapping[str, str] | None = None) -> dict:
    app = cafeteria.create_app()
    graph = template_graph()
    routes = []
    for rule in sorted(app.url_map.iter_rules(), key=lambda item: (item.endpoint, item.rule)):
        methods = sorted(m for m in (rule.methods or set()) if m not in {'HEAD', 'OPTIONS'})
        view = app.view_functions.get(rule.endpoint)
        source = view_source(view) if view else ''
        templates = templates_in(rule.endpoint, source)
        classification = classify(rule.endpoint, rule.rule, set(methods), templates, source)
        capability = capability_of(source, view, tuple(rule.arguments or ()))
        mp = owning_mp(rule.endpoint, classification)
        attach_templates(graph, rule.endpoint, templates, mp)
        blueprint = rule.endpoint.split('.')[0] if '.' in rule.endpoint else ''
        routes.append({
            'endpoint': rule.endpoint,
            'rule': rule.rule,
            'methods': methods,
            'blueprint': blueprint,
            'classification': classification,
            'visual': classification in {'html', 'html_fragment'},
            'templates': templates,
            'capability': capability,
            'roles': roles_for(capability, classification, rule.endpoint),
            'method_roles': method_roles_for(rule.endpoint),
            'layout_variant': layout_variant(rule.endpoint, templates),
            'owning_mp': mp,
            'family_variants': family_note(rule.rule),
            'module': getattr(inspect.getmodule(unwrap(view)), '__name__', None) if view else None,
            'source_discovered': True,
            'fixture': fixture_for(rule.endpoint, classification),
            'states': states_for(rule.endpoint, classification),
            'hooks': hooks_for(rule.endpoint, templates),
        })
    for rel, row in graph.items():
        row['used_by_endpoints'] = sorted(row['used_by_endpoints'])
        if not row['used_by_endpoints']:
            row['owning_mp'] = template_fallback_mp(rel)
    return {
        'meta': {
            **capture_provenance(identity),
            'mp_id': 'MP-UI-INVENTORY',
            'source_commit': SOURCE_COMMIT,
            'schema': 25,
            'schema_note': (
                'Actual production source is 5f5 / schema 25. Schema 26/27 and undeployed '
                'foundation consumers are not claimed as present.'
            ),
            'baseline_status': 'proposed_never_user_approved',
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'discovery': 'cafeteria.create_app().url_map plus templates/*.html on disk',
            'route_count': len(routes),
            'template_count': len(graph),
            'html_route_count': sum(1 for item in routes if item['visual']),
        },
        'common': {
            'roles': ROLE_CAPS,
            'capability_semantics': (
                'The capability field records the statically detected require_capability literal; '
                'null indicates that the capability is not statically determinable (for example, '
                'method-dependent protected wrappers using GET draft.read and POST recipe.write or '
                'masterdata.write); effective role assignments are additionally validated by '
                'runtime test test_matrix_roles_match_server_side_authorization, which queries '
                'every visual admin GET route as anonymous, Editor, Publisher, and Admin.'
            ),
            'navigation': {
                'sidebar_template': 'admin/_workflow_sidebar.html',
                'sidebar_insufficient': True,
                'note': 'Inventory includes editors, subpages, dialogs, print, signage, API, not only sidebar links.',
                'conditionals': NAV_CONDITIONALS,
                'always_visible_admin': [
                    'Wochenpläne', 'Wochenverwaltung', 'Menüs', 'Komponenten', 'Grundlagen',
                    'CSV Import', 'Screens', 'Vorlagen', 'API & Schnittstellen', 'Abmelden',
                ],
            },
            'assets': {
                'tabler_core': '1.5.0',
                'tabler_icons': '3.46.0',
                'tabler_lock': 'reference_scaffold/cafeteria/static/vendor/tabler.lock.json',
                'admin_css': ['tokens.css', 'vendor/tabler/tabler.min.css', 'admin-tabler.css', 'menu-images.css'],
                'admin_js': ['vendor/tabler/tabler.min.js', 'admin.js'],
                'public_css': ['tokens.css', 'vendor/tabler/tabler.min.css', 'public.css', 'menu-images.css', 'food-symbols.css'],
                'signage_css': ['tokens.css', 'vendor/tabler/tabler.min.css', 'signage.css'],
                'signage_js': ['signage.js'],
                'auth_css': ['tokens.css', 'app.css'],
            },
            'fonts': {
                'declared_stack_ui': '"Fira Sans", Aptos, "Segoe UI Variable", "Segoe UI", ui-sans-serif, sans-serif',
                'declared_stack_display': '"Fira Sans", Aptos, "Segoe UI Variable Display", "Segoe UI", ui-sans-serif, sans-serif',
                'self_hosted': [
                    'static/fonts/fira-sans-400.woff2',
                    'static/fonts/fira-sans-500.woff2',
                    'static/fonts/fira-sans-600.woff2',
                    'static/fonts/fira-sans-700.woff2',
                ],
                'masterprompt_body': 'Arial, Helvetica, sans-serif',
                'masterprompt_heading': 'Georgia, "Times New Roman", serif',
                'conflict': (
                    'Source 5f5 ships Fira Sans via tokens.css. Masterprompt 2026-09-09 names Arial/Georgia. '
                    'MP-UI-BRAND-DECISION owns the mapping; this inventory records the conflict, does not resolve it.'
                ),
            },
            'hooks': [
                'csrf_token / _csrf / csrf_token form fields',
                '_form_context signed form tokens',
                'data-menu-editor, data-add-row, data-remove-row, data-move-row, data-sticky',
                'data-admin-icon-action + Tabler tooltip',
                'data-confirm native confirm',
                'data-retry-page, data-error-link, .error-region[role=alert]',
                'data-bs-toggle / data-bs-target dialogs (week-publish-modal)',
                'data-signage-revision / data-signage-clock / signage.js poll',
                'data-brand-stylesheet branding CSS last',
                'aria-current on active nav, aria-invalid/aria-describedby field errors',
            ],
            'source_hashes': {
                'database/schema.sql': sha256_file(ROOT / 'database' / 'schema.sql'),
                'database/seed.sql': sha256_file(ROOT / 'database' / 'seed.sql'),
                'database/seed_demo.sql': sha256_file(ROOT / 'database' / 'seed_demo.sql'),
                'demo/snapshots/cafeteria_kw36.json': sha256_file(ROOT / 'demo' / 'snapshots' / 'cafeteria_kw36.json'),
                'demo/snapshots/patienten_kw36.json': sha256_file(ROOT / 'demo' / 'snapshots' / 'patienten_kw36.json'),
            },
        },
        'routes': routes,
        'templates': [graph[key] for key in sorted(graph)],
        'states': SHARED_STATES,
        'coverage_blocks': COVERAGE_BLOCKS,
    }


def template_fallback_mp(rel: str) -> str:
    if rel.startswith('signage/') or rel.startswith('public/') or rel.startswith('_'):
        return 'MP-UI-SPECIAL-OUTPUTS'
    if rel.startswith('auth/'):
        return 'MP-UI-AUTH'
    if rel.startswith('api/'):
        return 'MP-UI-API'
    fallbacks = {
        'admin/_macros.html': 'MP-UI-MACROS',
        'admin/_workflow_sidebar.html': 'MP-UI-SHELL',
        'admin/base_tabler.html': 'MP-UI-SHELL',
        'admin/_country_select.html': 'MP-UI-COMPONENTS',
        'admin/_rezepte_fields.html': 'MP-UI-RECIPE-FORMS',
        'admin/_recipe_template_selection.html': 'MP-UI-PRINT-EDITOR',
        'admin/_local_user_forms.html': 'MP-UI-LOCAL-USERS',
        'admin/grundlagen_unavailable.html': 'MP-UI-FOUNDATIONS',
        'admin/grundlagen_location_conflict.html': 'MP-UI-FOUNDATIONS',
        'admin/print_template_unavailable.html': 'MP-UI-PRINT-EDITOR',
        'admin/screen_template_unavailable.html': 'MP-UI-OUTPUT-HUBS',
        'admin/recipe_template_error.html': 'MP-UI-PRINT-EDITOR',
        'admin/rezepte_conflict.html': 'MP-UI-RECIPE-FORMS',
        'admin/local_user_unavailable.html': 'MP-UI-LOCAL-USERS',
        'base.html': 'MP-UI-SHELL',
    }
    return fallbacks.get(rel, 'unmapped')


def fixture_for(endpoint: str, classification: str) -> str:
    if classification not in {'html', 'html_fragment'}:
        return 'not_visual'
    if endpoint.startswith(('public.', 'signage.')):
        return 'demo_snapshots_kw36_synthetic'
    if endpoint.startswith('auth.'):
        return 'local_auth_enabled_no_production_persons'
    return 'isolated_pg_schema25_seed_plus_synthetic_week'


def states_for(endpoint: str, classification: str) -> list[str]:
    if classification == 'html_fragment':
        return ['default', 'access_denied_401', 'access_denied_403']
    if classification != 'html':
        return []
    states = ['default']
    if endpoint.startswith('admin.'):
        states += ['empty', 'invalid', 'access_denied_401', 'access_denied_403']
    if 'menu' in endpoint:
        states += ['form_error', 'origin_conflict']
    if endpoint in {'admin.cafeteria', 'admin.patienten'}:
        states += ['dialog_publish', 'review_open', 'live']
    if endpoint.startswith('signage.') and 'cafeteria' in endpoint:
        states += ['closed']
    if endpoint.startswith(('public.', 'signage.')):
        states += ['unavailable_404']
    if endpoint == 'auth.local_login':
        states += ['invalid_credentials']
    if endpoint == 'auth.login':
        states += ['demo_redirect', 'entra_unconfigured']
    return states


def hooks_for(endpoint: str, templates: list[str]) -> list[str]:
    hooks = []
    joined = ' '.join(templates)
    if endpoint.startswith('admin.'):
        hooks += ['admin.js', 'tabler.min.js', 'csrf']
    if 'menu_editor' in joined:
        hooks.append('data-menu-editor')
    if endpoint in {'admin.cafeteria', 'admin.patienten'}:
        hooks.append('#week-publish-modal')
    if endpoint.startswith('signage.'):
        hooks.append('signage.js')
    if endpoint.startswith('auth.'):
        hooks.append('csrf_token')
    return hooks


def _captures(*rows: tuple[str, str]) -> list[dict[str, str]]:
    return [{'endpoint': endpoint, 'suffix': suffix} for endpoint, suffix in rows]


SHARED_STATES = [
    {
        'id': 'login',
        # auth/error.html is a template rendered by auth.login/auth.callback, not an endpoint.
        'routes': ['auth.local_login', 'auth.login'],
        'owning_mp': 'MP-UI-AUTH',
        'note': 'Auth layout without admin sidebar.',
        'fixture': 'local_auth_enabled_no_production_persons',
        'captures': _captures(('auth.local_login', ''), ('auth.login', 'auth-login')),
    },
    {
        'id': 'empty',
        'routes': ['admin.menu_collection', 'admin.recipes_list', 'admin.cookbooks_list', 'admin.master_data_list', 'admin.components_get'],
        'owning_mp': 'MP-UI-MACROS',
        'note': 'Empty vs no-search-hit vs no-permission must stay distinct.',
        'fixture': 'isolated_pg_schema25_seed_before_prepare_entities',
        'captures': _captures(
            ('admin.menu_collection', 'empty'), ('admin.recipes_list', 'empty'),
            ('admin.cookbooks_list', 'empty'), ('admin.master_data_list', 'empty'),
            ('admin.components_get', 'empty'),
        ),
    },
    {
        'id': 'invalid',
        'routes': ['admin.menu_get', 'admin.display_settings', 'admin.recipe_edit'],
        'owning_mp': 'MP-UI-MACROS',
        'note': 'Server-side errors keep values and original form tokens.',
        'fixture': 'isolated_pg_schema25_seed_plus_synthetic_entities_invalid_submit',
        'captures': _captures(
            ('admin.menu_get', 'invalid'), ('admin.display_settings', 'invalid'),
            ('admin.recipe_edit', 'invalid'),
        ),
    },
    {
        'id': 'access_denied',
        'routes': ['admin.*'],
        'owning_mp': 'MP-UI-AUTH',
        'note': '401 unauthenticated, 403 authenticated without capability. Flask default HTML unless a template is registered.',
        'fixture': 'anonymous_context_and_synthetic_editor_without_users_manage',
        'captures': _captures(('admin.cafeteria', 'anonymous-401'), ('admin.local_users_list', 'editor-403')),
    },
    {
        'id': 'dialogs',
        'routes': ['admin.cafeteria', 'admin.patienten'],
        'owning_mp': 'MP-UI-WEEKS',
        'note': 'week-publish-modal and similar Bootstrap dialogs are inventory rows, not sidebar items.',
        'fixture': 'isolated_pg_schema25_seed_plus_synthetic_week',
        'captures': _captures(('admin.cafeteria', 'dialog-publish')),
    },
    {
        'id': 'role_navigation',
        'routes': ['admin.cafeteria'],
        'owning_mp': 'MP-UI-SHELL',
        'note': 'Conditional sidebar per role; nav_items recorded per capture row.',
        'fixture': 'synthetic_entra_users_editor_publisher_admin',
        'captures': _captures(
            ('admin.cafeteria', 'role-nav-editor'),
            ('admin.cafeteria', 'role-nav-publisher'),
            ('admin.cafeteria', 'role-nav-admin'),
        ),
    },
]

COVERAGE_BLOCKS = [
    {
        'id': 'entra_callback_live_tenant',
        'reason': 'Cannot safely synthesize a real Entra tenant callback or production person.',
        'endpoints': ['auth.callback', 'auth.frontchannel_logout'],
        'status': 'blocked_not_fake_pass',
    },
    {
        'id': 'yodeck_physical_player',
        'reason': 'Physical Yodeck/Raspberry player is MP-QA-PLAYER, not this inventory WP.',
        'endpoints': ['signage.cafeteria_day', 'signage.cafeteria_week', 'signage.patient_day', 'signage.patient_week'],
        'status': 'out_of_scope_source_and_synthetic_html_only',
    },
    {
        'id': 'native_pdf_bytes',
        'reason': 'PDF download bytes and paper layout are separate from HTML screenshots.',
        'endpoints': ['admin.print_week', 'admin.recipe_revision_pdf', 'admin.print_template_preview', 'admin.recipe_print_template_preview'],
        'status': 'classified_download_not_visual',
    },
    {
        'id': 'schema26_27_undeployed',
        'reason': 'Source is schema 25. Do not invent dish-template or schema27 foundation consumer pages.',
        'endpoints': [],
        'status': 'not_applicable',
    },
]


def write_matrix(target: Path | None = None, identity: Mapping[str, str] | None = None) -> Path:
    """Write the matrix. Callers may redirect it so a regression run keeps the baseline."""
    destination = Path(target) if target is not None else MATRIX_PATH
    payload = build(identity)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'wrote {destination} routes={payload["meta"]["route_count"]} '
          f'templates={payload["meta"]["template_count"]}')
    return destination


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=None,
                        help='write here instead of the versioned matrix')
    parser.add_argument('--wp-id', default=None)
    parser.add_argument('--lane', default=None)
    parser.add_argument('--model', default=None)
    args = parser.parse_args(argv)
    supplied = {
        key: value for key, value in (
            ('wp_id', args.wp_id), ('lane', args.lane), ('model', args.model),
        ) if value
    }
    write_matrix(args.out, supplied or None)


if __name__ == '__main__':
    main()
