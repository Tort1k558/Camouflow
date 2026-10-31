"""Replay GPU input-plan sources and execute the real CPU controller with fake native GPU capabilities."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parent


def extract_contracts(staging):
    source = (MODULE.parent / 'webgpu-shader-capture/controller_test.cc').read_text(encoding='utf-8-sig')
    source = '\n'.join(line for line in source.splitlines()
                       if not line.startswith(('#include', '#define CHECK'))) + '\n'
    if source.count('int main() {') != 1:
        raise ValueError('Expected one legacy controller entry point')
    source = source.replace('int main() {', 'void Run() {')
    source = source[:source.rindex('  std::printf(')] + '}\n'
    return {'legacy': 'namespace legacy {\n' + source + '}\n'}


def main():
    path = MODULE.parent / 'webgpu-private-backing/check.py'
    spec = importlib.util.spec_from_file_location('glint_source_predicate_check', path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker.main(
        module=MODULE, record_name='webgpu-input-plan-preparation.json', extractor=extract_contracts,
        controller=True, expected_result={
            'passed': True, 'assertions': 12802, 'iterations': 256, 'legacy_assertions': 10154,
            'backend_mocked': True, 'cpu_controller_executed': True,
            'stale_and_foreign_plan_rejected': True, 'plan_commit_does_not_admit_raw_inputs': True,
            'actual_native_device_queue_executed': False,
        },
    )


if __name__ == '__main__':
    raise SystemExit(main())
