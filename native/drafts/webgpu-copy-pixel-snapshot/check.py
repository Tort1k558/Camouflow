"""Replay paired-copy sources and execute extracted factory logic with mocked native owners."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parent


def extract_contracts(staging):
    native = staging / 'third_party/dawn/src/dawn/native/d3d12'
    capture = (native / 'GlintTextureReadbackD3D12.cpp').read_text(encoding='utf-8-sig')
    projection = (native / 'GlintTextureProjectionD3D12.cpp').read_text(encoding='utf-8-sig')
    start = capture.index('class NativeGlintReadbackSnapshot final')
    end = capture.index('class NativeGlintByteReadbackSnapshot', start)
    snapshot = capture[start:end]
    start = capture.index('ResultOrError<std::unique_ptr<GlintReadbackSnapshot>> RecordGlintNativeTextureSnapshot(')
    end = capture.index('ResultOrError<std::unique_ptr<GlintByteReadbackSnapshot>>', start)
    factory = capture[start:end]
    start = projection.index('ResultOrError<std::unique_ptr<glint::candidate::d3d12::ProjectedTexture>>\nGlintTextureProjector::RecordCopy(')
    end = projection.index('ResultOrError<std::unique_ptr<glint::candidate::d3d12::ProjectedTexture>>\nGlintTextureProjector::RecordTexture(', start)
    return {'snapshot': snapshot, 'factory': factory, 'copy': projection[start:end]}


def main():
    path = MODULE.parent / 'webgpu-private-backing/check.py'
    spec = importlib.util.spec_from_file_location('glint_source_predicate_check', path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker.main(
        module=MODULE, record_name='webgpu-copy-pixel-snapshot-preparation.json',
        extractor=extract_contracts, expected_result={
            'passed': True, 'backend_mocked': True, 'assertions': 52232, 'factory_cases': 6149,
            'source_extracted_paired_factory_only': True,
            'actual_native_device_queue_executed': False,
        },
    )


if __name__ == '__main__':
    raise SystemExit(main())
