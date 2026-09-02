from __future__ import annotations

import math
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / 'site'
INDEX = SITE / 'index.html'
STYLES = (
    SITE / 'foundation.css',
    SITE / 'components.css',
    SITE / 'responsive.css',
)
WORKFLOW = ROOT / '.github' / 'workflows' / 'pages.yml'


def parse_oklch_token(source: str, name: str) -> tuple[float, float, float]:
    match = re.search(
        rf'--color-{re.escape(name)}:\s*oklch\('
        r'([0-9.]+)%\s+([0-9.]+)\s+([0-9.]+)deg\)',
        source,
    )
    assert match is not None, f'missing semantic token --color-{name}'
    lightness, chroma, hue = (float(value) for value in match.groups())
    return lightness / 100, chroma, math.radians(hue)


def relative_luminance(color: tuple[float, float, float]) -> float:
    lightness, chroma, hue = color
    a = chroma * math.cos(hue)
    b = chroma * math.sin(hue)
    light = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    medium = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    short = (lightness - 0.0894841775 * a - 1.291485548 * b) ** 3
    red = 4.0767416621 * light - 3.3077115913 * medium + 0.2309699292 * short
    green = -1.2684380046 * light + 2.6097574011 * medium - 0.3413193965 * short
    blue = -0.0041960863 * light - 0.7034186147 * medium + 1.707614701 * short
    return (
        0.2126 * min(1, max(0, red))
        + 0.7152 * min(1, max(0, green))
        + 0.0722 * min(1, max(0, blue))
    )


def contrast_ratio(
    foreground: tuple[float, float, float],
    background: tuple[float, float, float],
) -> float:
    lighter, darker = sorted(
        (relative_luminance(foreground), relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def css_block(source: str, selector: str) -> str:
    match = re.search(rf'{re.escape(selector)}\s*\{{([^}}]+)\}}', source)
    assert match is not None, f'missing CSS block {selector}'
    return match.group(1)


class PageContractParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.references: list[str] = []
        self.start_tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        self.start_tags.append((tag, attributes))
        if element_id := attributes.get('id'):
            self.ids.add(element_id)
        for attribute in ('href', 'src'):
            if reference := attributes.get(attribute):
                self.references.append(reference)


def parse_page() -> tuple[str, PageContractParser]:
    source = INDEX.read_text(encoding='utf-8')
    parser = PageContractParser()
    parser.feed(source)
    return source, parser


def test_page_has_accessible_semantic_entrypoint() -> None:
    source, parser = parse_page()
    html = next(attributes for tag, attributes in parser.start_tags if tag == 'html')
    assert html.get('lang') == 'de'
    assert len(re.findall(r'<h1(?:\s|>)', source, flags=re.IGNORECASE)) == 1
    assert re.search(r'<title>[^<]+</title>', source, flags=re.IGNORECASE)
    assert re.search(r'<meta\s+name="viewport"', source, flags=re.IGNORECASE)
    assert re.search(r'<meta\s+http-equiv="Content-Security-Policy"', source, flags=re.IGNORECASE)
    assert re.search(r'<a\s+class="skip-link"\s+href="#main"', source)
    assert re.search(r'<main\s+id="main"', source)
    assert re.search(r'<nav\s+aria-label="[^\"]+"', source)
    assert '<script' not in source.lower()
    assert not re.search(r'\sstyle=', source, flags=re.IGNORECASE)


def test_page_links_are_safe_and_resolvable() -> None:
    _, parser = parse_page()
    assert 'https://github.com/joehomeskillet/Dishboard' in parser.references
    assert 'https://dishboard.joelduss.xyz/' in parser.references

    for reference in parser.references:
        parsed = urlsplit(reference)
        if parsed.scheme:
            assert parsed.scheme == 'https', reference
            continue
        if reference.startswith('#'):
            assert reference[1:] in parser.ids, reference
            continue
        relative_path = parsed.path or 'index.html'
        target = (SITE / relative_path).resolve()
        assert target.is_relative_to(SITE.resolve()), reference
        assert target.is_file(), reference


def test_styles_are_local_tokenized_and_accessible() -> None:
    sources = [path.read_text(encoding='utf-8') for path in STYLES]
    source = '\n'.join(sources)
    assert ':root' in source
    assert ':focus-visible' in source
    assert '@media (prefers-reduced-motion: reduce)' in source
    assert '@media (max-width:' in source
    assert not re.search(r'#[0-9a-fA-F]{3,8}\b', source)
    assert '@import' not in source
    assert not re.search(r'url\(["\']?https?://', source, flags=re.IGNORECASE)
    assert all(len(stylesheet.splitlines()) < 400 for stylesheet in sources)


def test_semantic_color_tokens_meet_calculated_contrast_ratios() -> None:
    source = (SITE / 'foundation.css').read_text(encoding='utf-8')
    colors = {
        name: parse_oklch_token(source, name)
        for name in (
            'paper',
            'paper-warm',
            'patient-soft',
            'cafeteria-soft',
            'white',
            'focus',
            'patient-label',
            'cafeteria-label',
        )
    }

    for background in ('paper', 'paper-warm', 'patient-soft', 'cafeteria-soft', 'white'):
        assert contrast_ratio(colors['focus'], colors[background]) >= 3, background
    assert contrast_ratio(colors['patient-label'], colors['paper']) >= 4.5
    assert contrast_ratio(colors['cafeteria-label'], colors['paper']) >= 4.5

    assert 'var(--color-focus)' in css_block(source, 'a:focus-visible')
    assert 'var(--color-patient-label)' in css_block(source, '.eyebrow')
    responsive = (SITE / 'responsive.css').read_text(encoding='utf-8')
    assert 'var(--color-cafeteria-label)' in css_block(
        responsive,
        '.closing-section .eyebrow',
    )


def test_mobile_menu_profiles_stack_without_overlap() -> None:
    source = (SITE / 'responsive.css').read_text(encoding='utf-8')
    mobile = source[
        source.index('@media (max-width: 44rem)'):
        source.index('@media (prefers-reduced-motion: reduce)')
    ]
    board = css_block(mobile, '.menu-board')
    sheet = css_block(mobile, '.menu-sheet')

    assert 'display: grid;' in board
    assert 'min-height: auto;' in board
    assert 'position: static;' in sheet
    assert 'width: 100%;' in sheet
    assert 'transform: none;' in sheet


def test_pages_workflow_is_least_privilege_and_deploys_only_site() -> None:
    source = WORKFLOW.read_text(encoding='utf-8')
    assert re.search(r'^on:\n\s{2}push:\n\s{4}branches:\n\s{6}- main$', source, re.MULTILINE)
    assert re.search(r'^\s{2}workflow_dispatch:\s*$', source, re.MULTILINE)
    assert 'pull_request:' not in source
    assert re.search(
        r'^permissions:\n\s{2}contents: read\n\s{2}pages: write\n\s{2}id-token: write$',
        source,
        re.MULTILINE,
    )
    assert 'group: pages' in source
    assert 'cancel-in-progress: false' in source
    assert 'actions/checkout@v4' in source
    assert 'actions/configure-pages@v5' in source
    assert 'actions/upload-pages-artifact@v3' in source
    assert 'actions/deploy-pages@v5' in source
    assert re.search(r'^\s{10}path: site$', source, re.MULTILINE)
    assert 'secrets.' not in source
