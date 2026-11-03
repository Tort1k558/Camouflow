import os
from pathlib import Path
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows process/ACL integration')

from scripts import native_checkpoint_crash as control


def test_duplicate_receipt_fields_are_rejected():
    with pytest.raises(ValueError, match='Duplicate'):
        control._unique_object([('pid', 1), ('pid', 2)])


def test_extra_receipt_fields_cannot_change_the_protocol(tmp_path):
    profile = tmp_path / 'profile'
    profile.mkdir()
    record = dict(schema=1, challenge='a' * 64, pid=1, profile=str(profile),
                  acknowledged=True, workers=1, scope='document-and-worker-cookie-prefix',
                  unexpected='field')
    with pytest.raises(ValueError, match='fields'):
        control.validate_ack(record, pid=1, challenge='a' * 64, profile=profile)


@pytest.mark.parametrize('budget', [True, 0, -1, float('nan'), float('inf'), 301])
def test_bad_budget_rejects_before_creating_or_launching_anything(tmp_path, budget):
    with pytest.raises(ValueError, match='budgets'):
        control.run_acknowledged_crash([str(Path(sys._base_executable).resolve())],
            owner_root=tmp_path, output=tmp_path / 'must-not-exist',
            cwd=Path(__file__).resolve().parent, env=dict(os.environ),
            expected_binary_sha256='0' * 64, timeout_seconds=budget)
    assert not (tmp_path / 'must-not-exist').exists()
