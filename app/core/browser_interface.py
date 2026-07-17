import asyncio
import locale
import logging
import os
import random
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from app.storage.db import (
    db_get_browser_engine,
    db_get_camoufox_defaults,
    db_get_cloakbrowser_defaults,
    profile_dir_for_email,
)

from .browser_launchers import (
    CamoufoxLaunchBuilder,
    CloakBrowserLaunchBuilder,
    load_or_create_cloakbrowser_seed,
    normalize_locale_token,
    split_setting_list,
)
from .browser_lifecycle import BrowserLifecycleManager
from .browser_proxy_service import BrowserProxyService
from .locale_mapping import country_to_locale
from .proxy_utils import LocalSocksProxyServer, parse_proxy


AsyncCamoufox = Any


def _import_camoufox():
    from camoufox import AsyncCamoufox as imported

    return imported


BROWSER_ENGINE_CAMOUFOX = "camoufox"
BROWSER_ENGINE_CLOAKBROWSER = "cloakbrowser"


def normalize_browser_engine(engine: Optional[str]) -> str:
    normalized = str(engine or "").strip().lower()
    if normalized in {BROWSER_ENGINE_CAMOUFOX, BROWSER_ENGINE_CLOAKBROWSER}:
        return normalized
    return BROWSER_ENGINE_CAMOUFOX


def cloakbrowser_profile_dir(profile_dir: Path) -> Path:
    return Path(profile_dir) / BROWSER_ENGINE_CLOAKBROWSER


class BrowserInterface:
    """Browser/proxy interface that starts Camoufox or CloakBrowser and exposes a Playwright page."""

    @staticmethod
    def _normalize_locale_token(value: str) -> str:
        return normalize_locale_token(value)

    def __init__(
        self,
        profile_name,
        proxy: str = "",
        keep_browser_open: bool = True,
        camoufox_settings: Optional[Dict[str, object]] = None,
        browser_engine: Optional[str] = None,
        browser_settings: Optional[Dict[str, object]] = None,
    ) -> None:
        self.profile_name = profile_name
        self.proxy = proxy
        self.keep_browser_open = keep_browser_open
        self.profile_root = profile_dir_for_email(self.profile_name)
        self.browser_engine = normalize_browser_engine(browser_engine or db_get_browser_engine())
        self.user_data_dir = self.profile_root
        if self.browser_engine == BROWSER_ENGINE_CLOAKBROWSER:
            self.user_data_dir = cloakbrowser_profile_dir(self.profile_root)
        os.makedirs(self.user_data_dir, exist_ok=True)

        self._browser_settings = browser_settings if browser_settings is not None else (camoufox_settings or {})
        self._camoufox_settings = self._browser_settings
        self._camoufox_defaults = db_get_camoufox_defaults()
        self._cloakbrowser_defaults = db_get_cloakbrowser_defaults()

        self.logger = logging.LoggerAdapter(logging.getLogger(__name__), {"profile": self.profile_name})
        self._proxy_logger = self._init_proxy_logger()

        self.browser = None
        self.context = None
        self.page = None
        self._camoufox_ctx: Optional[AsyncCamoufox] = None
        self._cloakbrowser_context = None
        self._proxy_config, self._proxy_details = parse_proxy(proxy, profile_name=self.profile_name)
        self._local_proxy: Optional[LocalSocksProxyServer] = None
        self._proxy_service = BrowserProxyService(
            profile_name=self.profile_name,
            proxy_config=self._proxy_config,
            proxy_details=self._proxy_details,
            proxy_logger=self._proxy_logger,
            logger=self.logger,
        )
        self._lifecycle = BrowserLifecycleManager(
            profile_name=self.profile_name,
            user_data_dir_provider=lambda: Path(self.user_data_dir),
            browser_provider=lambda: self.browser,
            context_provider=lambda: self.context,
            page_provider=lambda: self.page,
            logger=self.logger,
        )

        if proxy and not self._proxy_config:
            msg = f"Proxy string provided for {self.profile_name} but failed to parse; proxy disabled"
            self.logger.warning(msg)
            self._proxy_logger.warning(msg)

    def _init_proxy_logger(self) -> logging.LoggerAdapter:
        proxy_logger = logging.getLogger("proxy_log")
        if not proxy_logger.handlers:
            proxy_logger.setLevel(logging.INFO)
            log_path = os.path.join(os.getcwd(), "logs", "proxy.log")
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            handler = logging.FileHandler(log_path, encoding="utf-8")
            from app.utils.gui_logging import PROFILE_FILTER, ProfileFormatter

            fmt = ProfileFormatter("%(asctime)s %(levelname)s [%(profile)s] %(message)s")
            handler.setFormatter(fmt)
            handler.addFilter(PROFILE_FILTER)
            proxy_logger.addHandler(handler)
        proxy_logger.propagate = True
        return logging.LoggerAdapter(proxy_logger, {"profile": self.profile_name})

    def _build_launch_kwargs(self) -> Dict[str, object]:
        builder = CamoufoxLaunchBuilder(
            profile_name=self.profile_name,
            user_data_dir=Path(self.user_data_dir),
            browser_settings=self._camoufox_settings,
            defaults=self._camoufox_defaults,
            proxy_config=self._proxy_config,
            proxy_details=self._proxy_details,
            proxy_service=self._proxy_service,
            proxy_logger=self._proxy_logger,
            logger=self.logger,
            detect_browser_locale=self._detect_browser_locale,
        )
        try:
            return builder.build()
        finally:
            if builder.local_proxy:
                self._local_proxy = builder.local_proxy
                self._proxy_service.set_local_proxy(self._local_proxy)

    def _build_cloakbrowser_launch_kwargs(self) -> Dict[str, object]:
        builder = CloakBrowserLaunchBuilder(
            profile_root=Path(self.profile_root),
            defaults=self._cloakbrowser_defaults,
            browser_settings=self._browser_settings,
            proxy_config=self._proxy_config,
            detect_browser_locale=self._detect_browser_locale,
            detect_browser_timezone=self._detect_browser_timezone,
        )
        return builder.build()

    @staticmethod
    def _context_kwargs_from_settings(settings: Dict[str, object]) -> Dict[str, object]:
        kwargs: Dict[str, object] = {}
        headers = settings.get("extra_http_headers")
        if isinstance(headers, dict) and headers:
            kwargs["extra_http_headers"] = {str(k): str(v) for k, v in headers.items() if str(k).strip()}
        permissions = split_setting_list(settings.get("permissions"))
        if permissions:
            kwargs["permissions"] = permissions
        storage_state_path = str(settings.get("storage_state_path") or "").strip()
        if storage_state_path:
            kwargs["storage_state"] = storage_state_path
        for key in ("ignore_https_errors", "java_script_enabled", "bypass_csp", "accept_downloads"):
            if key in settings:
                kwargs[key] = bool(settings.get(key))
        return kwargs

    async def _apply_context_runtime_settings(self) -> None:
        if not self.context:
            return
        headers = self._browser_settings.get("extra_http_headers")
        if isinstance(headers, dict) and headers:
            try:
                await self.context.set_extra_http_headers({str(k): str(v) for k, v in headers.items() if str(k).strip()})
            except Exception:
                self.logger.warning("Cannot apply extra HTTP headers for %s", self.profile_name, exc_info=True)
        permissions = split_setting_list(self._browser_settings.get("permissions"))
        if permissions:
            try:
                await self.context.grant_permissions(permissions)
            except Exception:
                self.logger.warning("Cannot grant browser permissions for %s", self.profile_name, exc_info=True)

    def _probe_proxy_endpoint(self) -> bool:
        return self._proxy_service.probe_endpoint()

    def _verify_proxy_connection(self) -> bool:
        return self._proxy_service.verify_connection()

    def _detect_proxy_locale(self) -> Optional[str]:
        return self._proxy_service.detect_locale()

    async def _human_type(self, element, text: str, clear: bool = True) -> None:
        """Type text into an element character by character with small random delays."""
        if element is None:
            return
        humanize_raw = self._browser_settings.get("humanize", True)
        humanize_enabled = (
            humanize_raw
            if isinstance(humanize_raw, bool)
            else str(humanize_raw).lower() not in {"0", "false", "no", "off"}
        )
        if self.browser_engine == BROWSER_ENGINE_CLOAKBROWSER and humanize_enabled:
            if clear:
                await element.fill(text)
            else:
                await element.type(text)
            return
        if clear:
            try:
                await element.fill("")
            except Exception:
                pass
        for ch in text:
            await element.type(ch)
            await asyncio.sleep(random.uniform(0.05, 0.25))

    def _geo_proxy_context(self):
        return self._proxy_service.geo_proxy_context()

    def _current_proxy_host_label(self) -> Optional[str]:
        return self._proxy_service.current_host_label()

    def _fetch_country_via_proxy(self, timeout: int = 10) -> dict:
        return self._proxy_service.fetch_country(timeout=timeout)

    @staticmethod
    def _country_to_locale(country: str) -> str:
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
        return BrowserProxyService.timezone_from_geo_data(geo_data)

    def _detect_browser_timezone(self) -> Optional[str]:
        return self._proxy_service.detect_timezone()

    async def start(self):
        self._lifecycle.reset_for_start()
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

        if self.browser_engine == BROWSER_ENGINE_CLOAKBROWSER:
            await self._start_cloakbrowser()
        else:
            await self._start_camoufox()
        if getattr(self.context, "pages", None) and self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()
        await self._apply_context_runtime_settings()
        self._attach_close_listeners()
        if self._lifecycle.has_process_exit_callbacks():
            self._start_process_watchdog()
        self.logger.info("%s context started for %s", self.browser_engine, self.profile_name)
        self.page.set_default_navigation_timeout(60000)
        self.page.set_default_timeout(60000)
        self._notify_browser_ready()

    async def _start_camoufox(self) -> None:
        launch_kwargs = self._build_launch_kwargs()
        self.logger.info("Launching Camoufox for %s with kwargs keys: %s", self.profile_name, str(launch_kwargs))
        Camoufox = _import_camoufox()
        self._camoufox_ctx = Camoufox(**launch_kwargs)

        use_persistent = launch_kwargs.get("persistent_context", False)
        camoufox_result = await self._camoufox_ctx.__aenter__()
        if use_persistent:
            self.context = camoufox_result
            self.browser = getattr(self.context, "browser", None)
        else:
            self.browser = camoufox_result
            self.context = await self.browser.new_context(**self._context_kwargs_from_settings(self._browser_settings))

    async def _start_cloakbrowser(self) -> None:
        try:
            from cloakbrowser import launch_async, launch_persistent_context_async
        except Exception as exc:
            raise RuntimeError("CloakBrowser is not installed. Run: pip install -r requirements.txt") from exc

        merged = dict(self._cloakbrowser_defaults or {})
        merged.update({k: v for k, v in (self._browser_settings or {}).items() if v is not None})
        launch_kwargs = self._build_cloakbrowser_launch_kwargs()
        use_persistent = bool(merged.get("persistent_context", True))
        self.logger.info(
            "Launching CloakBrowser for %s with kwargs keys: %s",
            self.profile_name,
            str(launch_kwargs),
        )
        try:
            context_kwargs = launch_kwargs.pop("context_kwargs", {})
            if not isinstance(context_kwargs, dict):
                context_kwargs = {}
            if use_persistent:
                persistent_kwargs = dict(launch_kwargs)
                persistent_kwargs.update(context_kwargs)
                self.context = await launch_persistent_context_async(str(self.user_data_dir), **persistent_kwargs)
                self._cloakbrowser_context = self.context
                self.browser = getattr(self.context, "browser", None)
            else:
                launch_only_kwargs = dict(launch_kwargs)
                launch_only_kwargs.pop("viewport", None)
                user_agent_value = launch_only_kwargs.pop("user_agent", None)
                color_scheme_value = launch_only_kwargs.pop("color_scheme", None)
                self.browser = await launch_async(**launch_only_kwargs)
                context_kwargs = dict(context_kwargs)
                viewport = launch_kwargs.get("viewport")
                if isinstance(viewport, dict):
                    context_kwargs["viewport"] = viewport
                locale_value = launch_kwargs.get("locale")
                timezone_value = launch_kwargs.get("timezone")
                if locale_value:
                    context_kwargs["locale"] = locale_value
                if timezone_value:
                    context_kwargs["timezone_id"] = timezone_value
                if user_agent_value:
                    context_kwargs["user_agent"] = user_agent_value
                if color_scheme_value:
                    context_kwargs["color_scheme"] = color_scheme_value
                self.context = await self.browser.new_context(**context_kwargs)
        except Exception as exc:
            self.logger.exception("CloakBrowser start failed for %s", self.profile_name)
            raise RuntimeError(f"CloakBrowser start failed: {exc}") from exc

    def _start_process_watchdog(self) -> None:
        self._lifecycle.start_process_watchdog()

    async def close(self, force: bool = False):
        if self.keep_browser_open and (self.browser or self.context) and not force:
            self.logger.info(
                "Keeping %s session for %s open; force close when finished.",
                self.browser_engine,
                self.profile_name,
            )
            return

        self.logger.info("Closing %s resources for %s", self.browser_engine, self.profile_name)
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
        finally:
            if self._camoufox_ctx:
                await self._camoufox_ctx.__aexit__(None, None, None)
                self._camoufox_ctx = None
            if self.browser_engine == BROWSER_ENGINE_CLOAKBROWSER and self.browser:
                try:
                    await self.browser.close()
                except Exception:
                    pass
            if self._local_proxy:
                self._local_proxy.stop()
                self._local_proxy = None
                self._proxy_service.set_local_proxy(None)
            self.browser = None
            self.context = None
            self.page = None
            self._notify_process_exited()
            self._notify_browser_closed()
            self._lifecycle.reset_ready()

    def add_process_exit_callback(self, callback: Callable[[], None]) -> None:
        self._lifecycle.add_process_exit_callback(callback)

    def add_close_callback(self, callback: Callable[[], None]) -> None:
        self._lifecycle.add_close_callback(callback)

    def add_ready_callback(self, callback: Callable[[], None]) -> None:
        self._lifecycle.add_ready_callback(callback)

    def _notify_browser_closed(self) -> None:
        self._lifecycle.notify_browser_closed()

    def _notify_process_exited(self) -> None:
        self._lifecycle.notify_process_exited()

    def _notify_browser_ready(self) -> None:
        self._lifecycle.notify_browser_ready()

    def _attach_close_listeners(self) -> None:
        self._lifecycle.attach_close_listeners()
