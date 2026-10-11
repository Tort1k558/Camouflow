"""Keep MIDL name hashes consistent with the locale stored in the type library."""

import struct


def normalize_name_hashes(contents: bytes, hash_name) -> bytes:
    if len(contents) < 0x54 or contents[:8] != b'MSFT\x02\x00\x01\x00':
        raise ValueError('Unsupported MIDL type library header')
    locale, _, flags = struct.unpack_from('<III', contents, 0x0c)
    system = flags & 0x0f
    count, = struct.unpack_from('<I', contents, 0x20)
    directory = 0x54 + 4 * count
    directory_end = directory + 15 * 16
    if system > 3 or flags & 0x100 or directory_end > len(contents):
        raise ValueError('Unsupported MIDL type library layout')
    hash_offset, hash_length = struct.unpack_from('<II', contents, directory + 6 * 16)
    name_offset, name_length = struct.unpack_from('<II', contents, directory + 7 * 16)
    if (hash_length != 512 or min(hash_offset, name_offset) < directory_end
            or hash_offset + hash_length > len(contents)
            or name_offset + name_length > len(contents)
            or not (hash_offset + hash_length <= name_offset
                    or name_offset + name_length <= hash_offset)):
        raise ValueError('Invalid MIDL name table bounds')
    result = bytearray(contents)
    buckets = [0xffffffff] * (hash_length // 4)
    position = name_offset
    names = 0
    while position < name_offset + name_length:
        if position + 12 > name_offset + name_length:
            raise ValueError('Truncated MIDL name entry')
        length = result[position + 8]
        end = position + 12 + ((length + 3) & ~3)
        if end > name_offset + name_length:
            raise ValueError('Truncated MIDL name string')
        name = bytes(result[position + 12:position + 12 + length]).decode('ascii')
        if '\0' in name:
            raise ValueError('Embedded NUL in MIDL name')
        hashed = hash_name(system, locale, name) & 0xffff
        bucket = hashed % len(buckets)
        struct.pack_into('<I', result, position + 4, buckets[bucket])
        struct.pack_into('<H', result, position + 10, hashed)
        buckets[bucket] = position - name_offset
        position = end
        names += 1
    if names != struct.unpack_from('<I', contents, 0x30)[0]:
        raise ValueError('MIDL name count differs from its header')
    for index, entry in enumerate(buckets):
        struct.pack_into('<I', result, hash_offset + 4 * index, entry)
    return bytes(result)


def normalize_windows_name_hashes(contents: bytes) -> bytes:
    import ctypes

    function = ctypes.WinDLL('oleaut32').LHashValOfNameSys
    function.argtypes = [ctypes.c_int, ctypes.c_uint32, ctypes.c_wchar_p]
    function.restype = ctypes.c_uint32
    return normalize_name_hashes(contents, function)
