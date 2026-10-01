"""Server-render legacy filter-slot chips without changing the owning GET form."""
from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit, urlunsplit

from markupsafe import Markup


@dataclass
class _Control:
    name: str
    kind: str
    identifier: str = ''
    values: list[str] = field(default_factory=list)
    reset: list[str] = field(default_factory=list)
    label: str = ''
    active: bool = False


class _Fields(HTMLParser):
    """Read trusted rendered fields, never interpret markup as executable code."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.controls: list[_Control] = []
        self.labels: dict[str, str] = {}
        self.label_for: str | None = None
        self.label_text: list[str] | None = None
        self.wrapped: list[_Control] = []
        self.select: _Control | None = None
        self.options: list[tuple[dict[str, str | None], list[str]]] = []
        self.option: tuple[dict[str, str | None], list[str]] | None = None
        self.multiple = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        name = attributes.get('name')
        if tag == 'label':
            self.label_for, self.label_text, self.wrapped = attributes.get('for'), [], []
        if tag in {'input', 'select'} and name and 'disabled' not in attributes:
            kind = (attributes.get('type') or 'text') if tag == 'input' else 'select'
            if kind in {'submit', 'button', 'reset', 'image', 'file'}:
                return
            control = _Control(name, kind, attributes.get('id') or '')
            self.controls.append(control)
            if self.label_text is not None:
                self.wrapped.append(control)
            if tag == 'select':
                self.select, self.options = control, []
                self.multiple = 'multiple' in attributes
            else:
                checked = kind not in {'checkbox', 'radio'} or 'checked' in attributes
                value = attributes.get('value', 'on' if kind in {'checkbox', 'radio'} else '') or ''
                control.values = [value] if checked else []
                control.reset = [] if kind in {'checkbox', 'radio'} else ['']
                control.active = kind != 'hidden' and checked and bool(value.strip())
        if tag == 'option' and self.select is not None:
            self.option = (attributes, [])
            self.options.append(self.option)

    def handle_data(self, data: str) -> None:
        if self.label_text is not None:
            self.label_text.append(data)
        if self.option is not None:
            self.option[1].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == 'label' and self.label_text is not None:
            label = ' '.join(''.join(self.label_text).split())
            if self.label_for:
                self.labels[self.label_for] = label
            for control in self.wrapped:
                control.label = label
            self.label_text = None
        if tag == 'option':
            self.option = None
        if tag == 'select' and self.select is not None:
            selected = [i for i, (attrs, _) in enumerate(self.options) if 'selected' in attrs]
            selected = selected if self.multiple else selected[-1:] or ([0] if self.options else [])
            for i, (attrs, text) in enumerate(self.options):
                label = ' '.join(''.join(text).split())
                value = attrs.get('value', label) or ''
                if i == 0 and not self.multiple and 'disabled' not in attrs:
                    self.select.reset = [value]
                if i in selected and 'disabled' not in attrs:
                    self.select.values.append(value)
                    if self.multiple or i > 0:
                        self.select.active = True
                        self.select.label += (', ' if self.select.label else '') + label
            self.select, self.option = None, None


def filter_chips(action: str, search_name: str, search_value: str | None,
                 profile: object, filters: object, more_filters: object) -> list[dict[str, str]]:
    """Mirror existing slot selection semantics; reset one field, retain others.

    Only Markup slots are HTML in Jinja. Plain strings remain escaped text and
    cannot create fields or active chips. Explicit active_filters bypass this.
    """
    parser = _Fields()
    if isinstance(profile, Markup):
        parser.feed(str(profile))
    first_filter = len(parser.controls)
    for slot in (filters, more_filters):
        if isinstance(slot, Markup):
            parser.feed(str(slot))
    parser.close()
    target = urlsplit(str(action))
    chips = []
    for control in parser.controls[first_filter:]:
        if not control.active:
            continue
        label = (control.label or parser.labels.get(control.identifier, control.name)
                 if control.kind in {'checkbox', 'radio', 'select'} else ', '.join(control.values))
        pairs = [(search_name, search_value or '')]
        for other in parser.controls:
            pairs.extend((other.name, value) for value in (other.reset if other is control else other.values))
        href = urlunsplit((target.scheme, target.netloc, target.path, urlencode(pairs), target.fragment))
        chips.append({'label': label, 'href': href})
    return chips
