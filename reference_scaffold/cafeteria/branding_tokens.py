"""Validated semantic brand values enter CSS only through this token accessor."""
from __future__ import annotations

from .branding_config import BrandConfig, FONTS, contrast, default_config, validate_config


def _blend(color: str, target: int, amount: float) -> str:
    channels = [round(int(color[index:index + 2], 16) * (1 - amount) + target * amount) for index in (1, 3, 5)]
    return '#' + ''.join(f'{value:02x}' for value in channels)


def brand_tokens(config: BrandConfig) -> dict[str, str]:
    values = validate_config(config)
    defaults = default_config()
    tokens = {
        '--sh-font': f'"{FONTS[values["font_body"]]}", sans-serif',
        '--sh-font-display': f'"{FONTS[values["font_heading"]]}", sans-serif',
    }
    primary = values['primary']
    if primary != defaults['primary']:
        tokens.update({'--sh-primary': primary, '--sh-magenta': primary,
                       '--sh-primary-2': _blend(primary, 0, .12),
                       '--sh-primary-3': _blend(primary, 0, .24),
                       '--sh-primary-4': _blend(primary, 255, .8),
                       '--sh-primary-5': _blend(primary, 255, .92),
                       '--sh-magenta-soft': _blend(primary, 255, .92),
                       '--sh-primary-glow': _blend(primary, 255, .75)})
    accent = values['accent']
    if accent != defaults['accent']:
        tokens['--sh-secondary'] = accent
        for shade, factor in ((950, -.6), (900, -.45), (800, -.25), (700, 0), (600, .1),
                              (500, .2), (400, .4), (300, .6), (200, .8), (100, .9), ('050', .96)):
            tokens[f'--sh-teal-{shade}'] = _blend(accent, 0 if factor < 0 else 255, abs(factor))
        tokens.update({'--sh-signage-start': _blend(accent, 0, .6),
                       '--sh-signage-middle': _blend(accent, 0, .45),
                       '--sh-signage-end': _blend(accent, 0, .25)})
    if values['surface'] != defaults['surface']:
        for key in ('--sh-canvas', '--sh-canvas-strong', '--sh-panel', '--sh-panel-soft'):
            tokens[key] = values['surface']
    if values['text'] != defaults['text']:
        tokens.update({'--sh-ink': values['text'], '--sh-ink-muted': values['text']})
    changed_palette = any(dict(values)[key] != dict(defaults)[key] for key in ('primary', 'accent', 'surface', 'text'))
    if changed_palette:
        green = '#3e6b44'
        candidates = (_blend(green, target, step / 10) for step in range(11) for target in (0, 255))
        green = next(color for color in candidates if contrast(color, values['surface']) >= 4.5)
        tokens.update({
            '--brand-on-primary': values['surface'], '--brand-sidebar': _blend(accent, 0, .85),
            '--brand-meal-bg': primary,
            '--sh-primary-glow': 'rgb(' + ' '.join(str(int(primary[index:index + 2], 16)) for index in (1, 3, 5)) + ' / .12)',
            '--sh-green': green, '--sh-green-soft': values['surface'],
            '--sh-ink': values['text'], '--sh-ink-muted': values['text'], '--sh-neutral-2': values['text'],
            '--sh-canvas': values['surface'], '--sh-canvas-strong': values['surface'],
            '--sh-panel': values['surface'], '--sh-panel-soft': values['surface'],
            '--sh-primary': primary, '--sh-primary-2': primary, '--sh-primary-3': primary,
            '--sh-magenta': primary, '--sh-magenta-soft': values['surface'],
            '--sh-secondary': accent, '--sh-teal-950': accent, '--sh-teal-900': accent,
            '--sh-teal-800': accent, '--sh-teal-700': accent,
            '--sh-teal-100': values['surface'], '--sh-teal-050': values['surface'],
            '--sh-white-098': values['surface'], '--sh-white-0985': values['surface'],
            '--sh-signage-start': _blend(accent, 0, .85),
            '--sh-signage-middle': _blend(accent, 0, .8), '--sh-signage-end': _blend(accent, 0, .75),
        })
    return tokens


def branding_css(config: BrandConfig, static_prefix: str) -> str:
    declarations = ';'.join(f'{key}:{value}' for key, value in brand_tokens(config).items())
    fonts = ''.join(
        '@font-face{font-family:"Carlito";font-style:normal;font-weight:' + weight +
        ';font-display:swap;src:url("' + static_prefix + '/fonts/weekly-print-carlito' + suffix + '.woff") format("woff")}'
        for weight, suffix in (('400', ''), ('700', '-bold'))
    )
    return fonts + ':root{' + declarations + '}' + (
        '.brand-logo{object-fit:contain;max-width:100%}'
        '.dishboard-admin h1,.dishboard-admin h2,.dishboard-admin h3,'
        '.public-page h1,.public-page h2,.public-page h3{font-family:var(--sh-font-display)}'
        '.dishboard-admin,.public-page,.signage-body{--tblr-primary-fg:var(--brand-on-primary,var(--sh-white));'
        '--tblr-heading-color:var(--sh-ink);--tblr-bg-forms:var(--sh-panel);--tblr-body-bg:var(--sh-canvas);'
        '--tblr-bg-surface:var(--sh-panel);--tblr-bg-surface-secondary:var(--sh-panel-soft);'
        '--tblr-bg-surface-tertiary:var(--sh-panel-soft)}'
        '.dishboard-admin .admin-sidebar{--tblr-navbar-bg:var(--brand-sidebar,var(--sh-teal-950))}'
        '.bg-primary.text-white,.btn-primary{color:var(--brand-on-primary,var(--sh-white))!important}'
        '.list-group-item.active{background:var(--sh-primary);color:var(--brand-on-primary,var(--sh-white))}'
        '.list-group-item.active .badge{color:inherit}'
        '.dishboard-admin .nav-tabs .nav-link{color:var(--sh-primary)}'
        '.dishboard-admin .form-control::file-selector-button{color:var(--sh-ink);background:var(--sh-panel-soft)}'
    )
