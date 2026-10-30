import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/environment'
SOURCE = ROOT / 'scripts/verify_native_canvas.py'
FRAMES = {'same_origin_frame': 'owned-frame', 'cross_origin_frame': 'cross-origin',
          'about_blank_frame': 'owned-about-blank', 'srcdoc_frame': 'owned-srcdoc'}


@pytest.fixture
def draft(tmp_path):
    path = tmp_path / 'scripts/verify_native_canvas.py'
    path.parent.mkdir()
    path.write_text(SOURCE.read_text(encoding='utf-8-sig'), encoding='utf-8', newline='\n')
    subprocess.run(['git', 'apply', '--whitespace=error', str(DIRECTORY / 'retained-contexts-next.patch')],
                   cwd=tmp_path, check=True, capture_output=True, timeout=30)
    namespace = {'__name__': 'retained_context_draft', '__file__': str(SOURCE)}
    exec(compile(path.read_text(encoding='utf-8-sig'), str(path), 'exec'), namespace)
    return namespace


def fixture_page(missing=None, missing_frame=False):
    expected = {'document': {'context': 'document'},
                **{name: {'context': name} for name in FRAMES},
                **{name: {'context': name} for name in ('worker', 'shared_worker', 'service_worker')}}
    frames = {}
    for name, identifier in FRAMES.items():
        frame = SimpleNamespace(evaluate=AsyncMock(return_value=expected[name]))
        element = SimpleNamespace(content_frame=AsyncMock(return_value=None if name == missing and missing_frame else frame))
        frames['#' + identifier] = SimpleNamespace(element_handle=AsyncMock(
            return_value=None if name == missing and not missing_frame else element))
    workers = {name: value for name, value in expected.items() if name.endswith('worker')}
    page = SimpleNamespace(goto=AsyncMock(), locator=Mock(side_effect=lambda selector: frames[selector]),
        evaluate=AsyncMock(side_effect=[expected['document'], workers]))
    return page, expected


def test_unselected_draft_binds_current_source_without_runtime_claims():
    record = json.loads((DIRECTORY / 'retained-contexts74-preparation-observations.json').read_bytes())
    assert record['source_normalized_utf8_lf_sha256'] == hashlib.sha256(
        SOURCE.read_text(encoding='utf-8-sig').encode('utf-8')).hexdigest()
    assert record['patch_sha256'] == hashlib.sha256((DIRECTORY / record['patch']).read_bytes()).hexdigest()
    assert record['selected'] is False and record['native_runtime_verified'] is False
    assert record['privacy_admitted'] is False and record['production_admitted'] is False


def test_ready_collection_reads_existing_contexts_without_navigation_or_dom_reset(draft):
    page, expected = fixture_page()
    assert asyncio.run(draft['observe_ready'](page, 'explicit-read')) == expected
    page.goto.assert_not_called()
    assert [call.args for call in page.evaluate.await_args_list] == [('explicit-read',), (draft['WORKERS'],)]
    assert [call.args for call in page.locator.call_args_list] == [('#' + value,) for value in FRAMES.values()]


@pytest.mark.parametrize('missing', FRAMES)
@pytest.mark.parametrize('missing_frame', [False, True])
def test_missing_retained_element_or_frame_is_not_recreated(draft, missing, missing_frame):
    page, _ = fixture_page(missing, missing_frame)
    with pytest.raises(ValueError, match='missing'):
        asyncio.run(draft['observe_ready'](page, 'explicit-read'))
    page.goto.assert_not_called()
    assert page.evaluate.await_count == 1
