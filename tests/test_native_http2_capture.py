import io
import json

import pytest

from native.drafts.network import http2


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
