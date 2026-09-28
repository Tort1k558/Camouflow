"""Phase 0 spike: verify the AI-agent DOM snapshot on real engines.

Run: python verify_ai_agent.py [engine]   (engine: camoufox | cloakbrowser, default camoufox)

Checks (no network, no LLM):
  1. dom.js evaluates on the engine and returns a snapshot
  2. interactive elements are captured with unique selectors
  3. hidden elements are skipped, values are never leaked
  4. every CSS selector resolves to exactly one element in the page
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

TEMP_DATA = tempfile.mkdtemp(prefix="camouflow-ai-spike-")
os.environ["CAMOUFLOW_DATA_DIR"] = TEMP_DATA

DOM_JS = (Path(__file__).resolve().parent / "app" / "services" / "ai_agent" / "dom.js").read_text(encoding="utf-8")

TEST_PAGE = """<!doctype html>
<html><head><title>Spike Page</title></head><body>
<h1>CamouFlow AI spike</h1>
<a href="/docs" id="docs-link">Documentation</a>
<button id="login">Log in</button>
<button>Only One</button>
<button>Only One</button>
<button>Only One</button>
<form>
  <label for="search">Search query</label>
  <input id="search" name="q" type="text" placeholder="Type here..." value="SECRET-VALUE">
  <label for="pass">Password</label>
  <input id="pass" name="password" type="password" value="hunter2">
  <label for="country">Country</label>
  <select id="country" name="country">
    <option value="de">Germany</option>
    <option value="jp" selected>Japan</option>
    <option value="us">United States</option>
  </select>
  <label for="agree">Agree</label>
  <input id="agree" name="agree" type="checkbox" checked>
  <input id="robot" name="robot" type="radio" value="yes">
</form>
<div role="button" data-testid="custom-action">Custom action</div>
<details><summary>Do I need a server?</summary>Not for local work.</details>
<details><summary><span class="faq-number">03</span>Server required?<span class="faq-plus">+</span></summary>No.</details>
<button style="display:none">Hidden</button>
<button style="visibility:hidden">Invisible</button>
<div><div><div><button>Nested deep button</button></div></div></div>
</body></html>
"""


async def run(engine: str) -> int:
    from app.core.browser_interface import BrowserInterface

    page_file = Path(TEMP_DATA) / "spike.html"
    page_file.write_text(TEST_PAGE, encoding="utf-8")

    interface = BrowserInterface(
        "ai-spike",
        browser_engine=engine,
        browser_settings={"headless": True},
    )
    failures = []

    def check(name, condition, detail=""):
        status = "PASS" if condition else "FAIL"
        print(f"  [{status}] {name}" + (f" — {detail}" if detail and not condition else ""))
        if not condition:
            failures.append(name)

    try:
        await interface.start()
        page = interface.page
        await page.goto(page_file.as_uri())
        snapshot = await page.evaluate(DOM_JS)

        print(f"engine={engine} url={snapshot['url']}")
        print(f"title={snapshot['title']!r} elements={len(snapshot['elements'])}")
        for element in snapshot["elements"]:
            print(f"    {element['index']:>3} {element['tag']:<10} sel={element['selector']}" + (f" text={element.get('text')!r}" if element.get("text") else ""))

        elements = snapshot["elements"]
        by_selector = {e["selector"]: e for e in elements}
        check("snapshot has url/title", snapshot["url"].startswith("file://") and snapshot["title"] == "Spike Page")
        check("captured >= 12 elements", len(elements) >= 12, f"got {len(elements)}")
        check("id selector used", 'button[id="login"]' in by_selector)
        check("unique text selector", 'button:text-is("Nested deep button")' in by_selector, str(list(by_selector)[:5]))
        check("structural fallback for duplicates", sum(1 for s in by_selector if ":nth-of-type(" in s) >= 2)
        check("select options listed", any(e.get("options") == ["de", "jp", "us"] for e in elements))
        check("checkbox state", any(e.get("checked") is True for e in elements))
        check("password field masked", any(e.get("type") == "password" and "value" not in e for e in elements))
        check("no element values leaked", all("value" not in e for e in elements))
        check("hidden elements skipped", all("Hidden" not in e.get("text", "") and "Invisible" not in e.get("text", "") for e in elements))
        check("role button with testid", 'div[data-testid="custom-action"]' in by_selector)
        check("summary gets text-is selector", 'summary:text-is("Do I need a server?")' in by_selector)
        check("span-mixed summary falls back to structural", any(":nth-of-type(" in e["selector"] and e["tag"] == "summary" for e in elements))
        check("deep nested button captured", any(e.get("text") == "Nested deep button" for e in elements))

        # Every plain-CSS selector must resolve to exactly one node (text-is is a playwright pseudo, checked separately).
        resolve_js = """(selectors) => selectors.map(sel => {
            if (sel.includes(':text-is(')) return 'pw';
            try { return document.querySelectorAll(sel).length; } catch (_) { return 'invalid'; }
        })"""
        css_selectors = [e["selector"] for e in elements if ":text-is(" not in e["selector"]]
        counts = await page.evaluate(resolve_js, css_selectors)
        bad = [(sel, cnt) for sel, cnt in zip(css_selectors, counts) if cnt != 1]
        check("every CSS selector resolves to exactly 1 element", not bad, str(bad[:4]))

        pw_selectors = [e["selector"] for e in elements if ":text-is(" in e["selector"]]
        for sel in pw_selectors:
            locator = page.locator(sel)
            count = await locator.count()
            check(f"playwright selector resolves to 1: {sel[:50]}", count == 1, f"count={count}")
    finally:
        await interface.close(force=True)

    print(f"\n{'ALL PASS' if not failures else 'FAILURES: ' + ', '.join(failures)} ({engine})")
    return 0 if not failures else 1


if __name__ == "__main__":
    engine = sys.argv[1] if len(sys.argv) > 1 else "camoufox"
    rc = asyncio.run(run(engine))
    if rc == 0 and len(sys.argv) > 1:
        sys.exit(rc)
    sys.exit(rc)
