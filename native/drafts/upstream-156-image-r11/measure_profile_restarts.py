"""Selected-policy concurrent profile storage/crash gate, not manager admission."""

from dataclasses import replace
from pathlib import Path
import threading

ROOT = Path(__file__).resolve().parents[3]
INPUTS = {ROOT / 'scripts/verify_native_runtime.py', ROOT / 'app/core/native/diagnostics.py'}


def selfcheck():
    return dict(prepared_presets=['native', 'gamma-1400-contrast-300'],
                rounds_per_preset=3, concurrent_profiles=3, browser_started=False,
                experimental_policy_research=True, production_admitted=False)


async def measure(make, configuration):
    from scripts.verify_native_runtime import FixtureHandler, FixtureServer, verify_multi_profile_restarts

    result = dict(passed=False, measurement_complete=False, phases=[], fixture_thread_closed=False,
                  experimental_policy_research=True, production_admitted=False)
    server = FixtureServer(('127.0.0.1', 0), FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for preset in ('native', 'gamma-1400-contrast-300'):
            selected = replace(configuration, rendering_preset=preset)
            owner = make('protected-profile-restarts-' + preset, selected)
            phase = dict(preset=preset, passed=False)
            result['phases'].append(phase)
            try:
                phase['rounds'] = await verify_multi_profile_restarts(owner.profile_dir, owner.executable,
                    'http://127.0.0.1:' + str(server.server_port), rounds=3, profiles=3,
                    configuration=selected)
                phase['passed'] = len(phase['rounds']) == 3
            except Exception as error:
                phase.update(error_type=type(error).__name__, error=str(error)[:3000],
                             error_notes=list(getattr(error, '__notes__', ())))
                break
        result['measurement_complete'] = len(result['phases']) == 2 and all(
            len(phase.get('rounds', ())) == 3 for phase in result['phases'])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        result['fixture_thread_closed'] = not thread.is_alive()
        result['passed'] = result['measurement_complete'] and result['fixture_thread_closed'] and all(
            phase['passed'] for phase in result['phases'])
    return result
