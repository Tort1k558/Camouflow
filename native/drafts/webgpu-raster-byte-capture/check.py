"""Replay raster byte-capture sources and test the extracted pass accumulator with a CPU controller."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parent


def extract_merge(staging):
    path = staging / 'third_party/dawn/src/dawn/native/d3d12/CommandBufferD3D12.cpp'
    text = path.read_text(encoding='utf-8-sig')
    start = text.index('    static bool MergeGlintBoundScope(')
    end = text.index('    MaybeError AccumulateGlintRenderScope(', start)
    return {'merge': text[start:end]}


def main():
    path = MODULE.parent / 'webgpu-private-backing/check.py'
    spec = importlib.util.spec_from_file_location('glint_source_predicate_check', path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker.main(
        module=MODULE, record_name='webgpu-raster-byte-capture-preparation.json',
        extractor=extract_merge, controller=True,
        expected_result={
            'passed': True, 'assertions': 191422, 'oracle_passes': 1000,
            'oracle_draws': 16000, 'duplicate_draws': 8192, 'controller_passes': 256,
            'source_extracted_merge_only': True, 'backend_mocked': True,
            'actual_native_render_pass_executed': False,
        },
    )


if __name__ == '__main__':
    raise SystemExit(main())
