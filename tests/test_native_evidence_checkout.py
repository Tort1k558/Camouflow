import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_byte_bound_evidence_has_explicit_checkout_policy():
    paths = {
        'native/drafts/audio-context-ownership/packet.json',
        'native/drafts/audio-lifecycle-runtime/r7-observations.json',
        'native/drafts/scoped-patch-index-r8/packet.json',
    }
    for name in ('upstream-156-audio-r8', 'upstream-156-checkpoint-r12',
                 'upstream-156-checkpoint-r13', 'upstream-156-document-r15'):
        manifest = json.loads((ROOT / 'native/drafts' / name / 'manifest.json').read_bytes())
        paths.update(row['packet'] for row in manifest['extension_batch']['packets'])
    for name in ('scoped-patch-index', 'scoped-patch-index-r8'):
        directory = ROOT / 'native/drafts' / name
        packet = json.loads((directory / 'packet.json').read_bytes())
        paths.add((directory / 'check.py').relative_to(ROOT).as_posix())
        paths.update(packet['test_inputs_sha256'])
    raw = subprocess.check_output(['git', 'check-attr', '-z', 'text', 'eol', '--', *sorted(paths)],
                                  cwd=ROOT)
    fields = raw.decode('utf-8').rstrip('\0').split('\0')
    assert len(fields) == len(paths) * 6
    attributes = {}
    for index in range(0, len(fields), 3):
        path, attribute, value = fields[index:index + 3]
        attributes.setdefault(path, {})[attribute] = value
    for path in paths:
        data = (ROOT / path).read_bytes()
        policy = attributes[path]
        assert not data.startswith(b'\xef\xbb\xbf'), path
        if b'\r\n' in data:
            assert policy['text'] == 'unset', path
        else:
            assert policy == {'text': 'set', 'eol': 'lf'}, path
