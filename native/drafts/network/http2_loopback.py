"""Owned TLS 1.3/h2 preface capture; deliberately does not serve an HTTP response."""

from socketserver import BaseRequestHandler
import ssl

from . import http2, negotiation


class Handler(BaseRequestHandler):
    def handle(self):
        row = {
            'passed': False,
            'tls_version': self.request.version(),
            'cipher': list(self.request.cipher()),
            'alpn': self.request.selected_alpn_protocol(),
            'session_reused': self.request.session_reused,
            'http_response_verified': False,
        }
        self.server.report['http2_captures'].append(row)
        try:
            if row['tls_version'] != 'TLSv1.3' or row['alpn'] != 'h2':
                raise http2.HTTP2CaptureError('The owned connection did not negotiate TLS 1.3 and h2')
            self.request.sendall(http2.SERVER_PREFACE)
            row['initial_connection'] = http2.read_initial_connection(self.request)
            row['passed'] = True
        except (OSError, http2.HTTP2CaptureError) as error:
            row.update(error_type=type(error).__name__, error=str(error))


def create_server(certificate, private_key, report):
    """Reuse canonical D: key/path guards and bounded loopback TLS acceptance."""
    server = negotiation.create_server(certificate, private_key, ssl.TLSVersion.TLSv1_3, 'tls13', report)
    try:
        server.RequestHandlerClass = Handler
        server.tls.set_alpn_protocols(['h2'])
        report.setdefault('http2_captures', [])
        return server
    except BaseException:
        server.server_close()
        raise
