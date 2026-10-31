"""Exercise native-format immutable GPU pixel snapshots and dependent buffer shadows."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parent


def main():
    path = MODULE.parent / 'webgpu-buffer-scatter/check.py'
    spec = importlib.util.spec_from_file_location('glint_gpu_scatter_check', path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker.main(
        module=MODULE, record_name='webgpu-canonical-plane-preparation.json', extension_required=True,
        fixture_base=MODULE.parent / 'webgpu-shadow-texture/shadow_test.cc',
        additional_native_sources=('projected_texture.cc',),
        shader_paths=tuple(MODULE.parent / name for name in (
            'webgpu-edge-compute/edge_compute.hlsl', 'webgpu-shadow-texture/texture_consumer.hlsl',
            'webgpu-buffer-scatter/buffer_scatter.hlsl')),
        expected_result={
            'passed': True, 'hardware_adapter': True, 'cases': 20, 'assertions': 154849,
            'shared_quota_cases': 20, 'typed_texture_consumer_verified': True,
            'canonical_plane_verified': True, 'source_mutation_isolated': True,
            'dependent_retirement_verified': True, 'browser_integrated': False,
        },
    )


if __name__ == '__main__':
    raise SystemExit(main())
