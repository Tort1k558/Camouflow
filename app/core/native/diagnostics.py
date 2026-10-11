"""Read actual Native browser values; never replace fingerprint APIs."""

from dataclasses import asdict

from .configuration import NativeConfiguration


OBSERVE = """async () => {
    const graphicsValues = () => {
        const result = {};
        for (const kind of ['webgl', 'webgl2']) {
            let context;
            try {
                if (typeof OffscreenCanvas === 'undefined') throw new Error('OffscreenCanvas unavailable');
                context = new OffscreenCanvas(16, 16).getContext(kind);
                if (!context) throw new Error('Native graphics context unavailable');
                const debug = context.getExtension('WEBGL_debug_renderer_info');
                result[kind] = {
                    available: true,
                    vendor: context.getParameter(context.VENDOR),
                    renderer: context.getParameter(context.RENDERER),
                    version: context.getParameter(context.VERSION),
                    shadingLanguage: context.getParameter(context.SHADING_LANGUAGE_VERSION),
                    unmaskedVendor: debug ? context.getParameter(debug.UNMASKED_VENDOR_WEBGL) : null,
                    unmaskedRenderer: debug ? context.getParameter(debug.UNMASKED_RENDERER_WEBGL) : null,
                    maxTextureSize: context.getParameter(context.MAX_TEXTURE_SIZE),
                    maxViewportDimensions: Array.from(context.getParameter(context.MAX_VIEWPORT_DIMS))
                };
            } catch (error) {
                result[kind] = {available: false, error: String(error.message)};
            } finally { context?.getExtension('WEBGL_lose_context')?.loseContext(); }
        }
        return result;
    };
    const navigatorValues = async () => {
        let userAgentHighEntropy = null;
        let userAgentDataError = '';
        if (navigator.userAgentData) {
            try {
                userAgentHighEntropy = await navigator.userAgentData.getHighEntropyValues([
                    'architecture', 'bitness', 'model', 'platformVersion',
                    'fullVersionList', 'wow64', 'formFactors'
                ]);
            } catch (error) { userAgentDataError = String(error.message); }
        }
        return {
            userAgent: navigator.userAgent, platform: navigator.platform,
            language: navigator.language, languages: [...navigator.languages],
            hardwareConcurrency: navigator.hardwareConcurrency,
            deviceMemory: navigator.deviceMemory ?? null,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            userAgentData: navigator.userAgentData?.toJSON() ?? null,
            userAgentHighEntropy, userAgentDataError
        };
    };
    const documentValues = {...await navigatorValues(),
        width: innerWidth, height: innerHeight, dpr: devicePixelRatio,
        touch: navigator.maxTouchPoints, webdriver: navigator.webdriver,
        secureContext: isSecureContext,
        screen: {width: screen.width, height: screen.height, colorDepth: screen.colorDepth},
        graphics: graphicsValues()
    };
    const source = '(async () => postMessage({...await (' + navigatorValues.toString() + ')(),graphics:(' + graphicsValues.toString() + ')()}))()';
    const url = URL.createObjectURL(new Blob([source], {type: 'text/javascript'}));
    let worker;
    try {
        const workerValues = await new Promise((resolve, reject) => {
            const timer = setTimeout(() => reject(new Error('Native worker probe timed out')), 5000);
            try { worker = new Worker(url); }
            catch (error) { clearTimeout(timer); reject(error); return; }
            worker.onmessage = event => { clearTimeout(timer); resolve(event.data); };
            worker.onerror = () => { clearTimeout(timer); reject(new Error('Native worker probe blocked or failed')); };
        });
        return {document: documentValues, worker: workerValues, workerError: ''};
    } catch (error) {
        return {document: documentValues, worker: null, workerError: String(error.message)};
    } finally { worker?.terminate(); URL.revokeObjectURL(url); }
}"""


def compare_observed(configuration: NativeConfiguration, observed: dict) -> list[str]:
    mismatches = []
    document = observed["document"]
    for key, expected in (("width", configuration.width), ("height", configuration.height),
                          ("dpr", configuration.device_scale_factor)):
        if document.get(key) != expected:
            mismatches.append(f"Document {key} differs from configured {expected}")
    if str(document.get("language", "")).lower() != configuration.locale.lower():
        mismatches.append("Document language differs from configured locale")
    if document.get("timezone") != configuration.timezone:
        mismatches.append("Document timezone differs from configured identifier; check IANA aliases")
    if configuration.environment == "mobile_web" and not document.get("touch"):
        mismatches.append("Mobile Web touch capability is unavailable")
    worker = observed.get("worker")
    if worker is None:
        mismatches.append(observed.get("workerError") or "Worker values could not be observed")
    else:
        for key in ("userAgent", "platform", "language", "languages", "hardwareConcurrency", "deviceMemory", "timezone", "userAgentData", "userAgentHighEntropy"):
            if worker.get(key) != document.get(key):
                mismatches.append(f"Document and dedicated worker disagree on {key}")
        document_graphics, worker_graphics = document.get("graphics", {}), worker.get("graphics", {})
        for kind in ("webgl", "webgl2"):
            if kind in document_graphics and kind in worker_graphics:
                first, second = document_graphics[kind], worker_graphics[kind]
                if first.get("available") != second.get("available"):
                    mismatches.append(f"Document and dedicated worker disagree on {kind} availability")
                elif first.get("available"):
                    for key in ("vendor", "renderer", "version", "shadingLanguage", "unmaskedVendor",
                                "unmaskedRenderer", "maxTextureSize", "maxViewportDimensions"):
                        if first.get(key) != second.get(key):
                            mismatches.append(f"Document and dedicated worker disagree on {kind} {key}")
    for scope in ("document", "worker"):
        if (observed.get(scope) or {}).get("userAgentDataError"):
            mismatches.append(f"{scope.capitalize()} high-entropy client hints could not be observed: "
                              + observed[scope]["userAgentDataError"])
    return mismatches


async def inspect_native_profile(page, configuration: NativeConfiguration, browser_version: str) -> dict:
    configuration.validate()
    observed = await page.evaluate(OBSERVE)
    return {"browser_version": browser_version, "configuration": asdict(configuration),
            "observed": observed, "mismatches": compare_observed(configuration, observed),
            "limitations": configuration.limitations(), "native_patch_capabilities": []}
