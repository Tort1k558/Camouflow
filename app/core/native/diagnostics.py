"""Read actual Native browser values; never replace fingerprint APIs."""

from dataclasses import asdict

from .configuration import NativeConfiguration


OBSERVE = """async () => {
    const canvasValues = async () => {
        let canvas;
        try {
            canvas = new OffscreenCanvas(256, 48);
            const context = canvas.getContext('2d');
            if (!context) throw new Error('Native 2D context unavailable');
            context.font = '20px Arial';
            context.fillStyle = '#246b45';
            const text = 'Glint 0123';
            const width = context.measureText(text).width;
            context.fillText(text, 4, 28);
            const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
            let pixelSha256 = null;
            let hashError = '';
            if (self.crypto?.subtle) {
                try {
                    const digest = await crypto.subtle.digest('SHA-256', pixels);
                    pixelSha256 = Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, '0')).join('');
                } catch (error) { hashError = String(error.message); }
            } else { hashError = 'SHA-256 unavailable outside a secure context'; }
            return {available: true, font: context.font, textWidth: width, pixelSha256, hashError};
        } catch (error) { return {available: false, error: String(error.message)}; }
        finally { if (canvas) canvas.width = 0; }
    };
    const audioValues = async () => {
        let oscillator;
        try {
            if (typeof OfflineAudioContext === 'undefined') throw new Error('OfflineAudioContext unavailable');
            const context = new OfflineAudioContext(1, 4096, 44100);
            oscillator = context.createOscillator();
            oscillator.frequency.value = 440;
            oscillator.connect(context.destination);
            oscillator.start();
            oscillator.stop(4096 / 44100);
            const buffer = await context.startRendering();
            const samples = buffer.getChannelData(0);
            let absoluteSum = 0;
            for (const value of samples) absoluteSum += Math.abs(value);
            return {available: true, probeSampleRate: buffer.sampleRate, channels: buffer.numberOfChannels,
                frames: buffer.length, absoluteSum};
        } catch (error) { return {available: false, error: String(error.message)}; }
        finally { oscillator?.disconnect(); }
    };
    const mediaValues = async () => {
        let timer;
        try {
            if (!navigator.mediaDevices?.enumerateDevices) throw new Error('Media device enumeration unavailable');
            const devices = await Promise.race([
                navigator.mediaDevices.enumerateDevices(),
                new Promise((resolve, reject) => {
                    timer = setTimeout(() => reject(new Error('Media device enumeration timed out')), 3000);
                })
            ]);
            const counts = {audioinput: 0, audiooutput: 0, videoinput: 0};
            for (const device of devices) if (device.kind in counts) counts[device.kind]++;
            return {available: true, counts};
        } catch (error) { return {available: false, error: String(error.message)}; }
        finally { clearTimeout(timer); }
    };
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
        graphics: graphicsValues(), canvas: await canvasValues(),
        audio: await audioValues(), media: await mediaValues()
    };
    const source = '(async () => postMessage({...await (' + navigatorValues.toString() + ')(),graphics:(' + graphicsValues.toString() + ')(),canvas:await (' + canvasValues.toString() + ')()}))()';
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
        if "canvas" in document and "canvas" in worker:
            first, second = document["canvas"], worker["canvas"]
            if first.get("available") != second.get("available"):
                mismatches.append("Document and dedicated worker disagree on canvas availability")
            elif first.get("available"):
                for key in ("font", "textWidth", "pixelSha256"):
                    if first.get(key) != second.get(key):
                        mismatches.append(f"Document and dedicated worker disagree on canvas {key}")
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
