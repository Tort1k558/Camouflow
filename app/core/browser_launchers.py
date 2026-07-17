import json
import random
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, cast

from .browser_proxy_service import BrowserProxyService
from .proxy_utils import LocalSocksProxyServer, ProxyDetails


def sample_webgl(*args, **kwargs):
    from camoufox.webgl.sample import sample_webgl as imported

    return imported(*args, **kwargs)


def load_or_create_profile_fingerprint_bundle(*args, **kwargs):
    from .camoufox_profile_fingerprint import load_or_create_profile_fingerprint_bundle as imported

    return imported(*args, **kwargs)


def normalize_locale_token(value: str) -> str:
    """
    Normalize a locale into a BCP47-ish tag that browsers accept.

    Examples:
    - "ru_RU" -> "ru-RU"
    - "en_US.UTF-8" -> "en-US"
    - "zh_Hant_HK" -> "zh-Hant-HK"
    """
    raw = str(value or "").strip()
    if not raw:
        return ""

    for sep in (".", "@"):
        if sep in raw:
            raw = raw.split(sep, 1)[0]
    raw = raw.replace("_", "-").strip()
    if not raw:
        return ""

    if raw.upper() in {"C", "POSIX"}:
        return ""

    parts = [p for p in raw.split("-") if p]
    if not parts:
        return ""

    normalized: List[str] = []
    for idx, part in enumerate(parts):
        token = part.strip()
        if not token:
            continue
        if idx == 0:
            normalized.append(token.lower())
            continue
        if len(token) == 4 and token.isalpha():
            normalized.append(token.title())
            continue
        if (len(token) == 2 and token.isalpha()) or (len(token) == 3 and token.isdigit()):
            normalized.append(token.upper())
            continue
        normalized.append(token)

    return "-".join(normalized)


def load_or_create_cloakbrowser_seed(profile_dir: Path) -> int:
    path = Path(profile_dir) / "cloakbrowser_fingerprint.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        seed = int(data.get("seed"))
        if 10_000 <= seed <= 99_999_999:
            if path.read_bytes().startswith(b"\xef\xbb\xbf"):
                path.write_text(json.dumps({"seed": seed}, ensure_ascii=False, indent=2), encoding="utf-8")
            return seed
    except Exception:
        pass
    seed = random.randint(10_000, 99_999_999)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"seed": seed}, ensure_ascii=False, indent=2), encoding="utf-8")
    return seed


def split_setting_list(value: object) -> List[str]:
    if isinstance(value, str):
        parts = []
        for chunk in value.replace("\r", "\n").replace(",", "\n").split("\n"):
            chunk = chunk.strip()
            if chunk:
                parts.append(chunk)
        return parts
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def browser_headless_value(raw: object) -> object:
    if isinstance(raw, bool):
        return raw
    headless_mode = str(raw or "").strip().lower()
    if headless_mode in {"true", "headless"}:
        return True
    if headless_mode in {"virtual"}:
        return "virtual"
    if headless_mode in {"false", "windowed", ""}:
        return False
    return False


def chromium_headless_value(raw: object) -> bool:
    if isinstance(raw, bool):
        return raw
    value = str(raw or "").strip().lower()
    return value in {"1", "true", "yes", "headless", "virtual"}


def positive_int(raw: object, default: int = 0) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def positive_float(raw: object, default: float = 0.0) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def normalize_navigator_overrides(raw: Optional[Dict[str, object]]) -> Dict[str, object]:
    if not isinstance(raw, dict):
        return {}
    cleaned: Dict[str, object] = {}
    for key, value in raw.items():
        if value is None:
            continue
        if key == "languages":
            languages: List[str] = []
            if isinstance(value, list):
                languages = [str(item).strip() for item in value if str(item).strip()]
            elif isinstance(value, str):
                chunks = value.replace("\r", "\n").replace(",", "\n").split("\n")
                languages = [chunk.strip() for chunk in chunks if chunk.strip()]
            if languages:
                cleaned[key] = languages
            continue
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                cleaned[key] = stripped
            continue
        if isinstance(value, bool):
            cleaned[key] = value
            continue
        if isinstance(value, (int, float)):
            cleaned[key] = int(value)
            continue
    return cleaned


def normalize_window_overrides(raw: Optional[Dict[str, object]]) -> Dict[str, object]:
    if not isinstance(raw, dict):
        return {}
    schema: Dict[str, Dict[str, type]] = {
        "screen": {
            "availHeight": int,
            "availWidth": int,
            "availTop": int,
            "availLeft": int,
            "height": int,
            "width": int,
            "colorDepth": int,
            "pixelDepth": int,
        },
        "page": {
            "pageXOffset": float,
            "pageYOffset": float,
        },
        "browser": {
            "scrollMinX": int,
            "scrollMinY": int,
            "scrollMaxX": int,
            "scrollMaxY": int,
            "outerHeight": int,
            "outerWidth": int,
            "innerHeight": int,
            "innerWidth": int,
            "screenX": int,
            "screenY": int,
            "devicePixelRatio": float,
        },
        "history": {
            "length": int,
        },
    }
    cleaned: Dict[str, Dict[str, object]] = {}
    for section, fields in schema.items():
        payload = raw.get(section)
        if not isinstance(payload, dict):
            continue
        section_clean: Dict[str, object] = {}
        for field, field_type in fields.items():
            value = payload.get(field)
            if value is None:
                continue
            try:
                normalized = float(value) if field_type is float else int(value)
            except (TypeError, ValueError):
                continue
            section_clean[field] = normalized
        if section_clean:
            cleaned[section] = section_clean
    return cleaned


class CamoufoxLaunchBuilder:
    """Build Camoufox launch kwargs and own the optional local SOCKS bridge."""

    def __init__(
        self,
        profile_name: str,
        user_data_dir: Path,
        browser_settings: Dict[str, object],
        defaults: Dict[str, Any],
        proxy_config: Optional[Dict[str, str]],
        proxy_details: Optional[ProxyDetails],
        proxy_service: BrowserProxyService,
        proxy_logger,
        logger,
        detect_browser_locale: Callable[[], str],
    ) -> None:
        self.profile_name = profile_name
        self.user_data_dir = Path(user_data_dir)
        self.browser_settings = browser_settings
        self.defaults = defaults
        self.proxy_config = proxy_config
        self.proxy_details = proxy_details
        self.proxy_service = proxy_service
        self.proxy_logger = proxy_logger
        self.logger = logger
        self.detect_browser_locale = detect_browser_locale
        self.local_proxy: Optional[LocalSocksProxyServer] = None

    def build(self) -> Dict[str, object]:
        proxy_for_launch = self._build_proxy_for_launch()
        config_overrides: Dict[str, object] = {}

        merged = dict(self.defaults or {})
        merged.update({k: v for k, v in (self.browser_settings or {}).items() if v is not None})

        locale_raw = str(merged.get("locale") or "").strip() or self.detect_browser_locale()
        locale_value = normalize_locale_token(locale_raw) or "en-US"
        timezone_value = str(merged.get("timezone") or "").strip()
        os_value = merged.get("os")
        os_list = split_setting_list(os_value)
        if os_list:
            os_payload: Optional[object] = os_list if len(os_list) > 1 else os_list[0]
        elif isinstance(os_value, str) and os_value.strip():
            os_payload = os_value.strip()
        else:
            os_payload = ["windows", "macos", "linux"]

        fonts_list = split_setting_list(merged.get("fonts"))
        addons_list = split_setting_list(merged.get("addons"))
        exclude_list = self._normalize_exclude_addons(split_setting_list(merged.get("exclude_addons")))
        window_tuple = self._window_tuple(merged.get("window_width"), merged.get("window_height"))

        webgl_vendor = str(merged.get("webgl_vendor") or "").strip()
        webgl_renderer = str(merged.get("webgl_renderer") or "").strip()
        humanize_arg = self._humanize_arg(merged.get("humanize", True))

        try:
            fp, stable_overrides, stored_webgl = load_or_create_profile_fingerprint_bundle(
                self.user_data_dir,
                os_payload=os_payload,
                window=window_tuple,
                logger=self.logger,
            )
        except Exception as exc:
            raise RuntimeError(
                "Camoufox fingerprint data failed to load. Reinstall dependencies: "
                "python -m pip install --force-reinstall browserforge apify-fingerprint-datapoints orjson"
            ) from exc

        persistent_context_value = bool(merged.get("persistent_context", True))
        kwargs: Dict[str, object] = {
            "headless": browser_headless_value(merged.get("headless", False)),
            "humanize": humanize_arg,
            "locale": locale_value,
            "proxy": proxy_for_launch,
            "persistent_context": persistent_context_value,
            "enable_cache": bool(merged.get("enable_cache", True)),
            "i_know_what_im_doing": True,
            "fingerprint": fp,
        }
        if persistent_context_value:
            kwargs["user_data_dir"] = str(self.user_data_dir)

        locale_list = self._normalize_locale_list(locale_value)
        if locale_list:
            kwargs["locale"] = locale_list if len(locale_list) > 1 else locale_list[0]

        desired_pair = None
        if webgl_vendor and webgl_renderer:
            desired_pair = (webgl_vendor, webgl_renderer)
        elif stored_webgl:
            desired_pair = stored_webgl

        validated_pair = self._valid_webgl_pair(fp.navigator.userAgent, desired_pair)
        if validated_pair:
            kwargs["webgl_config"] = validated_pair
            if not os_payload:
                kwargs["os"] = self._infer_camoufox_os(fp.navigator.userAgent)
        if os_payload:
            kwargs["os"] = os_payload
        if fonts_list:
            kwargs["fonts"] = fonts_list
        if addons_list:
            kwargs["addons"] = addons_list
        if exclude_list:
            kwargs["exclude_addons"] = exclude_list
        if window_tuple:
            kwargs["window"] = window_tuple
        if merged.get("block_webrtc"):
            kwargs["block_webrtc"] = True
        if merged.get("block_images"):
            kwargs["block_images"] = True
        if merged.get("block_webgl"):
            kwargs["block_webgl"] = True
        if merged.get("disable_coop"):
            kwargs["disable_coop"] = True
        if stable_overrides:
            for key, value in stable_overrides.items():
                if key not in config_overrides and key not in {"webgl_vendor", "webgl_renderer"}:
                    config_overrides[key] = value
        if timezone_value:
            config_overrides["timezone"] = timezone_value
        else:
            timezone_id = self.proxy_service.detect_timezone()
            if timezone_id:
                config_overrides["timezone"] = timezone_id

        navigator_payload = normalize_navigator_overrides(merged.get("navigator_overrides"))
        if not navigator_payload and locale_list:
            navigator_payload = {"language": locale_list[0], "languages": list(locale_list)}
        if navigator_payload:
            for key, value in navigator_payload.items():
                config_overrides[f"navigator.{key}"] = value

        accept_language_source: Sequence[str] = []
        if isinstance(navigator_payload, dict) and isinstance(navigator_payload.get("languages"), list):
            accept_language_source = cast(List[str], navigator_payload.get("languages") or [])
        elif locale_list:
            accept_language_source = locale_list
        accept_language = self._build_accept_language(accept_language_source)
        if accept_language:
            config_overrides["headers.Accept-Language"] = accept_language

        window_payload = normalize_window_overrides(merged.get("window_overrides"))
        if window_payload:
            for section, values in window_payload.items():
                if not isinstance(values, dict):
                    continue
                prefix = "window.history" if section == "history" else section
                for field, value in values.items():
                    config_overrides[f"{prefix}.{field}"] = value
        if config_overrides:
            kwargs["config"] = config_overrides
        return kwargs

    def _build_proxy_for_launch(self):
        proxy_applied = False
        proxy_for_launch = None
        if self.proxy_config and self.proxy_details:
            scheme = (self.proxy_details.scheme or "").lower()
            if scheme.startswith("socks"):
                self.local_proxy = LocalSocksProxyServer(self.proxy_details, profile_name=self.profile_name)
                proxy_url = self.local_proxy.start()
                self.proxy_service.set_local_proxy(self.local_proxy)
                time.sleep(3)
                proxy_for_launch = {"server": proxy_url}
                msg = (
                    f"Using local SOCKS bridge for {self.profile_name} via upstream "
                    f"{self.proxy_details.scheme}://{self.proxy_details.host}:{self.proxy_details.port}"
                )
                self.proxy_logger.info(msg)
                proxy_applied = True
            else:
                proxy_for_launch = self.proxy_config
                msg = (
                    f"Using direct proxy for {self.profile_name}: "
                    f"{self.proxy_details.scheme}://{self.proxy_details.host}:{self.proxy_details.port}"
                )
                self.proxy_logger.info(msg)
                proxy_applied = True
        elif self.proxy_config:
            proxy_for_launch = self.proxy_config
            msg = f"Using proxy settings without parsed details for {self.profile_name}"
            self.proxy_logger.info(msg)
            proxy_applied = True

        if proxy_applied:
            self.proxy_logger.info("Proxy applied for %s", self.profile_name)
        else:
            self.proxy_logger.info("No proxy applied for %s", self.profile_name)
        return proxy_for_launch

    @staticmethod
    def _normalize_exclude_addons(values: Sequence[str]) -> List[object]:
        try:
            from camoufox import DefaultAddons
        except Exception:
            return [str(v).strip() for v in values if str(v).strip()]
        out: List[object] = []
        for raw in values:
            token = str(raw).strip()
            if not token:
                continue
            key = token.split(".")[-1].upper()
            if hasattr(DefaultAddons, key):
                out.append(getattr(DefaultAddons, key))
            else:
                out.append(token)
        return out

    @staticmethod
    def _window_tuple(width: object, height: object) -> Optional[Tuple[int, int]]:
        try:
            w_int = int(width)
            h_int = int(height)
            if w_int > 0 and h_int > 0:
                return w_int, h_int
        except Exception:
            return None
        return None

    @staticmethod
    def _humanize_arg(humanize_setting: object) -> object:
        if isinstance(humanize_setting, bool):
            return humanize_setting
        try:
            duration = float(humanize_setting)
            return duration if duration > 0 else True
        except Exception:
            return True

    @staticmethod
    def _normalize_locale_list(locale_str: str) -> List[str]:
        raw = (locale_str or "").strip()
        if not raw:
            return []
        if "," in raw:
            parts = [p.strip() for p in raw.split(",") if p.strip()]
        else:
            parts = [raw]
        normalized_parts: List[str] = []
        seen = set()
        for p in parts:
            tok = normalize_locale_token(p)
            if not tok or tok in seen:
                continue
            seen.add(tok)
            normalized_parts.append(tok)
        if not normalized_parts:
            return []
        primary = normalized_parts[0]
        if "-" in primary:
            chunks = primary.split("-")
            if len(chunks) >= 3:
                script_tag = "-".join(chunks[:2])
                if script_tag not in normalized_parts:
                    normalized_parts.append(script_tag)
            lang_tag = chunks[0]
            if lang_tag and lang_tag not in normalized_parts:
                normalized_parts.append(lang_tag)
        return normalized_parts

    @staticmethod
    def _build_accept_language(locales: Sequence[str]) -> str:
        seen = set()
        items: List[str] = []
        for loc in locales:
            token = str(loc or "").strip()
            if not token or token in seen:
                continue
            seen.add(token)
            items.append(token)
        if not items:
            return ""
        out: List[str] = []
        for idx, token in enumerate(items):
            if idx == 0:
                out.append(token)
                continue
            q = max(0.1, 1.0 - (0.1 * idx))
            out.append(f"{token};q={q:.1f}")
        return ",".join(out)

    @staticmethod
    def _infer_camoufox_os(user_agent: str) -> str:
        ua = (user_agent or "").lower()
        if "windows" in ua:
            return "windows"
        if "macintosh" in ua or "mac os" in ua or "macos" in ua:
            return "macos"
        return "linux"

    @staticmethod
    def _target_os_key(user_agent: str) -> str:
        ua = (user_agent or "").lower()
        if "windows" in ua:
            return "win"
        if "mac" in ua:
            return "mac"
        return "lin"

    @staticmethod
    def _webgl_pair_matches_user_agent(user_agent: str, renderer: str) -> bool:
        ua = (user_agent or "").lower()
        renderer_l = (renderer or "").lower()
        if "macintosh" in ua and "intel" in ua:
            if "apple m" in renderer_l or "m1" in renderer_l or "m2" in renderer_l or "m3" in renderer_l:
                return False
        if "macintosh" in ua and ("arm" in ua or "aarch" in ua):
            if "intel" in renderer_l:
                return False
        return True

    def _valid_webgl_pair(
        self,
        user_agent: str,
        pair: Optional[Tuple[str, str]],
    ) -> Optional[Tuple[str, str]]:
        if not pair:
            return None
        vendor, renderer = pair
        if not self._webgl_pair_matches_user_agent(user_agent, renderer):
            self.logger.warning(
                "WebGL renderer does not match user agent for %s; falling back to random",
                self.profile_name,
            )
            return None
        try:
            sample_webgl(self._target_os_key(user_agent), vendor, renderer)
        except Exception:
            self.logger.warning(
                "Invalid WebGL vendor/renderer for %s; falling back to random",
                self.profile_name,
            )
            return None
        return vendor, renderer


class CloakBrowserLaunchBuilder:
    """Build CloakBrowser launch kwargs."""

    def __init__(
        self,
        profile_root: Path,
        defaults: Dict[str, Any],
        browser_settings: Dict[str, object],
        proxy_config: Optional[Dict[str, str]],
        detect_browser_locale: Callable[[], str],
        detect_browser_timezone: Callable[[], Optional[str]],
    ) -> None:
        self.profile_root = Path(profile_root)
        self.defaults = defaults
        self.browser_settings = browser_settings
        self.proxy_config = proxy_config
        self.detect_browser_locale = detect_browser_locale
        self.detect_browser_timezone = detect_browser_timezone

    def build(self) -> Dict[str, object]:
        merged = dict(self.defaults or {})
        merged.update({k: v for k, v in (self.browser_settings or {}).items() if v is not None})

        locale_raw = str(merged.get("locale") or "").strip() or self.detect_browser_locale()
        locale_value = normalize_locale_token(locale_raw) or "en-US"
        timezone_value = str(merged.get("timezone") or "").strip() or self.detect_browser_timezone()

        fingerprint_seed = positive_int(merged.get("fingerprint_seed"))
        if not fingerprint_seed:
            fingerprint_seed = load_or_create_cloakbrowser_seed(self.profile_root)
        args = [f"--fingerprint={fingerprint_seed}"]

        platform = str(merged.get("platform") or "").strip().lower()
        if platform in {"windows", "macos", "linux"}:
            args.append(f"--fingerprint-platform={platform}")

        for key, flag in {
            "platform_version": "--fingerprint-platform-version",
            "brand": "--fingerprint-brand",
            "brand_version": "--fingerprint-brand-version",
        }.items():
            value = str(merged.get(key) or "").strip()
            if value:
                args.append(f"{flag}={value}")

        gpu_vendor = str(merged.get("gpu_vendor") or "").strip()
        if gpu_vendor:
            args.append(f"--fingerprint-gpu-vendor={gpu_vendor}")

        gpu_renderer = str(merged.get("gpu_renderer") or "").strip()
        if gpu_renderer:
            args.append(f"--fingerprint-gpu-renderer={gpu_renderer}")

        hardware_concurrency = positive_int(merged.get("hardware_concurrency"))
        if hardware_concurrency:
            args.append(f"--fingerprint-hardware-concurrency={hardware_concurrency}")

        device_memory = positive_int(merged.get("device_memory"))
        if device_memory:
            args.append(f"--fingerprint-device-memory={device_memory}")

        storage_quota = positive_int(merged.get("storage_quota"))
        if storage_quota:
            args.append(f"--fingerprint-storage-quota={storage_quota}")

        if merged.get("fingerprint_noise") is False:
            args.append("--fingerprint-noise=false")

        webrtc_ip = str(merged.get("webrtc_ip") or "").strip()
        if webrtc_ip:
            args.append(f"--fingerprint-webrtc-ip={webrtc_ip}")

        extension_paths = split_setting_list(merged.get("extension_paths"))
        if extension_paths:
            extension_arg = ",".join(extension_paths)
            args.extend(
                [
                    f"--disable-extensions-except={extension_arg}",
                    f"--load-extension={extension_arg}",
                ]
            )
        if bool(merged.get("disable_http2", False)):
            args.append("--disable-http2")
        args.extend(split_setting_list(merged.get("launch_args")))

        width = merged.get("screen_width") or merged.get("window_width")
        height = merged.get("screen_height") or merged.get("window_height")
        viewport: Optional[Dict[str, int]] = None
        w_int = positive_int(width)
        h_int = positive_int(height)
        if w_int and h_int:
            viewport = {"width": w_int, "height": h_int}
            args.append(f"--window-size={w_int},{h_int}")
            args.append(f"--fingerprint-screen-width={w_int}")
            args.append(f"--fingerprint-screen-height={h_int}")

        humanize_value = merged.get("humanize", True)
        if isinstance(humanize_value, bool):
            humanize_enabled = humanize_value
        else:
            humanize_enabled = str(humanize_value).strip().lower() not in {"0", "false", "no", "off"}
        human_preset = str(merged.get("human_preset") or "default").strip().lower()
        if human_preset not in {"default", "careful"}:
            human_preset = "default"

        human_config: Dict[str, object] = {}
        mouse_speed = positive_float(merged.get("human_mouse_speed"))
        if mouse_speed:
            human_config["mouse_speed"] = mouse_speed
        typing_min = positive_int(merged.get("human_typing_delay_min"))
        typing_max = positive_int(merged.get("human_typing_delay_max"))
        if typing_min:
            human_config["typing_delay_min"] = typing_min
        if typing_max:
            human_config["typing_delay_max"] = typing_max
        scroll_intensity = positive_int(merged.get("human_scroll_intensity"))
        if scroll_intensity:
            human_config["scroll_intensity"] = scroll_intensity
        if merged.get("human_actionability_wait") is False:
            human_config["actionability_wait"] = False

        proxy_config = dict(self.proxy_config) if self.proxy_config else None
        proxy_bypass = str(merged.get("proxy_bypass") or "").strip()
        if proxy_config and proxy_bypass:
            proxy_config["bypass"] = proxy_bypass

        kwargs: Dict[str, object] = {
            "headless": chromium_headless_value(merged.get("headless", False)),
            "proxy": proxy_config,
            "args": args,
            "locale": locale_value,
            "timezone": timezone_value,
            "humanize": humanize_enabled,
            "human_preset": human_preset,
        }
        if human_config:
            kwargs["human_config"] = human_config
        kwargs["stealth_args"] = bool(merged.get("stealth_args", True))
        backend = str(merged.get("backend") or "").strip()
        if backend:
            kwargs["backend"] = backend
        user_agent = str(merged.get("user_agent") or "").strip()
        if user_agent:
            kwargs["user_agent"] = user_agent
        color_scheme = str(merged.get("color_scheme") or "").strip().lower()
        if color_scheme in {"light", "dark", "no-preference"}:
            kwargs["color_scheme"] = color_scheme
        kwargs["geoip"] = bool(merged.get("geoip", False))
        if viewport:
            kwargs["viewport"] = viewport
        else:
            kwargs["viewport"] = None
        context_kwargs = self._context_kwargs(merged)
        if context_kwargs:
            kwargs["context_kwargs"] = context_kwargs
        return kwargs

    @staticmethod
    def _context_kwargs(merged: Dict[str, Any]) -> Dict[str, object]:
        kwargs: Dict[str, object] = {}
        headers = merged.get("extra_http_headers")
        if isinstance(headers, dict) and headers:
            kwargs["extra_http_headers"] = {str(k): str(v) for k, v in headers.items() if str(k).strip()}
        permissions = split_setting_list(merged.get("permissions"))
        if permissions:
            kwargs["permissions"] = permissions
        storage_state_path = str(merged.get("storage_state_path") or "").strip()
        if storage_state_path:
            kwargs["storage_state"] = storage_state_path
        for key in ("ignore_https_errors", "java_script_enabled", "bypass_csp", "accept_downloads"):
            if key in merged:
                kwargs[key] = bool(merged.get(key))
        return kwargs
