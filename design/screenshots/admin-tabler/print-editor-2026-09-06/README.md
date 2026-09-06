# First functional print-template editor

Real Flask factory over HTTP, production CSP, isolated PostgreSQL `test-ps5` pool,
Google Chrome 152.0.7977.82 (`/opt/google/chrome/chrome`, native PDF viewer enabled).
These are local test fixtures, not production acceptance screenshots.

Both families were exercised at 390, 820 and 1440 pixels. `print-editor-preview-*`
shows a saved Fira Sans / Südhang Magenta draft with the real PDF; `print-editor-pdf-*`
is the corresponding native iframe capture after nonblank document paint.
`print-editor-second-session-no-js.png` shows the second browser completing an
explicit reload after HTTP 409, saving and activating without JavaScript.

The browser gate covers save, preview, activate, duplicate and restore, keyboard
focus, 48-pixel controls, 16-pixel form text, no outer horizontal overflow and no
CSP/console errors. The existing logo also serves as the editor page's favicon.
Unsupported native PDF viewers have an explicit PDF link outside the iframe.

## Verification

```text
103 passed in 81.99s (0:01:21)
GATE_EXIT=0 cwd=/nvmetank1/projects/menuplan/.claude/worktrees/print-editor-0906/reference_scaffold
All checks passed!
Success: no issues found in 5 source files
```

The combined gate contains the existing weekly PDF and print-route tests, new
PDF/property/store/route/browser tests and the existing output-hub tests.
Actual PostgreSQL runtime-role and concurrent initialization tests passed.
Preview and active download bytes match for the same saved week and configuration;
canonical PDF creation metadata avoids request-time differences. Real revision
timestamps remain in the separate template history.

Both PDFs retain a complete week and refuse overflow or unsupported glyphs.
Patients are A4 landscape, Monday to Sunday, and remain free of cost data;
Cafeteria is A4 portrait, Monday to Friday. Minimum printed text is 8.5 points.
Every offered property has a checked PDF consumer. Existing licensed Fira Sans
WOFF2 files were decompressed to TTF with provenance and glyph/metric checks;
no renderer dependency, SQL migration or arbitrary user resource path was added.

`design-validator` returned exit 0 but skipped both external analysis passes
(Gemini unavailable, no HTML semantic input). Its automatic GREEN is not counted
as a design review. Native screenshots were inspected manually. Root's independent
review, package gate, deployment and live proof remain separate.
