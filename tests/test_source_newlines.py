import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'native/drafts/environment/historical-source-newlines.json'


def test_measured_mixed_endings_reconstruct_exact_observation_inputs(historical_source_newlines):
    assert set(historical_source_newlines) == {
        'app/main.py', 'app/services/cloud_sync.py', 'app/services/scenario_debug.py',
        'app/services/scenario_worker.py', 'app/ui/bridge/app_state.py',
        'app/ui/scenario_debugger_window.py',
    }
    for name, record in historical_source_newlines.items():
        source = record['measured_bytes']
        assert 0 < source.count(b'\r\n') < source.count(b'\n')
        assert hashlib.sha256(source).hexdigest() == record['measured_sha256']
        assert hashlib.sha256(source.replace(b'\r\n', b'\n')).hexdigest() == record['canonical_lf_sha256']
        assert record['measured_sha256'] != record['canonical_lf_sha256']
        assert record['bound_records']
        for relative in record['bound_records']:
            observation = json.loads((ROOT / relative).read_bytes())
            bindings = [value for key, value in observation.items()
                        if key.endswith('source_sha256') and isinstance(value, dict)]
            assert any(value.get(name) == record['measured_sha256'] for value in bindings), relative


def test_source_bound_files_have_explicit_lf_checkout_rules():
    sources = json.loads(MANIFEST.read_bytes())['lf_checkout_sources']
    assert len(sources) == len(set(sources)) == 80
    result = subprocess.run(['git', 'check-attr', 'text', 'eol', '--', *sources],
                            cwd=ROOT, check=True, capture_output=True, text=True, timeout=15)
    rows = result.stdout.splitlines()
    assert len(rows) == len(sources) * 2
    for name in sources:
        assert name + ': text: set' in rows
        assert name + ': eol: lf' in rows
