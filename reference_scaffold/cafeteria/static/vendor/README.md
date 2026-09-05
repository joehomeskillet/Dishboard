# Vendored frontend assets (admin only)

Self-hosted, pinned, no CDN. Loaded only for `admin-body` views via `templates/base.html`.

## @tabler/core 1.5.0 (MIT)

- Source tarball: https://registry.npmjs.org/@tabler/core/-/core-1.5.0.tgz
- Tarball SHA256: 8bb0fa17e34f711628364456159e148bae3f7ec013d0eefd202740731121799e
- Vendored file: `tabler/tabler.min.css` = `package/dist/css/tabler.min.css`
- File SHA256: 4cdeade29286540dff94acfeb6ea9ea6a16bad4a64ff5604f659414b7c954cd5
- License text: `tabler/LICENSE` from https://raw.githubusercontent.com/tabler/tabler/refs/tags/@tabler/core@1.5.0/LICENSE (SHA256 4f88a82d13be3c5c63a12c5631eae914aa4381b6dc17641bf1ab85f3f8f6c8a5)
- Release notes: https://github.com/tabler/tabler/releases/tag/@tabler/core@1.5.0
- Docs: https://docs.tabler.io/ui/getting-started/installation
- Not vendored: `tabler.min.js` (no collapse/dropdown behaviour is used yet).

## @tabler/icons 3.46.0 (MIT)

- Source tarball: https://registry.npmjs.org/@tabler/icons/-/icons-3.46.0.tgz
- Tarball SHA256: 6d727ad0489854d2d7d07ba9baa6476af7ee415aaa2eba1adc0deab48556852b
- Vendored file: `tabler-icons/tabler-icons.svg`, a sprite built from the official
  `package/icons/outline/<name>.svg` files (symbol id `tabler-<name>`).
- Sprite SHA256: a9448ddd3ce423d890c93a4a8c944692c185d9ddba009d6d07eb056d608740e1
- License text: `tabler-icons/LICENSE` = `package/LICENSE` (SHA256 b740a1d46122672da62833e97f7e7c8a13fa85cbc7445b584b297cc00dde93db)
- Icons included: calendar-week, calendar-cog, calendar-plus, tools-kitchen-2, components, file-import, logout, search, x, plus, trash, arrow-left, check, eye, copy, device-floppy, alert-triangle, pencil, chevron-left, chevron-right, upload, archive, archive-off, file-check, info-circle, circle-check, refresh, clipboard-check

Both cached tarballs were verified against the SHA512 integrity values from the
official npm registry version endpoints before extraction. No package install.
To reproduce: download the pinned tarballs, verify registry integrity, extract
the CSS unchanged, and wrap the inner content of each listed outline SVG in a
`symbol` with its `tabler-<name>` id, viewBox `0 0 24 24`, fill `none`, stroke
`currentColor`, stroke-width `2`, round linecap and linejoin. Join these symbols
inside one SVG document without inline styles/scripts. Update file hashes after
any deliberate change. No framework JavaScript or runtime CDN is required.
