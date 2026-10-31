"""Exercise extracted native buffer descriptor/root-address methods on real D3D12 resources."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parent


def extract_methods(native):
    path = native / 'third_party/dawn/src/dawn/native/d3d12/BindGroupD3D12.cpp'
    source = path.read_text(encoding='utf-8-sig')
    first = source.index('void WriteBufferDescriptor(')
    helper = source[first:source.index('}  // namespace', first)]
    first = source.index('ResultOrError<bool> BindGroup::PopulateGlintViews(')
    methods = source[first:source.index('D3D12_GPU_DESCRIPTOR_HANDLE BindGroup::GetBaseViewDescriptor()', first)]
    return helper + methods


def prepare_fixture(native, output):
    path = output / 'native_method.inc'
    path.write_text(extract_methods(native), encoding='utf-8', newline='\n')
    return {path.name: path}


def main():
    path = MODULE.parent / 'webgpu-buffer-scatter/check.py'
    spec = importlib.util.spec_from_file_location('glint_gpu_scatter_check', path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker.main(
        module=MODULE, record_name='webgpu-buffer-bindings-preparation.json', extension_required=True,
        fixture_base=MODULE / 'compute_test.cc', fixture_preparer=prepare_fixture,
        source_gate_path=MODULE.parent / 'webgpu-input-plan/check.py',
        source_record_path=MODULE.parent / 'environment/webgpu-input-plan-preparation.json',
        shader_paths=(MODULE / 'buffer_consumer.hlsl',),
        expected_result={
            'passed': True, 'hardware_adapter': True, 'native_descriptor_methods_executed': True,
            'cases': 20, 'assertions': 21728, 'rejected_overrides': 244, 'root_uniform_cases': 2,
            'cached_descriptors_unchanged': True, 'original_buffer_unchanged': True,
            'browser_integrated': False, 'native_binding_routing_installed': False,
        },
    )


if __name__ == '__main__':
    raise SystemExit(main())
