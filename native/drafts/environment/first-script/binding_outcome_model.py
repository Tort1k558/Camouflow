import argparse
import ast
import asyncio
import hashlib
import inspect
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Callable

from playwright._impl._errors import TargetClosedError

parser = argparse.ArgumentParser(description='Model extracted BindingCall delivery; no browser or installation changes')
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--report', type=Path, required=True)
args = parser.parse_args()
PATH = args.source.resolve(strict=True)
tree = ast.parse(PATH.read_text(encoding='utf-8-sig'))
binding = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'BindingCall')
method = next(node for node in binding.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'call')
namespace = {'Callable': Callable, 'from_channel': lambda value: value, 'parse_result': lambda value: value,
             'serialize_argument': lambda value: value, 'serialize_error': lambda value, tb: {'message': str(value)},
             'inspect': inspect, 'sys': sys, 'TargetClosedError': TargetClosedError}
exec(compile(ast.Module(body=[method], type_ignores=[]), str(PATH), 'exec'), namespace)
rows = []

async def check(name, handler, *, send_error=None, expected_method=None, expected_error=None, serialize_error=False):
    calls = []
    count = 0
    async def send(method, timeout, params):
        calls.append((method, params))
        if send_error:
            raise send_error
    page = SimpleNamespace(context=object())
    frame = SimpleNamespace(_page=page)
    self = SimpleNamespace(_initializer={'frame': frame, 'args': [7]}, _channel=SimpleNamespace(send=send))
    def invoke(source, value):
        nonlocal count
        count += 1
        assert source['frame'] is frame and value == 7
        return handler(value)
    old = namespace['serialize_argument']
    if serialize_error:
        def reject_serialization(value):
            raise ValueError('unsupported result')
        namespace['serialize_argument'] = reject_serialization
    try:
        try:
            await namespace['call'](self, invoke)
        except BaseException as error:
            assert expected_error is not None and isinstance(error, expected_error), (name, error)
        else:
            assert expected_error is None, name
        assert count == 1
        assert len(calls) == (1 if expected_method else 0), (name, calls)
        if expected_method:
            assert calls[0][0] == expected_method
        rows.append({'name': name, 'passed': True, 'handler_calls': count, 'delivery_attempts': len(calls)})
    finally:
        namespace['serialize_argument'] = old

def fail(error):
    def handler(value):
        raise error
    return handler

async def run():
    await check('sync-result-resolves-once', lambda value: value, expected_method='resolve')
    async def asynchronous(value):
        await asyncio.sleep(0)
        return value
    await check('async-result-resolves-once', asynchronous, expected_method='resolve')
    await check('handler-error-rejects-once', fail(ValueError('owned handler error')), expected_method='reject')
    await check('handler-target-closed-is-still-a-rejection', fail(TargetClosedError()), expected_method='reject')
    await check('closed-target-during-resolve-does-not-spawn-reject-task', lambda value: value,
                send_error=TargetClosedError(), expected_method='resolve')
    await check('closed-target-during-reject-does-not-spawn-reject-task', fail(ValueError('owned')),
                send_error=TargetClosedError(), expected_method='reject')
    await check('nonclosing-resolve-error-is-visible', lambda value: value, send_error=RuntimeError('transport'),
                expected_method='resolve', expected_error=RuntimeError)
    await check('nonclosing-reject-error-is-visible', fail(ValueError('owned')), send_error=RuntimeError('transport'),
                expected_method='reject', expected_error=RuntimeError)
    await check('handler-cancellation-is-not-converted-to-an-rpc', fail(asyncio.CancelledError()), expected_error=asyncio.CancelledError)
    await check('serialization-error-rejects-once', lambda value: value, serialize_error=True, expected_method='reject')

asyncio.run(run())
report = {'passed': True, 'tests': len(rows), 'results': rows, 'scope': 'Exact extracted Python BindingCall draft with modeled channels; not browser or package admission',
          'source_sha256': hashlib.sha256(PATH.read_bytes()).hexdigest()}
args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps(report))
