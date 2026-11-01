import io
import json
from types import SimpleNamespace

import pytest

from native.drafts.network import http2
from native.drafts.network import http2_loopback
from native.drafts.network import http2_response


def frame(kind, payload=b'', *, stream=0, flags=0):
    return len(payload).to_bytes(3, 'big') + bytes((kind, flags)) + stream.to_bytes(4, 'big') + payload


class FragmentedSocket:
    def __init__(self, data):
        self.input = io.BytesIO(data)

    def recv(self, length):
        return self.input.read(min(length, 3))


def capture(*frames):
    return http2.read_initial_connection(FragmentedSocket(http2.PREFACE + b''.join(frames)))


def test_initial_http2_records_order_duplicates_and_unknown_settings_without_headers():
    settings = b'\x00\x01\x00\x01\x00\x00\x00\x01\x00\x00\x10\x00\xfa\xfa\x00\x00\x00\x07'
    result = capture(frame(4, settings), frame(8, b'\x80\x00\x00\x01'),
                     frame(250, b'private extension contents', flags=128),
                     frame(1, b'cookies and URL must not be returned', stream=1, flags=5))
    assert [row['type'] for row in result['frames']] == [4, 8, 250, 1]
    assert result['frames'][0]['settings'] == [
        {'identifier': 1, 'value': 65536}, {'identifier': 1, 'value': 4096},
        {'identifier': 64250, 'value': 7}]
    assert result['frames'][1]['window_increment'] == 1
    assert result['frames'][3]['end_headers'] and result['frames'][3]['end_stream']
    assert not result['header_block_decoded'] and not result['http_response_verified']
    assert 'private' not in json.dumps(result) and 'cookies' not in json.dumps(result)


def test_initial_http2_priority_and_padding_are_metadata_not_hpack_validation():
    result = capture(frame(4), frame(2, b'\x80\x00\x00\x00\xff', stream=3),
                     frame(1, b'\x02\x00\x00\x00\x00\x00abc\x00\x00', stream=1, flags=40))
    assert result['frames'][1]['priority'] == {'exclusive': True, 'dependency': 0, 'weight': 256}
    assert result['frames'][2]['header_block_bytes'] == 3
    assert not result['frames'][2]['end_headers']


@pytest.mark.parametrize('invalid', [frame(4, flags=1), frame(4, stream=1), frame(8, b'1234'), frame(1, stream=1)])
def test_initial_http2_requires_first_non_ack_settings(invalid):
    with pytest.raises(http2.HTTP2CaptureError, match='first client frame'):
        capture(invalid)


@pytest.mark.parametrize('invalid', [
    frame(4, b'bad'), frame(4, b'123456', flags=1), frame(4, stream=1),
    frame(4, b'\x00\x02\x00\x00\x00\x02'),
    frame(4, b'\x00\x04\x80\x00\x00\x00'),
    frame(4, b'\x00\x05\x00\x00\x00\x00'),
    frame(4, b'\x00\x05\x01\x00\x00\x00'),
    frame(8), frame(8, b'\x80\x00\x00\x00'), frame(2, b'12345'),
    frame(2, b'1234', stream=1), frame(2, b'\x00\x00\x00\x01\x00', stream=1),
    frame(6, b'12345678', stream=1), frame(6), frame(1), frame(1, stream=2),
    frame(1, stream=1, flags=8), frame(1, b'\x05x', stream=1, flags=8),
    frame(1, b'1234', stream=1, flags=32),
    frame(1, b'\x00\x00\x00\x01\x00', stream=1, flags=32),
    *[frame(kind) for kind in (0, 3, 5, 7, 9)],
])
def test_initial_http2_rejects_malformed_control_and_request_frames(invalid):
    with pytest.raises(http2.HTTP2CaptureError):
        capture(frame(4), invalid)


def test_initial_http2_ignores_reserved_stream_bit_and_preserves_unknown_flags():
    result = capture(frame(4, stream=0x80000000, flags=128),
                     frame(4, flags=1), frame(6, b'12345678'), frame(1, stream=0x80000001))
    assert result['frames'][0]['stream'] == 0
    assert result['frames'][0]['flags'] == 128
    assert result['frames'][-1]['stream'] == 1


@pytest.mark.parametrize('cut', [0, 1, 23, 24, 25, 32, 33, 37, 42])
def test_initial_http2_rejects_truncated_streams(cut):
    data = http2.PREFACE + frame(4) + frame(1, b'x', stream=1)
    with pytest.raises(http2.HTTP2CaptureError, match='Truncated'):
        http2.read_initial_connection(FragmentedSocket(data[:cut]))


def test_initial_http2_bounds_frame_size_frame_count_and_total_bytes():
    with pytest.raises(http2.HTTP2CaptureError, match='maximum frame size'):
        capture(frame(4), frame(250, bytes(16385)))
    with pytest.raises(http2.HTTP2CaptureError, match='frame-count bound'):
        capture(frame(4), *[frame(250) for _ in range(http2.MAX_FRAMES)])
    with pytest.raises(http2.HTTP2CaptureError, match='byte bound'):
        capture(frame(4), *[frame(250, bytes(16384)) for _ in range(4)])


def test_initial_http2_rejects_wrong_preface_and_propagates_socket_timeout():
    with pytest.raises(http2.HTTP2CaptureError, match='preface'):
        http2.read_initial_connection(FragmentedSocket(b'x' * len(http2.PREFACE)))

    class TimedOutSocket:
        def recv(self, length):
            raise TimeoutError('owned deadline')

    with pytest.raises(TimeoutError, match='owned deadline'):
        http2.read_initial_connection(TimedOutSocket())


class TLSSocket(FragmentedSocket):
    session_reused = False

    def __init__(self, data, alpn='h2'):
        super().__init__(data)
        self.alpn = alpn
        self.sent = []

    def version(self):
        return 'TLSv1.3'

    def selected_alpn_protocol(self):
        return self.alpn

    def cipher(self):
        return ('TLS_AES_256_GCM_SHA384', 'TLSv1.3', 256)

    def sendall(self, value):
        self.sent.append(value)


def test_owned_http2_handler_reports_negotiation_and_preface_not_a_response():
    connection = TLSSocket(http2.PREFACE + frame(4) + frame(1, b'opaque', stream=1, flags=5))
    server = SimpleNamespace(report={'http2_captures': []})
    http2_loopback.Handler(connection, ('127.0.0.1', 12345), server)
    row, = server.report['http2_captures']
    assert row['passed'] and row['tls_version'] == 'TLSv1.3' and row['alpn'] == 'h2'
    assert not row['http_response_verified']
    assert connection.sent == [http2.SERVER_PREFACE]
    assert row['initial_connection']['frames'][-1]['header_block_bytes'] == 6


@pytest.mark.parametrize('alpn', [None, 'http/1.1'])
def test_owned_http2_handler_never_sends_http2_when_alpn_does_not_match(alpn):
    connection = TLSSocket(b'', alpn=alpn)
    server = SimpleNamespace(report={'http2_captures': []})
    http2_loopback.Handler(connection, ('127.0.0.1', 12345), server)
    row, = server.report['http2_captures']
    assert not row['passed'] and row['error_type'] == 'HTTP2CaptureError'
    assert connection.sent == []


def test_owned_http2_handler_retains_truncation_as_failure():
    connection = TLSSocket(http2.PREFACE + frame(4))
    server = SimpleNamespace(report={'http2_captures': []})
    http2_loopback.Handler(connection, ('127.0.0.1', 12345), server)
    row, = server.report['http2_captures']
    assert not row['passed'] and 'Truncated' in row['error']


def test_owned_http2_server_reuses_explicit_tls_and_canonical_key_guards(monkeypatch):
    import ssl

    calls = []
    tls = SimpleNamespace(set_alpn_protocols=lambda values: calls.append(values))
    server = SimpleNamespace(tls=tls)

    def create(certificate, key, version, label, report):
        assert (certificate, key, version, label) == ('certificate', 'key', ssl.TLSVersion.TLSv1_3, 'tls13')
        return server

    monkeypatch.setattr(http2_loopback.negotiation, 'create_server', create)
    report = {}
    assert http2_loopback.create_server('certificate', 'key', report) is server
    assert server.RequestHandlerClass is http2_loopback.Handler
    assert calls == [['h2']] and report == {'http2_captures': []}


class RequestEvent:
    headers = [(':method', 'GET'), (':path', '/owned'), (':scheme', 'https')]
    stream_id = 1


class Protocol:
    def __init__(self):
        self.sent = []

    def initiate_connection(self):
        pass

    def data_to_send(self):
        return http2.SERVER_PREFACE

    def receive_data(self, data):
        assert data.startswith(http2.PREFACE)
        return [RequestEvent()]

    def send_headers(self, stream, headers):
        assert stream == 1 and dict(headers)[':status'] == '200'
        self.sent.append(headers)

    def send_data(self, stream, body, end_stream):
        assert stream == 1 and end_stream is True and b'Owned h2 response' in body
        self.sent.append(body)


def response_capture(data, alpn='h2', protocol=None):
    server = SimpleNamespace(report={'http2_captures': []},
                             protocol_factory=lambda: protocol or Protocol(), request_event_type=RequestEvent)
    http2_response.Handler(TLSSocket(data, alpn=alpn), ('127.0.0.1', 12345), server)
    row, = server.report['http2_captures']
    return row


def test_owned_http2_response_validates_request_and_reports_bytes_without_header_contents():
    data = http2.PREFACE + frame(4) + frame(1, b'opaque', stream=1, flags=5)
    row = response_capture(data)
    assert row['passed'] and row['http_response_sent'] and row['request_headers_validated']
    assert row['outcome'] == 'response-sent' and row['received_application_bytes'] == len(data)
    assert 'opaque' not in json.dumps(row)


def test_owned_http2_empty_connection_is_not_a_successful_request_capture():
    row = response_capture(b'')
    assert not row['passed'] and not row['http_response_sent']
    assert row['outcome'] == 'peer-closed-without-application-data'
    assert row['received_application_bytes'] == 0


@pytest.mark.parametrize('data', [b'x', b'x' * 24, http2.PREFACE, http2.PREFACE + frame(4)])
def test_owned_http2_partial_or_malformed_application_data_never_becomes_an_empty_connection(data):
    row = response_capture(data)
    assert not row['passed'] and row['outcome'] == 'failed'
    assert row['received_application_bytes'] > 0


def test_owned_http2_response_rejects_wrong_alpn_without_claiming_an_empty_connection():
    row = response_capture(b'', alpn='http/1.1')
    assert not row['passed'] and row['outcome'] == 'failed'


def test_owned_http2_response_rejects_an_unowned_path():
    class WrongRequest(RequestEvent):
        headers = [(':method', 'GET'), (':path', '/other'), (':scheme', 'https')]

    class WrongPath(Protocol):
        def receive_data(self, data):
            return [WrongRequest()]

    row = response_capture(http2.PREFACE + frame(4) + frame(1, stream=1), protocol=WrongPath())
    assert not row['passed'] and row['outcome'] == 'failed'
    assert 'explicit HTTPS GET' in row['error']


def test_owned_http2_stock_calibration_is_bound_and_does_not_admit_glint():
    import hashlib
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / 'native/drafts/network/stock-http2-observations.json').read_bytes())
    for name in ('passed', 'measurement_complete', 'http_response_verified', 'resources_closed',
                 'postguards_passed', 'ephemeral_private_key_removed', 'request_headers_validated_by_h2'):
        assert record[name] is True
    assert record['fresh_profile_count'] == record['successful_response_profiles'] == 3
    assert record['completed_request_connections'] == 3
    assert record['empty_connections_not_counted_as_requests'] == 2
    assert record['incomplete_application_data_connections'] == 0
    assert record['next_hop_protocols'] == ['h2'] * 3
    assert record['all_completed_selected_control_shapes_equal'] is True
    assert [frame['type'] for frame in record['selected_control_shape']] == [4, 8, 1]
    for name in ('glint_r8_measured', 'initial_parser_decodes_headers', 'http3_verified',
                 'session_resumption_verified', 'ja3_ja4_parity_verified', 'cross_platform_identity_verified',
                 'global_ignore_certificate_errors_used', 'certificate_store_changed',
                 'ordinary_certificate_path_validation_verified', 'privacy_admitted', 'production_admitted'):
        assert record[name] is False
    for name, digest in record['source_sha256'].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    assert hashlib.sha256((root / record['stock_control_file']).read_bytes()).hexdigest() == record['stock_control_sha256']
    assert len(record['retained_failed_attempts']) == 2
    assert all(row['passed'] is False and row['postguards_passed'] for row in record['retained_failed_attempts'])


def test_owned_http2_matched_r8_controls_do_not_claim_tls_or_platform_parity():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / 'native/drafts/network/matched-r8-http2-observations.json').read_bytes())
    stock = json.loads((root / 'native/drafts/network/stock-http2-observations.json').read_bytes())
    build = json.loads((root / 'native/drafts/upstream-156-audio-r8/windows-build.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['fresh_profile_count'] == 9
    assert [row['name'] for row in record['phases']] == ['glint-before', 'stock-control', 'glint-after']
    for row in record['phases']:
        expected = stock['stock_core_sha256'] if row['name'] == 'stock-control' else build['runtime_core_sha256_measured']
        assert row['passed'] and row['completed_request_connections'] == 3
        assert row['runtime_core_sha256_measured'] == expected
    assert record['selected_control_shape'] == stock['selected_control_shape']
    assert record['all_completed_selected_control_shapes_equal']
    assert record['fixture_threads_closed'] and record['ephemeral_private_keys_removed']
    assert record['diagnostic_spki_allowlist_used'] and record['earlier_failed_baseline_preserved']
    for name in ('protected_profile_policy_measured', 'fresh_complete_baseline_suite_verified',
                 'tls_fingerprint_parity_verified', 'ja3_ja4_verified', 'cross_platform_identity_verified',
                 'ordinary_certificate_path_validation_verified', 'global_ignore_certificate_errors_used',
                 'certificate_store_changed', 'privacy_admitted', 'production_admitted'):
        assert record[name] is False
