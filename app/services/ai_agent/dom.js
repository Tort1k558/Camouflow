/* CamouFlow AI agent DOM snapshot.
 *
 * Evaluated on the active page via playwright `page.evaluate`. Returns a compact,
 * indexed list of visible interactive elements with unique selectors, so an LLM
 * can pick `index` and the host can translate that into a durable CSS selector.
 *
 * Uses only standard DOM APIs (works on both Camoufox/Firefox and
 * CloakBrowser/Chromium). Never sends input values, cookies or attributes that
 * look like secrets; password fields are marked but their content is ignored.
 *
 * uniqueSelector() is intentionally kept in sync with the algorithm in
 * app/services/scenario_recorder.py (RECORDER_SCRIPT) so recorded and
 * AI-generated steps produce the same selectors.
 */
(() => {
    const MAX_ELEMENTS = 250;
    const clip = (value, limit) => String(value == null ? "" : value).replace(/\s+/g, " ").trim().slice(0, limit);

    const uniqueSelector = (el) => {
        for (const attr of ["data-testid", "id", "name", "aria-label", "placeholder", "title"]) {
            const value = el.getAttribute(attr);
            if (!value || value.includes("{{")) continue;
            const candidate = el.tagName.toLowerCase() + "[" + attr + "=" + JSON.stringify(value) + "]";
            try {
                if (document.querySelectorAll(candidate).length === 1) return candidate;
            } catch (_) { /* invalid selector value */ }
        }
        if (el.matches("button,a,summary,[role=\"button\"],[role=\"link\"]") && el.children.length === 0) {
            /* Text selectors only for pure-text elements: mixed inline spans
             * (badges, icons) produce whitespace-unstable text between the
             * pre- and post-hydration DOM, which breaks exact replay matching. */
            const text = clip(el.textContent, 100);
            const tag = el.tagName.toLowerCase();
            if (text && !text.includes("{{") &&
                [...document.querySelectorAll(tag)].filter((item) => clip(item.textContent, 100) === text).length === 1) {
                return tag + ":text-is(" + JSON.stringify(text) + ")";
            }
        }
        return "";
    };

    /* Structural fallback: unique among siblings via nth-of-type. */
    const cssPath = (el) => {
        const parts = [];
        let node = el;
        while (node && node.nodeType === 1 && parts.length < 64) {
            let part = node.tagName.toLowerCase();
            const parent = node.parentElement;
            if (parent) {
                const sameTag = [...parent.children].filter((child) => child.tagName === node.tagName);
                if (sameTag.length > 1) part += ":nth-of-type(" + (sameTag.indexOf(node) + 1) + ")";
            }
            parts.unshift(part);
            node = parent;
        }
        return parts.join(" > ");
    };

    const INTERACTIVE = [
        "a[href]", "button", "input", "textarea", "select", "summary",
        "[role=\"button\"]", "[role=\"link\"]", "[role=\"tab\"]", "[role=\"menuitem\"]",
        "[role=\"option\"]", "[role=\"checkbox\"]", "[contenteditable]",
        "table", "h1", "h2", "h3", "p", "[data-testid]",
    ].join(",");

    const elements = [];
    for (const el of document.querySelectorAll(INTERACTIVE)) {
        if (elements.length >= MAX_ELEMENTS) break;
        if (el.tagName === "INPUT" && el.type === "hidden") continue;
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        if (rect.width < 2 || rect.height < 2 || style.display === "none" || style.visibility === "hidden" ||
            rect.bottom < 0 || rect.top > window.innerHeight || rect.right < 0 || rect.left > window.innerWidth) continue;

        if (el.closest("textarea,[contenteditable]") && !el.matches("textarea,[contenteditable]")) continue;
        const stable = uniqueSelector(el);
        const item = {
            index: elements.length,
            tag: el.tagName.toLowerCase(),
            selector: stable || cssPath(el),
            stable_selector: Boolean(stable),
        };
        const role = el.getAttribute("role");
        if (role) item.role = clip(role, 40);
        if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") item.type = clip(el.type || "text", 20);
        if (el.isContentEditable) item.editable = true;

        /* Context text: never element values, only labels/aria/text content. */
        const editable = el.matches("input,textarea,[contenteditable]");
        const safe = el.cloneNode(true);
        safe.querySelectorAll("input,textarea,[contenteditable],script,style").forEach(node => node.remove());
        let text = clip(el.getAttribute("aria-label") || (editable ? "" : safe.textContent), 80);
        if (!text && el.labels && el.labels.length) text = clip(el.labels[0].textContent, 60);
        if (!text) text = clip(el.getAttribute("placeholder"), 60);
        if (text) item.text = text;

        if (el.tagName === "A" && el.hasAttribute("href")) item.href = clip(el.getAttribute("href"), 120);
        if (el.disabled) item.disabled = true;
        if (el.tagName === "INPUT" && (el.type === "checkbox" || el.type === "radio")) item.checked = Boolean(el.checked);
        if (el.tagName === "SELECT") {
            const options = [...el.options].map((option) => clip(option.value || option.textContent, 40)).filter(Boolean).slice(0, 15);
            item.options = options;
        }
        elements.push(item);
    }

    /* Read visible text without values or editable document contents. */
    const pieces = [];
    if (document.body) {
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        let node;
        while ((node = walker.nextNode()) && pieces.join(" ").length < 12000) {
            const parent = node.parentElement;
            if (!parent || parent.closest('input,textarea,[contenteditable],script,style,noscript')) continue;
            const style = getComputedStyle(parent);
            if (style.display === "none" || style.visibility === "hidden") continue;
            const range = document.createRange();
            range.selectNodeContents(node);
            const rect = range.getBoundingClientRect();
            if (rect.width < 1 || rect.height < 1 || rect.bottom < 0 || rect.top > innerHeight) continue;
            const part = clip(node.textContent, 2000);
            if (part) pieces.push(part);
        }
    }
    const text = pieces.join(" ").slice(0, 12000);

    return {
        url: location.href,
        title: clip(document.title, 120),
        text,
        viewport: { width: window.innerWidth, height: window.innerHeight },
        scroll: { y: window.scrollY, page_height: document.documentElement.scrollHeight },
        elements,
    };
})()
