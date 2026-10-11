"""Read actual Native browser values; never replace fingerprint APIs."""

from dataclasses import asdict

from .configuration import NativeConfiguration


OBSERVE = """async () => {
    const navigatorValues = () => ({
        userAgent: navigator.userAgent, platform: navigator.platform,
        language: navigator.language, languages: [...navigator.languages],
        hardwareConcurrency: navigator.hardwareConcurrency,
        deviceMemory: navigator.deviceMemory ?? null,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        userAgentData: navigator.userAgentData?.toJSON() ?? null
    });
    const documentValues = {...navigatorValues(),
        width: innerWidth, height: innerHeight, dpr: devicePixelRatio,
        touch: navigator.maxTouchPoints, webdriver: navigator.webdriver,
        secureContext: isSecureContext,
        screen: {width: screen.width, height: screen.height, colorDepth: screen.colorDepth}
    };
    const source = 'postMessage((' + navigatorValues.toString() + ')())';
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
        for key in ("userAgent", "platform", "language", "languages", "hardwareConcurrency", "deviceMemory", "timezone", "userAgentData"):
            if worker.get(key) != document.get(key):
                mismatches.append(f"Document and dedicated worker disagree on {key}")
    return mismatches


async def inspect_native_profile(page, configuration: NativeConfiguration, browser_version: str) -> dict:
    configuration.validate()
    observed = await page.evaluate(OBSERVE)
    return {"browser_version": browser_version, "configuration": asdict(configuration),
            "observed": observed, "mismatches": compare_observed(configuration, observed),
            "limitations": configuration.limitations(), "native_patch_capabilities": []}
