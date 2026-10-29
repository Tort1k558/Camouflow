"""Owned TLS negotiation collector; no TLS impersonation or system trust changes."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ssl
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from app.core.native.configuration import NativeConfiguration
from app.core.native.runtime import NativeRuntime
from playwright.async_api import Error as PlaywrightError
from scripts.verify_native_worker_startup import browser_arguments

class Server(ThreadingHTTPServer):
    def get_request(self):
        connection, address = self.socket.accept()
        connection.settimeout(5)
        try:
            return self.tls.wrap_socket(connection, server_side=True), address
        except BaseException:
            connection.close()
            raise

class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_GET(self):
        body = b'<title>Owned TLS fixture</title><h1>Owned TLS fixture</h1>'
        owned = self.path.startswith('/owned?')
        if owned:
            self.server.report['requests'].append({'server': self.server.label, 'path': self.path,
                'tls_version': self.connection.version(), 'cipher': list(self.connection.cipher()),
                'alpn': self.connection.selected_alpn_protocol(), 'session_reused': self.connection.session_reused,
                'http_version': self.request_version, 'headers': {name: self.headers.get(name) for name in
                    ('User-Agent', 'Accept-Language', 'Sec-CH-UA', 'Sec-CH-UA-Platform', 'Sec-CH-UA-Mobile')}})
        self.send_response(200 if owned else 404)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        self.wfile.write(body)

    def log_message(self, *args):
        pass

@dataclass(frozen=True)
class Configuration(NativeConfiguration):
    owned_spki: str = ''

    def launch_arguments(self):
        if not isinstance(self.owned_spki, str):
            raise ValueError('One owned fixture key is required')
        decoded = base64.b64decode(self.owned_spki, validate=True)
        if len(decoded) != 32 or base64.b64encode(decoded).decode('ascii') != self.owned_spki:
            raise ValueError('One owned fixture key is required')
        return [*super().launch_arguments(), '--enable-automation', '--ignore-certificate-errors-spki-list=' + self.owned_spki]


def create_server(certificate: Path, private_key: Path, version: ssl.TLSVersion,
                  label: str, report: dict):
    if type(version) is not ssl.TLSVersion or version not in {ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3}:
        raise ValueError("Select an explicit owned TLS 1.2 or TLS 1.3 server")
    if label not in {"tls12", "tls13", "unmatched-key"}:
        raise ValueError("Unknown owned TLS case")
    if any(not path.is_absolute() or path != path.resolve() or not path.is_file()
           or path.drive.upper() != "D:" or path.is_relative_to(ROOT) for path in (certificate, private_key)):
        raise ValueError("Owned fixture certificate/key must be canonical files on D:")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = version
    context.maximum_version = version
    context.set_alpn_protocols(["http/1.1"])
    context.load_cert_chain(certificate, private_key)
    server = Server(("127.0.0.1", 0), Handler)
    server.tls, server.label, server.report = context, label, report
    return server


async def capture(executable: Path, owned: Path, pin: str, servers, report: dict, save) -> None:
    if len(servers) != 3 or {server.label for server in servers} != {"tls12", "tls13", "unmatched-key"}:
        raise ValueError("All three explicit owned TLS cases are required")
    report.update(cases=[], requests=[], passed=False, measurement_complete=False,
        ordinary_certificate_path_validation_verified=False, system_trust_store_changed=False,
        scope="Owned TLS 1.2/1.3 and HTTP/1.1 with one diagnostic SPKI allowlist plus unrelated-key rejection; not TLS spoofing, ordinary certificate validation or HTTP/2/3")
    runtime = NativeRuntime(owned / 'profile', executable, Configuration(owned_spki=pin))
    try:
        context = await runtime.start(headless=True)
        arguments = await browser_arguments(context)
        assert not any(argument.split('=', 1)[0] in {'--ignore-certificate-errors', '--allow-insecure-localhost'}
                       for argument in arguments)
        assert [arg for arg in arguments if arg.startswith('--ignore-certificate-errors-spki-list=')] == [
            '--ignore-certificate-errors-spki-list=' + pin]
        session = await context.browser.new_browser_cdp_session()
        try:
            version = await session.send('Browser.getVersion')
            assert version['revision'] == '@' + report['chromium_revision']
            assert version['product'] == 'Chrome/' + report['chromium_version']
        finally:
            await session.detach()
        allowed = {server.server_port for server in servers}

        async def route(request):
            url = urlsplit(request.request.url)
            if url.scheme == 'https' and url.hostname == '127.0.0.1' and url.port in allowed:
                await request.continue_()
            else:
                await request.abort('blockedbyclient')

        await context.route('**/*', route)
        page = context.pages[0]
        for index, server in enumerate(servers):
            row = {'name': server.label, 'passed': False}
            report['cases'].append(row)
            url = f'https://127.0.0.1:{server.server_port}/owned?case={index}'
            if server.label == 'unmatched-key':
                try:
                    await page.goto(url, timeout=15000)
                except PlaywrightError as error:
                    row['navigation_error'] = str(error)
                    assert 'ERR_CERT_AUTHORITY_INVALID' in str(error)
                    assert not any(request['server'] == server.label for request in report['requests'])
                else:
                    raise AssertionError('Unmatched self-signed key unexpectedly accepted')
            else:
                response = await page.goto(url, timeout=15000)
                assert response.status == 200 and await page.locator('h1').inner_text() == 'Owned TLS fixture'
                request = next(value for value in report['requests'] if value['path'] == f'/owned?case={index}')
                assert request['tls_version'] == ('TLSv1.3' if server.label == 'tls13' else 'TLSv1.2')
                assert request['alpn'] == 'http/1.1' and request['http_version'] == 'HTTP/1.1'
            row['passed'] = True
            save()
        report.update(passed=True, measurement_complete=True)
    finally:
        await runtime.close()
        report['runtime_resource_free'] = not runtime.has_resources

