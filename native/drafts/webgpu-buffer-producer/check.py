"""Check extracted native shadow-production control flow with explicitly mocked GPU operations."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parent


def extract_contracts(staging):
    native = staging / 'third_party/dawn/src/dawn/native/d3d12'
    source = (native / 'GlintTextureProjectionD3D12.cpp').read_text(encoding='utf-8-sig')
    header = (native / 'GlintTextureProjectionD3D12.h').read_text(encoding='utf-8-sig')
    return {
        'types': header[header.index('struct GlintBufferWriteRange {'):
                        header.index('class GlintTextureProjector {')],
        'helpers': source[source.index('class GlintNativeBufferOwner final'):
                          source.index('ResultOrError<ComPtr<ID3D12PipelineState>> CompileGlintProjectionPipeline(')],
        'resolve': source[source.index('std::shared_ptr<const GlintGpuPixelSnapshot> GlintTextureProjector::ResolveSnapshot('):
                          source.index('ResultOrError<std::unique_ptr<GlintBufferProjectionBatch>>')],
        'producer': source[source.index('ResultOrError<std::unique_ptr<GlintBufferProjectionBatch>>'):
                           source.index('ResultOrError<std::unique_ptr<glint::candidate::d3d12::ProjectedTexture>>\n'
                                        'GlintTextureProjector::RecordTexture(')],
    }


def main():
    path = MODULE.parent / 'webgpu-private-backing/check.py'
    spec = importlib.util.spec_from_file_location('glint_producer_control_check', path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker.main(
        module=MODULE, record_name='webgpu-buffer-producer-preparation.json',
        extractor=extract_contracts, expected_result={
            'passed': True, 'cases': 1216, 'assertions': 24288,
            'native_producer_control_flow_executed': True, 'backend_mocked': True,
            'actual_native_device_queue_executed': False,
        },
    )


if __name__ == '__main__':
    raise SystemExit(main())
