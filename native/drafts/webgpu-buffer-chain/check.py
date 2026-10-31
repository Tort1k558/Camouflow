"""Exercise native GPU projection through transient buffer descriptors with explicit Dawn mocks."""
import importlib.util
import shutil
from pathlib import Path

MODULE = Path(__file__).resolve().parent


def prepare_fixture(native, output):
    path = MODULE.parent / 'webgpu-buffer-bindings/check.py'
    spec = importlib.util.spec_from_file_location('glint_chain_descriptor_extract', path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    methods = output / 'native_method.inc'
    methods.write_text(checker.extract_methods(native), encoding='utf-8', newline='\n')
    header = output / 'descriptor_fixture.h'
    shutil.copyfile(path.parent / header.name, header)
    source = (native / 'third_party/dawn/src/dawn/native/d3d12/CommandBufferD3D12.cpp').read_text(encoding='utf-8-sig')
    first = source.index('    MaybeError CopyBackGlintComputeBuffers(')
    copyback = output / 'copyback_method.inc'
    copyback.write_text(source[first:source.index('    MaybeError CaptureGlintComputeScope(', first)],
                        encoding='utf-8', newline='\n')
    return {methods.name: methods, header.name: header, copyback.name: copyback}


def main():
    path = MODULE.parent / 'webgpu-buffer-scatter/check.py'
    spec = importlib.util.spec_from_file_location('glint_chain_gpu_check', path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker.main(
        module=MODULE, record_name='webgpu-buffer-chain-observations.json',
        extension_required=True, fixture_base=MODULE / 'compute_test.cc',
        fixture_preparer=prepare_fixture, additional_native_sources=('projected_texture.cc',),
        source_gate_path=MODULE.parent / 'webgpu-buffer-producer/check.py',
        source_record_path=MODULE.parent / 'environment/webgpu-buffer-producer-preparation.json',
        shader_paths=tuple(MODULE.parent / name for name in (
            'webgpu-edge-compute/edge_compute.hlsl', 'webgpu-shadow-texture/texture_consumer.hlsl',
            'webgpu-buffer-scatter/buffer_scatter.hlsl')) + (MODULE / 'buffer_consumer.hlsl',),
        expected_result={
            'passed': True, 'hardware_adapter': True, 'cases': 40, 'assertions': 495537,
            'shared_quota_cases': 40, 'typed_texture_consumer_verified': True,
            'canonical_plane_verified': True, 'native_buffer_descriptor_chain_verified': True,
            'writable_copyback_chain_verified': True,
            'source_mutation_isolated': True, 'dependent_retirement_verified': True,
            'browser_integrated': False,
        },
    )


if __name__ == '__main__':
    raise SystemExit(main())
