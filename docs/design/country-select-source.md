# Shared country selection

`admin/_country_select.html` exports
`country_select(name, value, id, required=False, error=None)`.
Callers supply a visible label associated with `id`; repeated rows require unique IDs.
The macro renders a native Tabler `select.form-select`, preserving ISO values and field names.
Blank is `Nicht erfasst`. Unknown saved codes remain selected as `Gespeicherter Wert: …`;
they are not silently normalised or deleted. Existing server validation remains authoritative.
Optional errors add `is-invalid`, `aria-invalid` and an escaped message at `<id>-error`.

## Source and reproduction

Generated on 2026-09-05 from the installed Debian `iso-codes` package **4.20.1-1**,
upstream **4.20.1**: https://salsa.debian.org/iso-codes-team/iso-codes.
This is the iso-codes distribution of ISO 3166-1 data, not a new runtime dependency.

| Input | SHA256 |
|---|---|
| `/usr/share/iso-codes/json/iso_3166-1.json` | `f01b812b57fba9f31ff621bf33e7c7570a01964dbeb5be2167e94decf538c89f` |
| `/usr/share/locale/de/LC_MESSAGES/iso_3166-1.mo` | `eb58cdf4cab2459f90434b2d6f8e293a7f7116f767cb5dcfd15064b055179f1b` |

The German catalogue records `PO-Revision-Date: 2023-02-24 21:01+0000`, language `de`.
Extraction uses Python stdlib `json` and `gettext.GNUTranslations`: for each of the249
`3166-1` entries, use `alpha_2` and translate `common_name` when present, otherwise `name`.
Sort by `unicodedata.normalize('NFKD', translated_name).casefold()` and emit the literal
ordered mapping in the macro. The generated mapping and render tests are versioned;
the running application needs neither iso-codes, gettext files nor network access.

The derived country/name mapping is LGPL-2.1-or-later, matching iso-codes.
Preserved copyright notice: [iso-codes-copyright.txt](../licenses/iso-codes-copyright.txt).
License text: [iso-codes-LGPL-2.1.txt](../licenses/iso-codes-LGPL-2.1.txt).
Attribution: Alastair McKinstry (2001–2008), Christian Perrier (2004–2016),
Dr. Tobias Quathamer (2005–2026); translation attribution is retained in the source catalogue.
Modification: materialised the code/name mapping as a standalone Jinja select macro.
