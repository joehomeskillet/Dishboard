#!/usr/bin/env python3
"""Render the supplied static HTML design references, never the live application.

Optional reproduction tool: needs Playwright and a compatible local Chromium.
Do not add these tools to the production Flask application's dependencies.
This utility performs no login, no network request and no save/publish operation.
"""
from __future__ import annotations
import argparse
import base64
import json
import shutil
from pathlib import Path


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paket',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--chromium',type=str,default=None,help='Optional existing Chromium/Chrome executable')
    args=parser.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit('Optional renderer requires Playwright. The PNG files work without it.') from exc
    root=args.paket.resolve()
    dest=root/'soll'; dest.mkdir(parents=True,exist_ok=True)
    executable=args.chromium or shutil.which('chromium') or shutil.which('google-chrome')
    pages=['R1-menues','R2-wochenverwaltung','R3-baustein-bearbeiten','R4-druckvorlagen','E1-wochenplan','E2-menueeditor']
    jobs=[(p,p,1600,1100,1.5) for p in pages]
    jobs += [('R1-menues','R1-menues-mobil',390,844,2),('E1-wochenplan','E1-wochenplan-mobil',390,844,2)]
    results=[]
    with sync_playwright() as pw:
        kwargs={'headless':True}
        if executable: kwargs['executable_path']=executable
        browser=pw.chromium.launch(**kwargs)
        for source,name,width,height,dpr in jobs:
            html=root/'vorlagen'/f'{source}.html'
            if not html.is_file(): raise FileNotFoundError(html)
            context=browser.new_context(viewport={'width':width,'height':height},device_scale_factor=dpr,locale='de-CH',reduced_motion='reduce')
            page=context.new_page()
            requests=[]
            def deny_external(route):
                if route.request.url.startswith(('http:','https:')):
                    requests.append(route.request.url)
                    route.abort()
                else:
                    route.continue_()
            page.route('**/*',deny_external)
            # Inline the supplied local resources; no web server or file URL is needed.
            content=html.read_text(encoding='utf-8')
            css=(root/'vorlagen/assets/design.css').read_text(encoding='utf-8')
            logo=base64.b64encode((root/'vorlagen/assets/suedhang-logo-ausschnitt.png').read_bytes()).decode('ascii')
            content=content.replace('<link rel="stylesheet" href="assets/design.css">', '<style>'+css+'</style>')
            content=content.replace('src="assets/suedhang-logo-ausschnitt.png"','src="data:image/png;base64,'+logo+'"')
            page.set_content(content,wait_until='load')
            page.evaluate('document.fonts.ready')
            metrics=page.evaluate('''() => ({
                innerWidth:window.innerWidth,
                scrollWidth:document.documentElement.scrollWidth,
                scrollHeight:document.documentElement.scrollHeight,
                visiblePrimary:[...document.querySelectorAll('.btn.primary')].map(e=>({text:e.innerText,top:e.getBoundingClientRect().top,bottom:e.getBoundingClientRect().bottom})),
                navCount:document.querySelectorAll('.sidebar .nav-item').length,
                externalImages:[...document.images].filter(i=>!i.complete||i.naturalWidth===0).map(i=>i.src)
            })''')
            if metrics['scrollWidth'] > width:
                raise RuntimeError(f'Horizontal overflow for {name}: {metrics}')
            if metrics['externalImages']:
                raise RuntimeError(f'Broken image for {name}: {metrics}')
            outfile=dest/f'{name}.png'
            page.screenshot(path=str(outfile),full_page=True,animations='disabled')
            results.append({'id':name,'source':str(html.relative_to(root)), 'output':str(outfile.relative_to(root)), 'kind':'Browsergerendertes, isoliertes HTML-Mockup; keine Live-Anwendung','viewport_css':{'width':width,'height':height},'device_scale_factor':dpr,'browser_zoom':'100 %','full_page':True,'metrics':metrics,'blocked_network_requests':requests})
            print(name,json.dumps(metrics,ensure_ascii=False))
            context.close()
        browser.close()
    (root/'grundlagen/RENDER_METADATEN.json').write_text(json.dumps({'scope':'Static reference HTML only; no application or workflow tests','renders':results},ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
    main()
