#!/usr/bin/env python3
"""Browser regression for deferred family feedback in List and Map.

Optional Playwright check against an existing built site, with parts requests held
and failed deterministically. No public network or startup prefetch is needed.
Run: python3 scripts/tests/test_universe_status.py [--site-root site/_build] [--shots DIR]
"""
from __future__ import annotations

import argparse
import functools
import http.server
from pathlib import Path
import threading


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[2]
    parser.add_argument('--site-root', type=Path, default=root / 'site' / '_build')
    parser.add_argument('--shots', type=Path)
    args = parser.parse_args()
    if not (args.site_root / 'index.html').is_file():
        parser.error('Build the site and universe before running this browser check.')
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        parser.error('This optional browser check requires Playwright and Chromium or Chrome.')
    if args.shots:
        args.shots.mkdir(parents=True, exist_ok=True)

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_args):
            pass

    server = http.server.ThreadingHTTPServer(
        ('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(args.site_root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(channel='chrome')
            except Exception:
                browser = playwright.chromium.launch()
            try:
                # The relocated status must follow the site's .js convention:
                # without scripts, the native family list is the complete UI.
                context = browser.new_context(viewport={'width': 390, 'height': 664}, java_script_enabled=False)
                try:
                    page = context.new_page()
                    page.goto(f'http://127.0.0.1:{server.server_port}/', wait_until='load')
                    assert page.locator('html.js').count() == 0
                    assert not page.locator('[data-u-status]').is_visible(), 'no permanent loading overlay without JavaScript'
                    assert not page.locator('[data-u-stage]').is_visible()
                    families = page.locator('.u-index__fams a')
                    assert families.count() > 0, 'the native family list remains available'
                    families.first.scroll_into_view_if_needed()
                    assert families.first.is_visible()
                    if args.shots:
                        page.screenshot(path=str(args.shots / 'status-nojs-390.png'))
                    target = families.first.get_attribute('href')
                    families.first.click()
                    assert page.url.endswith('/' + target), 'native family links still navigate without scripts'
                    print('PASS 390px no JavaScript: loading status hidden; native family link opens', flush=True)
                finally:
                    context.close()
                for width, height, scheme in [(390, 664, 'light'), (390, 664, 'dark'), (1440, 790, 'light')]:
                    context = browser.new_context(viewport={'width': width, 'height': height}, color_scheme=scheme)
                    try:
                        page = context.new_page()
                        errors, pending = [], []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.route('**/data/universe-parts.json*', lambda route: pending.append(route))
                        page.goto(f'http://127.0.0.1:{server.server_port}/', wait_until='load')
                        page.wait_for_function('window.__universe')
                        assert not pending, 'initial List or Map must not prefetch family parts'
                        status = page.locator('[data-u-status]')
                        assert status.count() == 1 and status.get_attribute('role') == 'status'
                        assert status.locator('xpath=ancestor::*[@data-u-stage]').count() == 0
                        page.locator('[data-u-view] [data-go^="d:"]').first.click()
                        family = page.locator('[data-u-view] a.u-entry[data-go^="f:"]').first
                        family.wait_for(state='visible')
                        key, href = family.get_attribute('data-go'), family.get_attribute('href')
                        assert href and href.startswith('families/'), 'a family in the list is a link to its page'
                        # Choosing a family on the map (the test's explicit selection) waits for
                        # the parts, reports a failure, retries on the next explicit selection
                        # and then settles the selection.
                        page.evaluate('k => window.__universe.select(k)', key)
                        status = page.locator('[data-u-status]')
                        status.wait_for(state='visible')
                        assert status.inner_text() == 'Opening the family…'
                        if width < 900:
                            assert not page.locator('[data-u-stage]').is_visible(), 'the regression starts with a hidden map'
                            box = status.bounding_box()
                            assert box and box['y'] >= 0 and box['y'] + box['height'] <= height
                        if args.shots:
                            page.screenshot(path=str(args.shots / f'status-loading-{width}-{scheme}.png'))
                        assert len(pending) == 1, 'selection starts exactly one parts request'
                        pending.pop().fulfill(status=503, content_type='application/json', body='{}')
                        page.wait_for_function("document.querySelector('[data-u-status]').textContent.includes('could not load')")
                        assert status.is_visible(), 'failed selection stays visible'
                        if args.shots:
                            page.screenshot(path=str(args.shots / f'status-failed-{width}-{scheme}.png'))
                        page.evaluate('k => window.__universe.select(k)', key)
                        page.wait_for_function("document.querySelector('[data-u-status]').textContent === 'Opening the family…'")
                        assert status.is_visible(), 'explicit retry replaces failure with visible loading'
                        assert len(pending) == 1, 'explicit retry starts one replacement request'
                        if width < 900:
                            page.locator('[data-u-show="map"]').click()
                            assert status.is_visible(), 'the same status survives a switch to Map'
                        pending.pop().continue_()
                        page.wait_for_function('key => window.__universe.state().sel === key', arg=key)
                        status.wait_for(state='hidden')
                        assert not errors, errors
                        print(f'PASS {width}px {scheme}: family links, loading, failure, retry and successful clear', flush=True)
                    finally:
                        context.close()
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
