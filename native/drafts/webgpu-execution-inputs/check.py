"""Replay execution-input contracts and test extracted native logic with synthetic owners and a CPU controller."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parent


def extract_contracts(staging):
    native = staging / 'third_party/dawn/src/dawn/native'
    header = (native / 'Commands.h').read_text(encoding='utf-8-sig')
    command = (native / 'd3d12/CommandBufferD3D12.cpp').read_text(encoding='utf-8-sig')

    def structure(text, name):
        start = text.index('struct ' + name + ' {')
        return text[start:text.index('\n};', start) + 3]

    start = command.index('bool AppendGlintOriginalIndirectUses(')
    end = command.index('bool HasGlintUnprojectedAttachmentInputs(', start)
    return {
        'inputs': structure(header, 'GlintIndirectInputs'),
        'native_use': structure(command, 'GlintNativeBufferUse'),
        'indirect': command[start:end],
        'attachments': command[end:command.index('\n}  // namespace', end)],
    }


def main():
    path = MODULE.parent / 'webgpu-private-backing/check.py'
    spec = importlib.util.spec_from_file_location('glint_source_predicate_check', path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker.main(
        module=MODULE, record_name='webgpu-execution-inputs-preparation.json',
        extractor=extract_contracts, controller=True,
        expected_result={
            'passed': True, 'assertions': 2391, 'attachment_cases': 720,
            'accepted_attachment_cases': 49, 'denied_logical_control_cases': 2,
            'source_extracted_input_contracts_only': True, 'backend_mocked': True,
            'actual_frontend_encoding_executed': False,
            'actual_native_device_queue_executed': False,
        },
    )


if __name__ == '__main__':
    raise SystemExit(main())
