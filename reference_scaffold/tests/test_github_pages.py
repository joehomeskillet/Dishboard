from __future__ import annotations

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
    assert 'cancel-in-progress: true' in source
    assert 'actions/checkout@v4' in source
    assert 'actions/configure-pages@v5' in source
    assert 'actions/upload-pages-artifact@v3' in source
    assert 'actions/deploy-pages@v4' in source
    assert re.search(r'^\s{10}path: site$', source, re.MULTILINE)
    assert 'secrets.' not in source
