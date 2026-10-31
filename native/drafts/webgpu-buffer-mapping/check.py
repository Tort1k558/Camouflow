"""Test shared GPU mapping and full-allocation initialization logic with the actual CPU controller."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parent


def extract_contracts(staging):
    native_header = staging / 'gpu/command_buffer/common/glint/buffer_scatter_mapping.h'
    public_header = MODULE.parent / 'webgpu-buffer-scatter/buffer_scatter_mapping.h'
    if native_header.read_bytes() != public_header.read_bytes():
        raise ValueError('Shared public/native mapping header differs')
    path = MODULE.parent / 'webgpu-input-plan/check.py'
    spec = importlib.util.spec_from_file_location('glint_input_plan_fixture', path)
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    source = (path.parent / 'predicates-template.cc').read_text(encoding='utf-8-sig')
    source = source.replace('/* GLINT_LEGACY */', previous.extract_contracts(staging)['legacy'])
    source = '\n'.join(line for line in source.splitlines() if not line.startswith('#include')) + '\n'
    if source.count('int main() {') != 1:
        raise ValueError('Expected one input-plan regression entry point')
    source = source.replace('int main() {', 'void RunInputPlanRegression() {')
    source = source[:source.rindex('    std::printf(')] + '}\n'
    buffer = (staging / 'third_party/dawn/src/dawn/native/d3d12/BufferD3D12.cpp').read_text(encoding='utf-8-sig')
    first = buffer.index('MaybeError Buffer::EnsureGlintAllocationInitialized(')
    allocation = buffer[first:buffer.index('MaybeError Buffer::EnsureDataInitialized(', first)]
    return {'regression': source, 'allocation': allocation}


def main():
    path = MODULE.parent / 'webgpu-private-backing/check.py'
    spec = importlib.util.spec_from_file_location('glint_source_predicate_check', path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker.main(
        module=MODULE, record_name='webgpu-buffer-mapping-preparation.json', extractor=extract_contracts,
        controller=True, expected_result={
            'passed': True, 'assertions': 110776, 'prior_plan_assertions': 12802, 'legacy_assertions': 10154,
            'backend_mocked': True, 'cpu_controller_executed': True,
            'native_mapping_matches_byte_oracle': True, 'physical_padding_contract_verified': True,
            'actual_native_device_queue_executed': False,
        },
    )


if __name__ == '__main__':
    raise SystemExit(main())
