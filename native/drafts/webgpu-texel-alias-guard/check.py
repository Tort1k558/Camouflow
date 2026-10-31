"""Verify conditional rejection of unsupported projected texel-buffer aliases, not texel projection."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parent


def extract_contracts(staging):
    source = (staging / 'third_party/dawn/src/dawn/native/d3d12/CommandBufferD3D12.cpp').read_text(encoding='utf-8-sig')
    first = source.index('    GlintProjectedBuffer* FindGlintProjectedBuffer(')
    end = source.index('    MaybeError ValidateGlintProjectedTexelBindings(', first)
    guard_end = source.index('    ResultOrError<bool> PopulateGlintViews(', end)
    return {'lookup': source[first:end], 'guard': source[end:guard_end]}


def main():
    path = MODULE.parent / 'webgpu-private-backing/check.py'
    spec = importlib.util.spec_from_file_location('glint_texel_guard_cpu_check', path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker.main(
        module=MODULE, record_name='webgpu-texel-alias-guard-preparation.json',
        extractor=extract_contracts, expected_result={
            'passed': True, 'cases': 3840, 'assertions': 11584,
            'projected_texel_alias_denied': True, 'unprojected_texel_binding_preserved': True,
            'backend_mocked': True, 'actual_native_device_queue_executed': False,
        },
    )


if __name__ == '__main__':
    raise SystemExit(main())
