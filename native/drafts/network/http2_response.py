"""Owned GET fixture using an explicit external hyper-h2 diagnostic tool stage."""

from socketserver import BaseRequestHandler

from . import http2, http2_loopback


class _ObservedConnection:
    def __init__(self, connection):
        self.connection = connection
        self.initial = bytearray()

    def recv(self, length):
        value = self.connection.recv(length)
        self.initial.extend(value)
        return value


class Handler(BaseRequestHandler):
    def handle(self):
        row = dict(passed=False, outcome='failed', tls_version=self.request.version(),
                   alpn=self.request.selected_alpn_protocol(), cipher=list(self.request.cipher()),
                   http_response_sent=False)
        self.server.report['http2_captures'].append(row)
        observed = _ObservedConnection(self.request)
        try:
            if row['tls_version'] != 'TLSv1.3' or row['alpn'] != 'h2':
                raise http2.HTTP2CaptureError('The owned connection did not negotiate TLS 1.3 and h2')
            protocol = self.server.protocol_factory()
            protocol.initiate_connection()
            self.request.sendall(protocol.data_to_send())
            row['initial_connection'] = http2.read_initial_connection(observed)
            requests = [event for event in protocol.receive_data(bytes(observed.initial))
                        if isinstance(event, self.server.request_event_type)]
            if len(requests) != 1:
                raise http2.HTTP2CaptureError('Expected one complete request header block')
            headers = dict(requests[0].headers)
            if headers.get(':method') != 'GET' or headers.get(':path') != '/owned' or headers.get(':scheme') != 'https':
                raise http2.HTTP2CaptureError('The owned fixture accepts only its explicit HTTPS GET path')
            stream = requests[0].stream_id
            body = b'<title>Owned h2 response</title><link rel="icon" href="data:,"><h1>Owned h2 response</h1>'
            protocol.send_headers(stream, [(':status', '200'), ('content-type', 'text/html; charset=utf-8'),
                                           ('content-length', str(len(body)))])
            protocol.send_data(stream, body, end_stream=True)
            self.request.sendall(protocol.data_to_send())
            row.update(passed=True, outcome='response-sent', http_response_sent=True,
                       request_headers_validated=True)
        except Exception as error:
            row.update(error_type=type(error).__name__, error=str(error))
            if (isinstance(error, http2.HTTP2CaptureError) and not observed.initial
                    and str(error) == 'Truncated initial HTTP/2 connection'):
                row['outcome'] = 'peer-closed-without-application-data'
        finally:
            row['received_application_bytes'] = len(observed.initial)


def create_server(certificate, private_key, report):
    # The fixture tool stage is explicit; never install or substitute a protocol stack.
    from h2.config import H2Configuration
    from h2.connection import H2Connection
    from h2.events import RequestReceived

    server = http2_loopback.create_server(certificate, private_key, report)
    server.RequestHandlerClass = Handler
    server.protocol_factory = lambda: H2Connection(config=H2Configuration(client_side=False, header_encoding='utf-8'))
    server.request_event_type = RequestReceived
    return server
