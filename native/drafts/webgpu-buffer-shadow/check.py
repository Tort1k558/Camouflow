"""Replay native budgeted-buffer sources and execute the actual helper in a standalone GPU fixture."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parent


def main():
    path = MODULE.parent / 'webgpu-buffer-scatter/check.py'
    spec = importlib.util.spec_from_file_location('glint_gpu_scatter_check', path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker.main(
        module=MODULE, record_name='webgpu-buffer-shadow-preparation.json', extension_required=True,
        expected_result={
            'passed': True, 'hardware_adapter': True, 'cases': 58, 'assertions': 178960,
            'rejected_parameters': 696, 'budget_rejections': 812, 'cpu_cancel_cases': 26,
            'gpu_projection_scatter_consumer_verified': True, 'budgeted_shadow_helper_executed': True,
            'dependent_quota_lifetime_verified': True, 'original_buffer_unchanged': True,
            'native_binding_routing_installed': False, 'browser_integrated': False,
        },
    )


if __name__ == '__main__':
    raise SystemExit(main())
