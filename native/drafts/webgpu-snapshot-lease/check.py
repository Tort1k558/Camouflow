"""Replay private GPU lease sources and test extracted capability ownership with fake native resources."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parent


def extract_contracts(staging):
    native = staging / 'third_party/dawn'
    api = (native / 'include/dawn/native/DawnNative.h').read_text(encoding='utf-8-sig')
    header = (native / 'src/dawn/native/d3d12/GlintTextureProjectionD3D12.h').read_text(encoding='utf-8-sig')
    source = (native / 'src/dawn/native/d3d12/GlintTextureProjectionD3D12.cpp').read_text(encoding='utf-8-sig')
    capture = (native / 'src/dawn/native/d3d12/GlintTextureReadbackD3D12.cpp').read_text(encoding='utf-8-sig')

    def between(text, start, end):
        first = text.index(start)
        return text[first:text.index(end, first)]

    return {
        'api': between(api, 'namespace d3d12 {\nclass GlintTextureProjector;', 'struct GlintBufferIdentity {'),
        'native': between(header, 'struct GlintProjectionIdentity final', '}  // namespace dawn::native::d3d12'),
        'copy': between(source, 'ResultOrError<std::unique_ptr<glint::candidate::d3d12::ProjectedTexture>>\nGlintTextureProjector::RecordCopy(',
                        'ResultOrError<std::shared_ptr<const GlintGpuReadbackSnapshot>>'),
        'lease': between(source, 'ResultOrError<std::shared_ptr<const GlintGpuReadbackSnapshot>>',
                         'ResultOrError<std::unique_ptr<glint::candidate::d3d12::ProjectedTexture>>\nGlintTextureProjector::RecordTexture('),
        'snapshot': between(capture, 'class NativeGlintReadbackSnapshot final', 'class NativeGlintByteReadbackSnapshot'),
        'factory': between(capture, 'ResultOrError<std::unique_ptr<GlintReadbackSnapshot>> RecordGlintNativeTextureSnapshot(',
                           'ResultOrError<std::unique_ptr<GlintByteReadbackSnapshot>>'),
    }


def main():
    path = MODULE.parent / 'webgpu-private-backing/check.py'
    spec = importlib.util.spec_from_file_location('glint_source_predicate_check', path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker.main(
        module=MODULE, record_name='webgpu-snapshot-lease-preparation.json', extractor=extract_contracts,
        expected_result={
            'passed': True, 'assertions': 34817, 'iterations': 512,
            'backend_mocked': True, 'source_extracted_gpu_lease_only': True,
            'logical_owner_identity_verified': True, 'reused_device_address_rejected': True,
            'actual_native_device_queue_executed': False,
        },
    )


if __name__ == '__main__':
    raise SystemExit(main())
