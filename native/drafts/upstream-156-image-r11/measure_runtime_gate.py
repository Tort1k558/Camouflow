"""Execute the existing full source-runtime gate on an explicitly selected runtime."""

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import threading

ROOT = Path(__file__).resolve().parents[3]
INPUTS = {ROOT / 'scripts/verify_native_runtime.py'}


async def verify_controller_driver():
    import playwright

    expected = Path(playwright.__file__).resolve()
    env = {**os.environ, 'PYTHONPATH': sysconfig.get_path('purelib') + os.pathsep
           + os.environ.get('PYTHONPATH', '')}
    code = ('import json, pathlib, playwright; '
            'print(json.dumps(str(pathlib.Path(playwright.__file__).resolve())))')
    child = await asyncio.to_thread(subprocess.run,
        [sys._base_executable, '-B', '-c', code], cwd=ROOT, env=env,
        capture_output=True, text=True, check=True, timeout=20)
    if Path(json.loads(child.stdout)) != expected:
        raise ValueError('Controller interpreter shadows the explicitly selected Playwright package')
    return dict(verified=True, same_package_path=True, browser_started=False)


def selfcheck():
    return dict(prepared_gate='scripts.verify_native_runtime.verify', browser_started=False,
                experimental_policies_enabled=False, installed_package_verified=False,
                production_admitted=False)


async def measure(make, configuration):
    from scripts.verify_native_runtime import FixtureHandler, FixtureServer, close_owned_log_handlers, verify

    owner = make('native-owned-r11-runtime', configuration)
    root = owner.profile_dir
    if Path(os.environ.get('CAMOUFLOW_DATA_DIR', '')).resolve() != root / 'workspace':
        raise ValueError('Select the owned runtime gate database before importing application services')
    child_driver = await verify_controller_driver()
    servers = []
    threads = []
    report = dict(passed=False, measurement_complete=False, completed_checks=[],
                  experimental_policies_enabled=False, installed_package_verified=False,
                  production_admitted=False, cleanup_errors=[], controller_driver=child_driver)
    try:
        for proxy in (False, True):
            server = FixtureServer(('127.0.0.1', 0), FixtureHandler)
            servers.append(server)
            server.proxy_mode = proxy
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            threads.append(thread)
            thread.start()
        report['runtime'] = await verify(root, owner.executable,
            'http://127.0.0.1:' + str(servers[0].server_port), servers[1], checks=report['completed_checks'])
        report['measurement_complete'] = True
    except Exception as error:
        report.update(error_type=type(error).__name__, error=str(error)[:3000],
                      error_notes=list(getattr(error, '__notes__', ())))
    finally:
        for server, thread in zip(servers, threads):
            try:
                if thread.is_alive():
                    server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                if thread.is_alive():
                    raise RuntimeError('Runtime fixture thread remains live')
            except Exception as error:
                report['cleanup_errors'].append(dict(stage='fixture', type=type(error).__name__, error=str(error)))
        try:
            close_owned_log_handlers(root)
        except Exception as error:
            report['cleanup_errors'].append(dict(stage='logs', type=type(error).__name__, error=str(error)))
        report['fixture_threads_closed'] = all(not thread.is_alive() for thread in threads)
        report['passed'] = (report['measurement_complete'] and report['runtime'].get('passed') is True
                            and report['fixture_threads_closed'] and not report['cleanup_errors'])
    return report
