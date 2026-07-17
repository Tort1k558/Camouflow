import json
import socket
import urllib.parse
import urllib.request
from contextlib import contextmanager
from typing import Dict, Optional

import socks

from .locale_mapping import country_to_locale
from .proxy_utils import LocalSocksProxyServer, ProxyDetails


class BrowserProxyService:
    """Proxy verification and geo detection for a browser profile."""

    def __init__(
        self,
        profile_name: str,
        proxy_config: Optional[Dict[str, str]],
        proxy_details: Optional[ProxyDetails],
        proxy_logger,
        logger,
    ) -> None:
        self.profile_name = profile_name
        self.proxy_config = proxy_config
        self.proxy_details = proxy_details
        self.proxy_logger = proxy_logger
        self.logger = logger
        self.local_proxy: Optional[LocalSocksProxyServer] = None

    def set_local_proxy(self, local_proxy: Optional[LocalSocksProxyServer]) -> None:
        self.local_proxy = local_proxy

    def current_host_label(self) -> Optional[str]:
        """Return the active proxy host:port (respecting local bridge) for logging."""
        if not self.proxy_details or not self.proxy_details.host:
            return None
        proxy_host = self.proxy_details.host
        proxy_port = self.proxy_details.port
        if self.local_proxy and self.local_proxy.port:
            proxy_host = "127.0.0.1"
            proxy_port = self.local_proxy.port
        return f"{proxy_host}:{proxy_port}"

    def probe_endpoint(self) -> bool:
        """Quick TCP probe to avoid long browser waits when the proxy is unreachable."""
        if not self.proxy_details:
            return True
        try:
            with socket.create_connection((self.proxy_details.host, int(self.proxy_details.port)), timeout=8):
                return True
        except Exception as exc:
            self.proxy_logger.error(
                "Proxy TCP probe failed for %s: %s:%s - %s",
                self.profile_name,
                self.proxy_details.host,
                self.proxy_details.port,
                exc,
            )
            return False

    def verify_connection(self) -> bool:
        """Verify that configured proxy is reachable and resolves to a country."""
        if not self.proxy_config:
            return True
        if not self.proxy_details:
            self.proxy_logger.error("Proxy verification failed for %s: missing parsed details.", self.profile_name)
            return False

        host_label = f"{self.proxy_details.host}:{self.proxy_details.port}"
        if not self.probe_endpoint():
            self.proxy_logger.error("Proxy verification failed for %s (unreachable %s).", self.profile_name, host_label)
            return False

        geo_response = self.fetch_country()
        if geo_response and geo_response.get("country_code"):
            self.proxy_logger.info(
                "Proxy verification succeeded for %s (%s -> %s).",
                self.profile_name,
                host_label,
                geo_response.get("country_code"),
            )
            return True

        self.proxy_logger.error(
            "Proxy verification failed for %s (%s). Details: %s",
            self.profile_name,
            host_label,
            geo_response,
        )
        return False

    def detect_locale(self) -> Optional[str]:
        """Detect locale strictly via the configured proxy."""
        if not self.proxy_config:
            return None
        host_label = self.current_host_label()
        if not host_label:
            return None
        data = self.fetch_country()
        if data and data.get("country_code"):
            locale_str = country_to_locale(data.get("country_code"))
            self.proxy_logger.info("Locale detected via proxy %s -> %s", host_label, locale_str)
            return locale_str
        self.proxy_logger.error("Locale not detected via proxy %s; payload: %s", host_label, data)
        return None

    def detect_timezone(self) -> Optional[str]:
        """Detect timezone id via geo IP lookup."""
        geo_data = self.fetch_country()
        timezone_id = self.timezone_from_geo_data(geo_data)
        host_label = self.current_host_label()
        if timezone_id:
            if host_label:
                self.proxy_logger.info("Timezone detected via proxy %s -> %s", host_label, timezone_id)
            else:
                self.logger.info("Timezone detected via geo lookup -> %s", timezone_id)
            return timezone_id

        if host_label:
            self.proxy_logger.error("Timezone not detected via proxy %s; payload: %s", host_label, geo_data)
        else:
            self.logger.warning("Timezone lookup failed via geo API: %s", geo_data)
        return None

    @staticmethod
    def timezone_from_geo_data(geo_data: Optional[dict]) -> Optional[str]:
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

    def fetch_country(self, timeout: int = 10) -> dict:
        """Try multiple public geo APIs (over the current proxy) to get country code."""

        def _open_with_proxy(opener, url: str):
            if opener:
                with opener.open(url, timeout=timeout) as resp:
                    return json.load(resp)
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return json.load(resp)

        last_error = None
        with self.geo_proxy_context() as opener:
            try:
                return _open_with_proxy(opener, "https://ipwho.is/")
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

    @contextmanager
    def geo_proxy_context(self):
        """Wrap geo IP requests so they always go through the current proxy."""
        if not self.proxy_details or not self.proxy_details.host:
            yield None
            return

        proxy_host = self.proxy_details.host
        proxy_port = int(self.proxy_details.port)
        if self.local_proxy and self.local_proxy.port:
            proxy_host = "127.0.0.1"
            proxy_port = int(self.local_proxy.port)

        scheme = (self.proxy_details.scheme or "").lower()
        if scheme.startswith("socks"):
            proxy_type = socks.SOCKS4 if "4" in scheme else socks.SOCKS5
            original_socket = socket.socket
            socks.set_default_proxy(
                proxy_type,
                proxy_host,
                proxy_port,
                username=self.proxy_details.username,
                password=self.proxy_details.password,
            )
            socket.socket = socks.socksocket
            try:
                yield None
            finally:
                socket.socket = original_socket
        else:
            auth = ""
            if self.proxy_details.username:
                user = urllib.parse.quote(self.proxy_details.username)
                pwd = urllib.parse.quote(self.proxy_details.password or "")
                auth = f"{user}:{pwd}@"
            proxy_url = f"{scheme or 'http'}://{auth}{proxy_host}:{proxy_port}"
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
            )
            yield opener
