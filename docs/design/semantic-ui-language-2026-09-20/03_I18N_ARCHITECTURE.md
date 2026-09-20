# Multilingual Architecture

Recommended conceptual structure (adapt to existing project conventions):

```text
ui/
  semantics.py          # semantic registry
  macros.html           # Jinja UI macros
translations/
  de.json
  en.json
```

Registry record:
```text
key: action.save
ascii: [OK]
icon: device-floppy
label_key: action.save.label
tooltip_key: action.save.tooltip
aria_key: action.save.aria
icon_only_allowed: false
role: primary
```

Translations:
```json
{
  "action.save.label": "Speichern",
  "action.save.tooltip": "Änderungen speichern",
  "action.save.aria": "Änderungen speichern"
}
```

English:
```json
{
  "action.save.label": "Save",
  "action.save.tooltip": "Save changes",
  "action.save.aria": "Save changes"
}
```

Rules:
- semantic registry contains no translated visible text;
- translation files contain no icon decisions;
- business values and UI labels are separate;
- translation fallback must be observable/logged in development;
- missing translation must not silently become an empty control;
- pseudo-locale testing should lengthen labels and expose hard-coded widths.
