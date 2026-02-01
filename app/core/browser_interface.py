import asyncio
import json
import locale
import logging
import os
import random
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
import urllib.request
import urllib.parse
from typing import Callable, Dict, List, Optional, Sequence, cast

import socks

from camoufox import AsyncCamoufox
from camoufox.webgl.sample import sample_webgl
from camoufox.utils import launch_options
from app.storage.db import db_get_camoufox_defaults, profile_dir_for_email
from .camoufox_profile_fingerprint import load_or_create_profile_fingerprint_bundle
from .locale_mapping import country_to_locale
from .proxy_utils import LocalSocksProxyServer, ProxyDetails, parse_proxy


class BrowserInterface:
    """Browser/proxy interface that starts Camoufox and exposes a Playwright page."""

    @staticmethod
    def _normalize_locale_token(value: str) -> str:
        """
        Normalize a locale into a BCP47-ish tag that Camoufox accepts.

        Examples:
        - "ru_RU" -> "ru-RU"
        - "en_US.UTF-8" -> "en-US"
        - "zh_Hant_HK" -> "zh-Hant-HK"
        """
        raw = str(value or "").strip()
        if not raw:
            return ""

        # Strip encoding/modifiers from typical OS locale strings: "en_US.UTF-8", "de_DE@euro"
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

    def __init__(
        self,
        profile_name,
        proxy: str = "",
        keep_browser_open: bool = True,
        camoufox_settings: Optional[Dict[str, object]] = None,
    ) -> None:
        self.profile_name = profile_name
        self.proxy = proxy
        self.keep_browser_open = keep_browser_open
        self.user_data_dir = profile_dir_for_email(self.profile_name)
        os.makedirs(self.user_data_dir, exist_ok=True)
        self._camoufox_settings = camoufox_settings or {}
        self._camoufox_defaults = db_get_camoufox_defaults()

        self.logger = logging.LoggerAdapter(logging.getLogger(__name__), {"profile": self.profile_name})
        self._proxy_logger = self._init_proxy_logger()

        self.browser = None
        self.context = None
        self.page = None
        self._close_callbacks: List[Callable[[], None]] = []
        self._closed_notified = False
        self._process_exit_callbacks: List[Callable[[], None]] = []
        self._process_exited_notified = False
        self._close_listener_attached = False
        self._ready_callbacks: List[Callable[[], None]] = []
        self._ready_notified = False
        self._camoufox_ctx: Optional[AsyncCamoufox] = None
        self._proxy_config, self._proxy_details = parse_proxy(proxy, profile_name=self.profile_name)
        if proxy and not self._proxy_config:
            msg = f"Proxy string provided for {self.profile_name} but failed to parse; proxy disabled"
            self.logger.warning(msg)
            self._proxy_logger.warning(msg)
        self._local_proxy: Optional[LocalSocksProxyServer] = None
        self._process_watchdog_started = False

    def _init_proxy_logger(self) -> logging.LoggerAdapter:
        proxy_logger = logging.getLogger("proxy_log")
        if not proxy_logger.handlers:
            proxy_logger.setLevel(logging.INFO)
            log_path = os.path.join(os.getcwd(), "logs", "proxy.log")
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            handler = logging.FileHandler(log_path, encoding="utf-8")
            fmt = logging.Formatter("%(asctime)s %(levelname)s [%(profile)s] %(message)s")
            handler.setFormatter(fmt)
            proxy_logger.addHandler(handler)
        proxy_logger.propagate = True
        return logging.LoggerAdapter(proxy_logger, {"profile": self.profile_name})

    def _build_launch_kwargs(self) -> Dict[str, object]:
        proxy_applied = False
        proxy_for_launch = None
        if self._proxy_config and self._proxy_details:
            scheme = (self._proxy_details.scheme or "").lower()
            if scheme.startswith("socks"):
                self._local_proxy = LocalSocksProxyServer(self._proxy_details, profile_name=self.profile_name)
                proxy_url = self._local_proxy.start()
                time.sleep(3)
                proxy_for_launch = {"server": proxy_url}
                msg = (
                    f"Using local SOCKS bridge for {self.profile_name} via upstream "
                    f"{self._proxy_details.scheme}://{self._proxy_details.host}:{self._proxy_details.port}"
                )
                self._proxy_logger.info(msg)
                proxy_applied = True
            else:
                proxy_for_launch = self._proxy_config
                msg = (
                    f"Using direct proxy for {self.profile_name}: "
                    f"{self._proxy_details.scheme}://{self._proxy_details.host}:{self._proxy_details.port}"
                )
                self._proxy_logger.info(msg)
                proxy_applied = True
        elif self._proxy_config:
            proxy_for_launch = self._proxy_config
            msg = f"Using proxy settings without parsed details for {self.profile_name}"
            self._proxy_logger.info(msg)
            proxy_applied = True

        if proxy_applied:
            self._proxy_logger.info("Proxy applied for %s", self.profile_name)
        else:
            self._proxy_logger.info("No proxy applied for %s", self.profile_name)

        config_overrides: Dict[str, object] = {}

        merged = dict(self._camoufox_defaults or {})
        merged.update({k: v for k, v in (self._camoufox_settings or {}).items() if v is not None})

        def _split_list(value) -> List[str]:
            if isinstance(value, str):
                parts = []
                for chunk in value.replace("\r", "\n").replace(",", "\n").split("\n"):
                    chunk = chunk.strip()
                    if chunk:
                        parts.append(chunk)
                return parts
            if isinstance(value, Sequence):
                return [str(item).strip() for item in value if str(item).strip()]
            return []

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


        headless_raw = merged.get("headless", False)
        headless_value: object
        if isinstance(headless_raw, bool):
            headless_value = headless_raw
        else:
            headless_mode = str(headless_raw or "").lower()
            if headless_mode in {"true", "headless"}:
                headless_value = True
            elif headless_mode in {"virtual"}:
                headless_value = "virtual"
            elif headless_mode in {"false", "windowed", ""}:
                headless_value = False
            else:
                headless_value = False

        locale_raw = str(merged.get("locale") or "").strip() or self._detect_browser_locale()
        locale_value = self._normalize_locale_token(locale_raw) or "en-US"
        timezone_value = str(merged.get("timezone") or "").strip()
        os_value = merged.get("os")
        os_list = _split_list(os_value)
        os_payload: Optional[object]
        if os_list:
            os_payload = os_list if len(os_list) > 1 else os_list[0]
        elif isinstance(os_value, str) and os_value.strip():
            os_payload = os_value.strip()
        else:
            # UI "Auto" means no OS is selected. Treat it as "all OS allowed" to match Camoufox defaults.
            os_payload = ["windows", "macos", "linux"]

        fonts_list = _split_list(merged.get("fonts"))
        addons_list = _split_list(merged.get("addons"))
        exclude_raw = _split_list(merged.get("exclude_addons"))
        exclude_list = _normalize_exclude_addons(exclude_raw)
        width = merged.get("window_width")
        height = merged.get("window_height")
        window_tuple = None
        try:
            w_int = int(width)
            h_int = int(height)
            if w_int > 0 and h_int > 0:
                window_tuple = (w_int, h_int)
        except Exception:
            window_tuple = None

        webgl_vendor = str(merged.get("webgl_vendor") or "").strip()
        webgl_renderer = str(merged.get("webgl_renderer") or "").strip()
        humanize_setting = merged.get("humanize", True)
        if isinstance(humanize_setting, bool):
            humanize_arg: object = humanize_setting
        else:
            try:
                duration = float(humanize_setting)
                humanize_arg = duration if duration > 0 else True
            except Exception:
                humanize_arg = True

        fp, stable_overrides, stored_webgl = load_or_create_profile_fingerprint_bundle(
            Path(self.user_data_dir),
            os_payload=os_payload,
            window=window_tuple,
            logger=self.logger,
        )

        kwargs = {
            "headless": headless_value,
            "humanize": humanize_arg,
            "locale": locale_value,
            "proxy": proxy_for_launch,
            "persistent_context": bool(merged.get("persistent_context", True)),
            "user_data_dir": str(self.user_data_dir),
            "enable_cache": bool(merged.get("enable_cache", True)),
            "i_know_what_im_doing": False,
            "fingerprint": fp,
        }

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
                tok = self._normalize_locale_token(p)
                if not tok or tok in seen:
                    continue
                seen.add(tok)
                normalized_parts.append(tok)
            if not normalized_parts:
                return []
            primary = normalized_parts[0]
            # Add common fallbacks (e.g. "en-GB" -> "en", "zh-Hant-HK" -> "zh-Hant", "zh").
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

        locale_list = _normalize_locale_list(locale_value)
        if locale_list:
            kwargs["locale"] = locale_list if len(locale_list) > 1 else locale_list[0]

        def _infer_camoufox_os(user_agent: str) -> str:
            ua = (user_agent or "").lower()
            if "windows" in ua:
                return "windows"
            if "macintosh" in ua or "mac os" in ua or "macos" in ua:
                return "macos"
            return "linux"

        def _target_os_key(user_agent: str) -> str:
            ua = (user_agent or "").lower()
            if "windows" in ua:
                return "win"
            if "mac" in ua:
                return "mac"
            return "lin"

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

        def _valid_webgl_pair(pair: Optional[tuple[str, str]]) -> Optional[tuple[str, str]]:
            if not pair:
                return None
            vendor, renderer = pair
            if not _webgl_pair_matches_user_agent(fp.navigator.userAgent, renderer):
                self.logger.warning(
                    "WebGL renderer does not match user agent for %s; falling back to random",
                    self.profile_name,
                )
                return None
            try:
                sample_webgl(_target_os_key(fp.navigator.userAgent), vendor, renderer)
            except Exception:
                self.logger.warning(
                    "Invalid WebGL vendor/renderer for %s; falling back to random",
                    self.profile_name,
                )
                return None
            return vendor, renderer

        desired_pair = None
        if webgl_vendor and webgl_renderer:
            desired_pair = (webgl_vendor, webgl_renderer)
        elif stored_webgl:
            desired_pair = stored_webgl

        validated_pair = _valid_webgl_pair(desired_pair)
        if validated_pair:
            kwargs["webgl_config"] = validated_pair
            if not os_payload:
                kwargs["os"] = _infer_camoufox_os(fp.navigator.userAgent)
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
            timezone_id = self._detect_browser_timezone()
            if timezone_id:
                config_overrides["timezone"] = timezone_id
        navigator_payload = self._normalize_navigator_overrides(merged.get("navigator_overrides"))
        if not navigator_payload and locale_list:
            navigator_payload = {"language": locale_list[0], "languages": list(locale_list)}
        if navigator_payload:
            for key, value in navigator_payload.items():
                config_overrides[f"navigator.{key}"] = value

        # Keep HTTP Accept-Language aligned with JS-exposed languages.
        accept_language_source: Sequence[str] = []
        if isinstance(navigator_payload, dict) and isinstance(navigator_payload.get("languages"), list):
            accept_language_source = cast(List[str], navigator_payload.get("languages") or [])
        elif locale_list:
            accept_language_source = locale_list
        accept_language = _build_accept_language(accept_language_source)
        if accept_language:
            config_overrides["headers.Accept-Language"] = accept_language

        window_payload = self._normalize_window_overrides(merged.get("window_overrides"))
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

    def _normalize_navigator_overrides(self, raw: Optional[Dict[str, object]]) -> Dict[str, object]:
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

    def _normalize_window_overrides(self, raw: Optional[Dict[str, object]]) -> Dict[str, object]:
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
    
    def _probe_proxy_endpoint(self) -> bool:
        """Quick TCP probe to avoid long Camoufox waits when the proxy is unreachable."""
        if not self._proxy_details:
            return True
        try:
            with socket.create_connection(
                (self._proxy_details.host, self._proxy_details.port), timeout=5
            ):
                msg = f"Proxy endpoint reachable for {self.profile_name}: {self._proxy_details.host}:{self._proxy_details.port}"
                self._proxy_logger.info(msg)
                return True
        except OSError as exc:
            msg = f"Proxy {self._proxy_details.host}:{self._proxy_details.port} is unreachable: {exc}"
            self._proxy_logger.error(msg)
            return False

    def _verify_proxy_connection(self) -> bool:
        """Check whether a configured proxy is reachable and can issue HTTP requests."""
        if not self._proxy_config:
            return True
        if not self._proxy_details or not self._proxy_details.host or not self._proxy_details.port:
            self._proxy_logger.error(
                "Proxy provided for %s but missing details; cannot verify connectivity.",
                self.profile_name,
            )
            return False

        host_label = f"{self._proxy_details.host}:{self._proxy_details.port}"
        if not self._probe_proxy_endpoint():
            self._proxy_logger.error("Proxy verification failed for %s (unreachable %s).", self.profile_name, host_label)
            return False

        geo_response = self._fetch_country_via_proxy()
        if geo_response and geo_response.get("country_code"):
            self._proxy_logger.info(
                "Proxy verification succeeded for %s (%s -> %s).",
                self.profile_name,
                host_label,
                geo_response.get("country_code"),
            )
            return True

        self._proxy_logger.error(
            "Proxy verification failed for %s (%s). Details: %s",
            self.profile_name,
            host_label,
            geo_response,
        )
        return False

    def _detect_proxy_locale(self) -> Optional[str]:
        """
        Detect locale strictly via the configured proxy.

        Returns None when proxy lookup fails.
        """
        if not self._proxy_config:
            return None
        host_label = self._current_proxy_host_label()
        if not host_label:
            return None
        data = self._fetch_country_via_proxy()
        if data and data.get("country_code"):
            locale_str = self._country_to_locale(data.get("country_code"))
            self._proxy_logger.info("Locale detected via proxy %s -> %s", host_label, locale_str)
            return locale_str
        self._proxy_logger.error("Locale not detected via proxy %s; payload: %s", host_label, data)
        return None

    async def _human_type(self, element, text: str, clear: bool = True) -> None:
        """Type text into an element character by character with small random delays."""
        if element is None:
            return
        if clear:
            try:
                await element.fill("")
            except Exception:
                pass
        for ch in text:
            await element.type(ch)
            await asyncio.sleep(random.uniform(0.05, 0.25))

    @contextmanager
    def _geo_proxy_context(self):
        """Wrap geo IP requests so they always go through the current proxy."""
        if not self._proxy_details or not self._proxy_details.host:
            yield None
            return

        proxy_host = self._proxy_details.host
        proxy_port = int(self._proxy_details.port)
        if getattr(self, "_local_proxy", None) and getattr(self._local_proxy, "port", None):
            proxy_host = "127.0.0.1"
            proxy_port = int(self._local_proxy.port)

        scheme = (self._proxy_details.scheme or "").lower()
        if scheme.startswith("socks"):
            proxy_type = socks.SOCKS4 if "4" in scheme else socks.SOCKS5
            original_socket = socket.socket
            socks.set_default_proxy(
                proxy_type,
                proxy_host,
                proxy_port,
                username=self._proxy_details.username,
                password=self._proxy_details.password,
            )
            socket.socket = socks.socksocket
            try:
                yield None
            finally:
                socket.socket = original_socket
        else:
            auth = ""
            if self._proxy_details.username:
                user = urllib.parse.quote(self._proxy_details.username)
                pwd = urllib.parse.quote(self._proxy_details.password or "")
                auth = f"{user}:{pwd}@"
            proxy_url = f"{scheme or 'http'}://{auth}{proxy_host}:{proxy_port}"
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
            )
            yield opener

    def _current_proxy_host_label(self) -> Optional[str]:
        """Return the active proxy host:port (respecting local bridge) for logging."""
        if not self._proxy_details or not self._proxy_details.host:
            return None
        proxy_host = self._proxy_details.host
        proxy_port = self._proxy_details.port
        if getattr(self, "_local_proxy", None) and getattr(self._local_proxy, "port", None):
            proxy_host = "127.0.0.1"
            proxy_port = self._local_proxy.port
        return f"{proxy_host}:{proxy_port}"

    def _fetch_country_via_proxy(self, timeout: int = 10) -> dict:
        """Try multiple public geo APIs (over the current proxy) to get country code."""

        def _open_with_proxy(opener, url: str):
            if opener:
                with opener.open(url, timeout=timeout) as resp:
                    return json.load(resp)
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return json.load(resp)

        last_error = None
        with self._geo_proxy_context() as opener:
            try:
                data = _open_with_proxy(opener, "https://ipwho.is/")
                return data
            except Exception as exc:
                last_error = str(exc)

            try:
                data = _open_with_proxy(
                    opener,
                    "http://ip-api.com/json/?fields=countryCode,status,message,timezone",
                )
                if data.get("status") == "success" and data.get("countryCode"):
                    response = {"success": True, "country_code": data.get("countryCode")}
                    if data.get("timezone"):
                        response["timezone"] = data.get("timezone")
                    return response
                return {"success": False, "details": data}
            except Exception as exc:
                last_error = str(exc)
        return {"success": False, "error": last_error or "unknown"}

    @staticmethod
    def _country_to_locale(country: str) -> str:
        """Map a two-letter country code to a browser locale string."""
        return country_to_locale(country)

    def _detect_browser_locale(self) -> str:
        """
        Detect locale for the browser using a public geo IP API. Priority:
        1) proxy geo lookup; 2) OS locale; 3) en-US.
        """
        proxy_locale = self._detect_proxy_locale()
        if proxy_locale:
            return proxy_locale

        os_locale, _ = locale.getdefaultlocale()
        if os_locale:
            return os_locale
        return "en-US"

    @staticmethod
    def _timezone_from_geo_data(geo_data: Optional[dict]) -> Optional[str]:
        """Extract timezone identifier from geo API payload."""
        if not isinstance(geo_data, dict):
            return None
        timezone_info = geo_data.get("timezone")
        if isinstance(timezone_info, dict):
            for key in ("id", "name", "tz"):
                tz_candidate = timezone_info.get(key)
                if tz_candidate:
                    return tz_candidate
            tz_candidate = timezone_info.get("utc")
            if tz_candidate:
                return tz_candidate
        elif isinstance(timezone_info, str) and timezone_info:
            return timezone_info

        for fallback_key in ("timezone_id", "time_zone"):
            tz_candidate = geo_data.get(fallback_key)
            if isinstance(tz_candidate, str) and tz_candidate:
                return tz_candidate
        return None

    def _detect_browser_timezone(self) -> Optional[str]:
        """Detect timezone id via geo IP lookup."""
        geo_data = self._fetch_country_via_proxy()
        timezone_id = self._timezone_from_geo_data(geo_data)
        host_label = self._current_proxy_host_label()
        if timezone_id:
            if host_label:
                self._proxy_logger.info("Timezone detected via proxy %s -> %s", host_label, timezone_id)
            else:
                self.logger.info("Timezone detected via geo lookup -> %s", timezone_id)
            return timezone_id

        if host_label:
            self._proxy_logger.error("Timezone not detected via proxy %s; payload: %s", host_label, geo_data)
        else:
            self.logger.warning("Timezone lookup failed via geo API: %s", geo_data)
        return None

    async def start(self):
        self._closed_notified = False
        self._process_exited_notified = False
        self._close_listener_attached = False
        if self.proxy and not self._proxy_config:
            msg = f"Proxy configured for {self.profile_name} but failed to parse; browser launch aborted."
            self.logger.error(msg)
            self._proxy_logger.error(msg)
            raise RuntimeError("Proxy parse failed; see logs/proxy.log for details.")

        if self._proxy_config:
            if not self._verify_proxy_connection():
                raise RuntimeError("Proxy verification failed; see logs/proxy.log for details.")
            if not self._detect_proxy_locale():
                msg = f"Proxy locale detection failed for {self.profile_name}; browser launch aborted."
                self.logger.error(msg)
                self._proxy_logger.error(msg)
                raise RuntimeError("Proxy locale detection failed; see logs/proxy.log for details.")

        launch_kwargs = self._build_launch_kwargs()
        self.logger.info("Launching Camoufox for %s with kwargs keys: %s", self.profile_name, str(launch_kwargs))
        self._camoufox_ctx = AsyncCamoufox(**launch_kwargs)

        use_persistent = launch_kwargs.get("persistent_context", False)
        camoufox_result = await self._camoufox_ctx.__aenter__()
        if use_persistent:
            self.context = camoufox_result
            self.browser = getattr(self.context, "browser", None)
        else:
            self.browser = camoufox_result
            self.context = await self.browser.new_context()
        if use_persistent and self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()
        self._attach_close_listeners()
        if self._process_exit_callbacks:
            self._start_process_watchdog()
        self.logger.info("Camoufox context started for %s", self.profile_name)
        self.page.set_default_navigation_timeout(60000)
        self.page.set_default_timeout(60000)
        self._notify_browser_ready()

    def _start_process_watchdog(self) -> None:
        """
        Best-effort watchdog that fires process-exit callbacks when the browser window/process exits.

        Uses a Windows process lookup by profile directory when possible. Falls back to no-op on other platforms.
        """
        if self._process_watchdog_started:
            return
        self._process_watchdog_started = True

        def worker() -> None:
            if not sys.platform.startswith("win"):
                return

            env = dict(os.environ)
            env["_CAMOUFLOW_PROFILE_DIR"] = str(self.user_data_dir)
            ps_exists = (
                "$target=$env:_CAMOUFLOW_PROFILE_DIR; "
                "$rx=[regex]::Escape($target); "
                "$p=Get-CimInstance Win32_Process | Where-Object { "
                "  $_.CommandLine -and $_.CommandLine -match $rx -and "
                "  $_.Name -notin @('node.exe','python.exe','pythonw.exe','powershell.exe') "
                "} | Select-Object -First 1; "
                "if($p){'1'} else {'0'}"
            )

            seen = False
            # Wait until the browser process appears; then wait until it disappears.
            while not getattr(self, "_process_exited_notified", False):
                try:
                    out = subprocess.check_output(
                        ["powershell", "-NoProfile", "-Command", ps_exists],
                        env=env,
                        stderr=subprocess.DEVNULL,
                        text=True,
                        encoding="utf-8",
                        errors="ignore",
                    )
                    exists = (out or "").strip() == "1"
                except Exception:
                    exists = False

                if exists:
                    seen = True
                elif seen:
                    break

                time.sleep(1.0)

            if not seen:
                return
            self._notify_process_exited()
            self._notify_browser_closed()

        threading.Thread(target=worker, daemon=True).start()

    async def close(self, force: bool = False):
        if self.keep_browser_open and self.browser and not force:
            self.logger.info("Keeping Camoufox session for %s open; force close when finished.", self.profile_name)
            return

        self.logger.info("Closing Camoufox resources for %s", self.profile_name)
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
        finally:
            if self._camoufox_ctx:
                await self._camoufox_ctx.__aexit__(None, None, None)
                self._camoufox_ctx = None
            if self._local_proxy:
                self._local_proxy.stop()
                self._local_proxy = None
            self.browser = None
            self.context = None
            self.page = None
            self._notify_process_exited()
            self._notify_browser_closed()
            self._ready_notified = False

    def add_process_exit_callback(self, callback: Callable[[], None]) -> None:
        if not callable(callback):
            return
        if self._process_exited_notified:
            try:
                callback()
            except Exception:
                pass
            return
        self._process_exit_callbacks.append(callback)
        if self.browser is not None or self.context is not None:
            self._start_process_watchdog()
    def add_close_callback(self, callback: Callable[[], None]) -> None:
        if not callable(callback):
            return
        if self._closed_notified:
            try:
                callback()
            except Exception:
                pass
            return
        self._close_callbacks.append(callback)

    def add_ready_callback(self, callback: Callable[[], None]) -> None:
        if callable(callback):
            if self._ready_notified:
                try:
                    callback()
                except Exception:
                    pass
            else:
                self._ready_callbacks.append(callback)

    def _notify_browser_closed(self) -> None:
        if self._closed_notified:
            return
        self._closed_notified = True
        try:
            self.logger.info("Browser closed detected for %s", self.profile_name)
        except Exception:
            pass
        for callback in list(self._close_callbacks):
            try:
                callback()
            except Exception:
                continue

    def _notify_process_exited(self) -> None:
        if self._process_exited_notified:
            return
        self._process_exited_notified = True
        for callback in list(self._process_exit_callbacks):
            try:
                callback()
            except Exception:
                continue

    def _notify_browser_ready(self) -> None:
        if self._ready_notified:
            return
        self._ready_notified = True
        for callback in list(self._ready_callbacks):
            try:
                callback()
            except Exception:
                continue
        self._ready_callbacks.clear()

    def _attach_close_listeners(self) -> None:
        if self._close_listener_attached:
            return

        def _safe_attach(target, event: str) -> None:
            if not target:
                return
            handler = getattr(target, "on", None)
            if callable(handler):
                try:
                    target.on(event, lambda *_args, **_kwargs: self._notify_browser_closed())
                except Exception:
                    pass

        _safe_attach(self.browser, "disconnected")
        _safe_attach(self.context, "close")
        page = getattr(self, "page", None)
        if page is not None:
            try:
                page.on("close", lambda *_args, **_kwargs: self._notify_browser_closed())
            except Exception:
                pass
        self._close_listener_attached = True
