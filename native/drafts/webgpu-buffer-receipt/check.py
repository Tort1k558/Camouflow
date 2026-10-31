"""Check exact-scope GPU input receipts with the real CPU controller and mocked native issuer."""
import hashlib
import importlib.util
import json
from pathlib import Path

MODULE = Path(__file__).resolve().parent


def extract_contracts(staging):
    path = MODULE.parent / 'webgpu-input-plan/check.py'
    spec = importlib.util.spec_from_file_location('glint_old_input_plan', path)
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    regression = (path.parent / 'predicates-template.cc').read_text(encoding='utf-8-sig')
    regression = regression.replace('/* GLINT_LEGACY */', previous.extract_contracts(staging)['legacy'])
    regression = '\n'.join(line for line in regression.splitlines() if not line.startswith('#include')) + '\n'
    if regression.count('int main() {') != 1:
        raise ValueError('Expected one legacy input-plan entry point')
    regression = regression.replace('int main() {', 'void RunOldInputPlanRegression() {')
    regression = regression[:regression.rindex('    std::printf(')] + '}\n'
    source = (staging / 'third_party/dawn/src/dawn/native/d3d12/CommandBufferD3D12.cpp').read_text(encoding='utf-8-sig')
    first = source.index('    ResultOrError<std::shared_ptr<const GlintGpuInputPlan>> GetGlintGpuInputPlanForCapture()')
    getter = source[first:source.index('    MaybeError CopyBackGlintComputeBuffers(', first)]
    return {'regression': regression, 'getter': getter}


def main():
    record = json.loads((MODULE.parent / 'environment/webgpu-buffer-receipt-preparation.json').read_bytes())
    names = ('webgpu-input-plan/check.py', 'webgpu-input-plan/predicates-template.cc',
             'webgpu-shader-capture/controller_test.cc')
    if set(record['dependency_sources_sha256']) != set(names):
        raise ValueError('Measured receipt dependency set differs')
    for name in names:
        if hashlib.sha256((MODULE.parent / name).read_bytes()).hexdigest() != record['dependency_sources_sha256'][name]:
            raise ValueError('Measured receipt dependency differs')
    path = MODULE.parent / 'webgpu-private-backing/check.py'
    spec = importlib.util.spec_from_file_location('glint_receipt_cpu_check', path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker.main(module=MODULE, record_name='webgpu-buffer-receipt-preparation.json',
        extractor=extract_contracts, controller=True, expected_result={
            'passed': True, 'assertions': 15735, 'cases': 896, 'prior_plan_assertions': 12802,
            'legacy_assertions': 10154, 'backend_mocked': True, 'cpu_controller_executed': True,
            'exact_scope_receipt_checked': True, 'actual_native_device_queue_executed': False,
        })


if __name__ == '__main__':
    raise SystemExit(main())
