"""Read actual Native browser values; never replace fingerprint APIs."""

from dataclasses import asdict
import re

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
                const extensions = context.getSupportedExtensions();
                const contextAttributes = context.getContextAttributes();
                if (extensions === null || contextAttributes === null) throw new Error('Native graphics context was lost');
                const limits = {};
                for (const name of ['MAX_TEXTURE_SIZE', 'MAX_CUBE_MAP_TEXTURE_SIZE',
                                    'MAX_RENDERBUFFER_SIZE', 'MAX_VERTEX_ATTRIBS',
                                    'MAX_TEXTURE_IMAGE_UNITS', 'MAX_VERTEX_TEXTURE_IMAGE_UNITS']) {
                    limits[name] = context.getParameter(context[name]);
                }
                result[kind] = {
                    available: true,
                    vendor: context.getParameter(context.VENDOR),
                    renderer: context.getParameter(context.RENDERER),
                    version: context.getParameter(context.VERSION),
                    shadingLanguage: context.getParameter(context.SHADING_LANGUAGE_VERSION),
                    unmaskedVendor: debug ? context.getParameter(debug.UNMASKED_VENDOR_WEBGL) : null,
                    unmaskedRenderer: debug ? context.getParameter(debug.UNMASKED_RENDERER_WEBGL) : null,
                    maxTextureSize: context.getParameter(context.MAX_TEXTURE_SIZE),
                    maxViewportDimensions: Array.from(context.getParameter(context.MAX_VIEWPORT_DIMS)),
                    extensions: extensions.slice().sort(), limits, contextAttributes
                };
                if (context.getError() !== context.NO_ERROR) throw new Error('Native graphics metadata query failed');
            } catch (error) {
                result[kind] = {available: false, error: String(error.message)};
            } finally { context?.getExtension('WEBGL_lose_context')?.loseContext(); }
        }
        return result;
    };
    const webGPUValues = async () => {
        let timer;
        try {
            if (!navigator.gpu) throw new Error('WebGPU unavailable');
            const adapter = await Promise.race([
                navigator.gpu.requestAdapter(),
                new Promise((resolve, reject) => {
                    timer = setTimeout(() => reject(new Error('WebGPU adapter request timed out')), 3000);
                })
            ]);
            if (!adapter) throw new Error('Native WebGPU adapter unavailable');
            const info = adapter.info;
            const limits = {};
            for (const name of ['maxTextureDimension2D', 'maxBindGroups', 'maxBufferSize',
                                'maxStorageBufferBindingSize', 'maxComputeWorkgroupSizeX',
                                'maxComputeInvocationsPerWorkgroup']) {
                limits[name] = adapter.limits[name];
            }
            return {available: true, features: Array.from(adapter.features).sort(), limits,
                info: {vendor: info.vendor, architecture: info.architecture, device: info.device,
                    description: info.description, isFallbackAdapter: info.isFallbackAdapter,
                    subgroupMinSize: info.subgroupMinSize, subgroupMaxSize: info.subgroupMaxSize}};
        } catch (error) { return {available: false, error: String(error.message)}; }
        finally { clearTimeout(timer); }
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
            intlLocale: Intl.DateTimeFormat().resolvedOptions().locale,
            userAgentData: navigator.userAgentData?.toJSON() ?? null,
            userAgentHighEntropy, userAgentDataError
        };
    };
    const documentValues = {...await navigatorValues(),
        width: innerWidth, height: innerHeight, dpr: devicePixelRatio,
        touch: navigator.maxTouchPoints, webdriver: navigator.webdriver,
        secureContext: isSecureContext,
        screen: {width: screen.width, height: screen.height, colorDepth: screen.colorDepth,
            pixelDepth: screen.pixelDepth, availWidth: screen.availWidth, availHeight: screen.availHeight,
            orientation: {type: screen.orientation.type, angle: screen.orientation.angle}},
        graphics: graphicsValues(), webgpu: await webGPUValues(), canvas: await canvasValues(),
        audio: await audioValues(), media: await mediaValues()
    };
    const source = '(async () => postMessage({...await (' + navigatorValues.toString() + ')(),graphics:(' + graphicsValues.toString() + ')(),webgpu:await (' + webGPUValues.toString() + ')(),canvas:await (' + canvasValues.toString() + ')()}))()';
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
    if "screen" in document:
        screen = document["screen"]
        if not isinstance(screen, dict):
            mismatches.append("Document screen geometry could not be observed")
        else:
            for key, expected in (("width", configuration.width), ("height", configuration.height)):
                if type(screen.get(key)) is not int or screen[key] != expected:
                    mismatches.append(f"Document screen {key} differs from configured {expected}")
            for available, size in (("availWidth", "width"), ("availHeight", "height")):
                if available in screen and (type(screen.get(available)) is not int
                        or type(screen.get(size)) is not int or not 0 <= screen[available] <= screen[size]):
                    mismatches.append(f"Document screen {available} is inconsistent with {size}")
    worker = observed.get("worker")
    if worker is None:
        mismatches.append(observed.get("workerError") or "Worker values could not be observed")
    else:
        for key in ("userAgent", "platform", "language", "languages", "hardwareConcurrency", "deviceMemory", "timezone", "intlLocale", "userAgentData", "userAgentHighEntropy"):
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
        if "webgpu" in document or "webgpu" in worker:
            first, second = document.get("webgpu"), worker.get("webgpu")
            if (not isinstance(first, dict) or not isinstance(second, dict)
                    or type(first.get("available")) is not bool or type(second.get("available")) is not bool):
                mismatches.append("WebGPU observations could not be compared")
            elif first.get("available") != second.get("available"):
                mismatches.append("Document and dedicated worker disagree on webgpu availability")
            elif first.get("available"):
                for key in ("info", "features", "limits"):
                    if first.get(key) != second.get(key):
                        mismatches.append(f"Document and dedicated worker disagree on webgpu {key}")
        document_graphics, worker_graphics = document.get("graphics", {}), worker.get("graphics", {})
        for kind in ("webgl", "webgl2"):
            if kind in document_graphics and kind in worker_graphics:
                first, second = document_graphics[kind], worker_graphics[kind]
                if first.get("available") != second.get("available"):
                    mismatches.append(f"Document and dedicated worker disagree on {kind} availability")
                elif first.get("available"):
                    for key in ("vendor", "renderer", "version", "shadingLanguage", "unmaskedVendor",
                                "unmaskedRenderer", "maxTextureSize", "maxViewportDimensions",
                                "extensions", "limits", "contextAttributes"):
                        if first.get(key) != second.get(key):
                            mismatches.append(f"Document and dedicated worker disagree on {kind} {key}")
    for scope in ("document", "worker"):
        if (observed.get(scope) or {}).get("userAgentDataError"):
            mismatches.append(f"{scope.capitalize()} high-entropy client hints could not be observed: "
                              + observed[scope]["userAgentDataError"])
    return mismatches


def audit_observed_identity(observed: dict, browser_version: str) -> list[str]:
    """Check measured identity coherence, without inventing missing observations."""
    issues = []
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){3}", browser_version):
        return ["Actual Chromium runtime version could not be validated"]
    major = browser_version.split(".", 1)[0]
    for scope in ("document", "worker"):
        values = observed.get(scope)
        prefix = scope.capitalize()
        if not isinstance(values, dict):
            issues.append(f"{prefix} identity could not be observed")
            continue
        concurrency = values.get("hardwareConcurrency")
        if type(concurrency) is not int or concurrency <= 0:
            issues.append(f"{prefix} hardware concurrency is invalid")
        memory = values.get("deviceMemory")
        if "deviceMemory" not in values or (memory is not None and (
                type(memory) not in (int, float) or not 0 < memory <= 3.4028234663852886e38)):
            issues.append(f"{prefix} device memory observation is invalid")
        for field in ("userAgent", "platform", "language", "timezone", "intlLocale"):
            if not isinstance(values.get(field), str) or not values[field].strip():
                issues.append(f"{prefix} identity is missing {field}")
        languages = values.get("languages")
        if (not isinstance(languages, list) or not languages
                or any(not isinstance(value, str) or not value.strip() for value in languages)):
            issues.append(f"{prefix} identity is missing a valid languages list")
        elif (not isinstance(values.get("language"), str)
              or languages[0].casefold() != values["language"].casefold()):
            issues.append(f"{prefix} language disagrees with the primary languages entry")
        ua = values.get("userAgent", "")
        versions = re.findall(r"(?:HeadlessChrome|Chrome)/([0-9]+)(?:\.[0-9]+){3}(?:\s|$)", ua) if isinstance(ua, str) else []
        if versions != [major]:
            issues.append(f"{prefix} UA does not report the actual Chromium major version")
        hints = values.get("userAgentData")
        high = values.get("userAgentHighEntropy")
        if not isinstance(hints, dict) or not isinstance(high, dict):
            issues.append(f"{prefix} Client Hints coherence could not be observed")
            continue
        if not isinstance(hints.get("platform"), str) or not hints["platform"].strip():
            issues.append(f"{prefix} Client Hints platform is missing")
        hint_platform = hints.get("platform")
        navigator_platform = values.get("platform")
        expected_platforms = {"Win32": {"Windows"}, "Win64": {"Windows"},
                              "MacIntel": {"macOS"}, "MacPPC": {"macOS"}}
        if (isinstance(navigator_platform, str) and isinstance(hint_platform, str)
                and navigator_platform in expected_platforms
                and hint_platform not in expected_platforms[navigator_platform]):
            issues.append(f"{prefix} navigator platform disagrees with Client Hints OS")
        # Linux navigator.platform also occurs on Android and Chrome/Chromium OS.
        if (isinstance(navigator_platform, str) and isinstance(hint_platform, str)
                and navigator_platform.startswith("Linux")):
            if hint_platform not in {"Linux", "Android", "Chrome OS", "Chromium OS"}:
                issues.append(f"{prefix} navigator platform disagrees with Client Hints OS")
        if isinstance(ua, str) and isinstance(hint_platform, str):
            for marker, platforms in (("Windows NT", {"Windows"}), ("Macintosh", {"macOS"}),
                                      ("CrOS", {"Chrome OS", "Chromium OS"}),
                                      ("Linux", {"Linux", "Android"})):
                if marker in ua and hint_platform not in platforms:
                    issues.append(f"{prefix} UA operating system disagrees with Client Hints OS")
        if type(hints.get("mobile")) is not bool:
            issues.append(f"{prefix} Client Hints mobile flag is invalid")
        for key in ("brands", "mobile", "platform"):
            if (key not in high or type(high[key]) is not type(hints.get(key))
                    or high[key] != hints.get(key)):
                issues.append(f"{prefix} high-entropy Client Hints {key} disagrees with base hints")
        for key, expected, source in (("brands", major, hints), ("fullVersionList", browser_version, high)):
            brands = source.get(key)
            chromium = [brand.get("version") for brand in brands
                        if isinstance(brand, dict) and brand.get("brand") == "Chromium"] if isinstance(brands, list) else []
            if chromium != [expected]:
                issues.append(f"{prefix} Client Hints {key} disagrees with the actual Chromium version")
    return issues


def audit_observed_request_identity(headers: dict, observed: dict) -> list[str]:
    """Compare one document request with JS; not TLS or full Client Hints proof."""
    if (not isinstance(headers, dict) or any(not isinstance(key, str) or not isinstance(value, str)
                                           for key, value in headers.items())):
        return ["Document request identity headers could not be observed"]
    normalized = {key.lower(): value for key, value in headers.items()}
    if len(normalized) != len(headers):
        return ["Document request contains ambiguous repeated header names"]
    document = observed.get("document") if isinstance(observed, dict) else None
    if not isinstance(document, dict):
        return ["Document request identity cannot be compared without JS observations"]
    issues = []
    ua = document.get("userAgent")
    if not isinstance(ua, str) or not ua or normalized.get("user-agent") != ua:
        issues.append("Document request User-Agent disagrees with JS identity")
    language = document.get("language")
    primary = normalized.get("accept-language", "").split(",", 1)[0].split(";", 1)[0].strip()
    if not isinstance(language, str) or not language or primary.casefold() != language.casefold():
        issues.append("Document request Accept-Language disagrees with JS primary language")
    hints = document.get("userAgentData")
    if not isinstance(hints, dict):
        issues.append("Document request Client Hints cannot be compared without JS observations")
        return issues
    platform = hints.get("platform")
    if (not isinstance(platform, str) or not platform or not platform.isascii()
            or any(ord(value) < 32 or value in '\\"' for value in platform)
            or normalized.get("sec-ch-ua-platform") != '"' + platform + '"'):
        issues.append("Document request Client Hints platform disagrees with JS identity")
    mobile = hints.get("mobile")
    if type(mobile) is not bool or normalized.get("sec-ch-ua-mobile") != ("?1" if mobile else "?0"):
        issues.append("Document request Client Hints mobile flag disagrees with JS identity")
    return issues


async def inspect_native_profile(page, configuration: NativeConfiguration, browser_version: str) -> dict:
    configuration.validate()
    observed = await page.evaluate(OBSERVE)
    mismatches = compare_observed(configuration, observed) + audit_observed_identity(observed, browser_version)
    return {"browser_version": browser_version, "configuration": asdict(configuration),
            "observed": observed, "mismatches": mismatches,
            "limitations": configuration.limitations(), "native_patch_capabilities": []}
