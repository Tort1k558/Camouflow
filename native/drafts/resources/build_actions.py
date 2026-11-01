"""Read-only build-rule diagnostics; process names alone do not identify actions."""

import argparse
import codecs
import hashlib
import json
from pathlib import Path
import re


MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_LINE_BUFFER_BYTES = 64 * 1024


def classify_process(image: str, arguments: list[str] | None) -> str:
    if not isinstance(image, str) or not image or '\0' in image:
        raise ValueError('Expected an executable image name')
    if arguments is None:
        return 'unavailable'
    if (not isinstance(arguments, list) or len(arguments) > 4096
            or any(not isinstance(value, str) or '\0' in value for value in arguments)
            or sum(map(len, arguments)) > 32768):
        raise ValueError('Expected bounded, already parsed process arguments')
    image = image.replace('\\', '/').rsplit('/', 1)[-1].lower()
    lowered = [value.lower() for value in arguments]
    if image == 'lld-link.exe':
        if '/lib' in lowered or '-lib' in lowered:
            return 'archive'
        if any(value.startswith(('/out:', '-out:')) for value in lowered):
            return 'link'
        return 'link-unclassified'
    if image == 'clang-cl.exe':
        if '-cc1' in lowered or '-cc1as' in lowered:
            return 'compiler-frontend'
        if '/c' in lowered or '-c' in lowered:
            return 'compiler-driver'
        return 'compiler-unclassified'
    return 'other'


def read_configuration(path: Path) -> dict:
    if not path.is_absolute() or path != path.resolve() or not path.is_file():
        raise ValueError('Expected a canonical unlinked Ninja file')
    rules, pools = {}, {}
    current = None
    digest = hashlib.sha256()
    captured = 0
    before = path.stat()
    if before.st_size > MAX_FILE_BYTES:
        raise ValueError('Ninja file exceeds the diagnostic bound')
    with path.open('rb') as stream:
        while True:
            raw = stream.readline(MAX_LINE_BUFFER_BYTES)
            if not raw:
                break
            digest.update(raw)
            captured += len(raw)
            if captured > MAX_FILE_BYTES:
                raise ValueError('Ninja file exceeds the diagnostic bound')
            # GN interleaves rules and build edges. Skip long edge tails without
            # retaining them, but hash the entire file and resume at the next line.
            prefix = raw
            fragmented = not raw.endswith(b'\n') and len(raw) == MAX_LINE_BUFFER_BYTES
            while not raw.endswith(b'\n') and len(raw) == MAX_LINE_BUFFER_BYTES:
                raw = stream.readline(MAX_LINE_BUFFER_BYTES)
                digest.update(raw)
                captured += len(raw)
                if captured > MAX_FILE_BYTES:
                    raise ValueError('Ninja file exceeds the diagnostic bound')
            decoder = codecs.getincrementaldecoder('utf-8-sig')()
            line = decoder.decode(prefix, final=not fragmented).rstrip('\r\n')
            declaration = re.fullmatch(r'(rule|pool) ([A-Za-z0-9_.-]+)', line)
            if declaration:
                kind, name = declaration.groups()
                table = rules if kind == 'rule' else pools
                if name in table:
                    raise ValueError('Duplicate Ninja rule or pool')
                table[name] = None
                current = kind, name
            elif line and not line.startswith((' ', '#')):
                current = None
            elif current:
                kind, name = current
                if kind == 'rule' and line.startswith('  pool = '):
                    value = line.removeprefix('  pool = ')
                    if rules[name] is not None or not re.fullmatch(r'[A-Za-z0-9_.-]+', value):
                        raise ValueError('Unsupported or duplicate Ninja rule pool')
                    rules[name] = value
                elif kind == 'pool' and line.startswith('  depth = '):
                    value = line.removeprefix('  depth = ')
                    if pools[name] is not None or not value.isascii() or not value.isdecimal() or int(value) < 1:
                        raise ValueError('Unsupported or duplicate Ninja pool depth')
                    pools[name] = int(value)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or captured != after.st_size:
        raise ValueError('Ninja file changed during inspection')
    return dict(rules=rules, pools=pools, captured_bytes=captured,
                sha256=digest.hexdigest(), whole_file_hashed=True,
                maximum_line_buffer_bytes=MAX_LINE_BUFFER_BYTES)


def inspect(build_directory: Path) -> dict:
    if not build_directory.is_absolute() or build_directory != build_directory.resolve() or not build_directory.is_dir():
        raise ValueError('Expected a canonical build directory')
    root = read_configuration(build_directory / 'build.ninja')
    tools = read_configuration(build_directory / 'toolchain.ninja')
    required = ('link', 'solink', 'alink')
    if any(name not in tools['rules'] for name in required):
        raise ValueError('Expected Windows executable, DLL and archive rules')
    links = {name: tools['rules'][name] for name in ('link', 'solink')}
    configured = all(value is not None and root['pools'].get(value) == 1 for value in links.values())
    return dict(schema=1, configured_executable_and_dll_link_pool_depth_one=configured,
                executable_and_dll_pools=links, archive_pool=tools['rules']['alink'],
                root_configuration=root, toolchain_configuration=tools,
                scope='Generated Ninja rule configuration only; no runtime scheduling or action attribution proof',
                raw_lld_process_count_is_heavy_link_count=False,
                historical_two_linker_cause_confirmed=False, runtime_scheduling_verified=False,
                build_modified=False, production_admitted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-directory', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    report = args.report
    if (not report.is_absolute() or report != report.resolve() or report.drive.upper() != 'D:'
            or not report.parent.is_dir() or report.exists() or report.is_relative_to(args.build_directory)):
        parser.error('Use a fresh external D: report outside the inspected build directory')
    result = inspect(args.build_directory)
    with report.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key: value for key, value in result.items() if not key.endswith('_configuration')}))


if __name__ == '__main__':
    main()
