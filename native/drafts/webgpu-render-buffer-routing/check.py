"""Check extracted render-scope equality and cursor restoration, not native dispatch."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parent


def extract_contracts(staging):
    header = (staging / 'third_party/dawn/src/dawn/native/CommandAllocator.h').read_text(encoding='utf-8-sig')
    first = header.index('    template <typename Visitor>')
    end = header.index('    // This method must', first)
    source = (staging / 'third_party/dawn/src/dawn/native/d3d12/CommandBufferD3D12.cpp').read_text(encoding='utf-8-sig')
    scope = source.index('    static bool SameGlintRenderScope(')
    scope_end = source.index('    MaybeError CaptureGlintRenderScope(', scope)
    return {'cursor': header[first:end], 'scope': source[scope:scope_end]}


def main():
    path = MODULE.parent / 'webgpu-private-backing/check.py'
    spec = importlib.util.spec_from_file_location('glint_render_buffer_cpu_check', path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker.main(
        module=MODULE, record_name='webgpu-render-buffer-routing-preparation.json',
        extractor=extract_contracts, expected_result={
            'passed': True, 'cursor_cases': 125, 'scope_cases': 1536,
            'backend_mocked': True, 'actual_native_device_queue_executed': False,
        },
    )


if __name__ == '__main__':
    raise SystemExit(main())
