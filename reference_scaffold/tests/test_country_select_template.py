from html.parser import HTMLParser
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape


class SelectMarkup(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.select = {}
        self.options = []
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.tags.append((tag, attributes))
        if tag == 'select':
            self.select = attributes
        elif tag == 'option':
            self.options.append({'attributes': attributes, 'label': ''})

    def handle_data(self, data):
        if self.lasttag == 'option' and self.options:
            self.options[-1]['label'] += data.strip()


def render(value='', **kwargs):
    templates = Path(__file__).resolve().parents[1] / 'cafeteria' / 'templates'
    environment = Environment(loader=FileSystemLoader(templates), autoescape=select_autoescape())
    macro = environment.get_template('admin/_country_select.html').module.country_select
    return SelectMarkup(str(macro('origin_country_code', value, 'origin-country', **kwargs)))


def test_complete_country_list_has_german_names_and_unchanged_iso_values():
    markup = render('CH')
    countries = {row['attributes']['value']: row['label'] for row in markup.options[1:]}
    assert len(markup.options) == 250
    assert len(countries) == 249
    assert all(len(code) == 2 and code.isascii() and code.isupper() for code in countries)
    assert {code: countries[code] for code in ('CH', 'DE', 'AT', 'US', 'FR')} == {
        'CH': 'Schweiz', 'DE': 'Deutschland', 'AT': 'Österreich',
        'US': 'Vereinigte Staaten', 'FR': 'Frankreich',
    }
    assert {'AX', 'AQ', 'BQ', 'VA', 'ZW'} <= countries.keys()
    assert markup.select == {'class': 'form-select', 'name': 'origin_country_code', 'id': 'origin-country'}


@pytest.mark.parametrize('value', ('', None, 'CH', 'DE', 'ZZ', 'ch', '\"><script>invalid</script>'))
def test_saved_value_is_preserved_without_extra_selected_options(value):
    markup = render(value)
    selected = [row for row in markup.options if 'selected' in row['attributes']]
    assert len(selected) == 1
    assert selected[0]['attributes']['value'] == (value or '')
    if value in ('', None):
        assert selected[0]['label'] == 'Nicht erfasst'
    elif value not in ('CH', 'DE'):
        assert selected[0]['label'] == f'Gespeicherter Wert: {value}'
    assert not any(tag == 'script' for tag, _ in markup.tags)


def test_required_and_error_are_accessibly_linked_and_escaped():
    markup = render('ZZ', required=True, error='<script>Land prüfen</script>')
    assert 'required' in markup.select
    assert markup.select['aria-invalid'] == 'true'
    assert markup.select['aria-describedby'] == 'origin-country-error'
    assert 'is-invalid' in markup.select['class'].split()
    assert any(tag == 'div' and attrs.get('id') == 'origin-country-error' for tag, attrs in markup.tags)
    assert not any(tag == 'script' for tag, _ in markup.tags)
