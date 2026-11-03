"""Owned host-test process, deliberately not a browser or persistence oracle."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--mode', default='valid')
parser.add_argument('--foreign-pid', type=int)
parser.add_argument('--user-data-dir', required=True)
parser.add_argument('--glint-crash-challenge', required=True)
parser.add_argument('--glint-crash-ack', required=True)
args = parser.parse_args()
if args.mode == 'exit':
    raise SystemExit(0)
profile = Path(args.user_data_dir)
(profile / 'host-stub-profile.txt').write_text('host control test only', encoding='utf-8')
if args.mode == 'descendant':
    subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
if args.mode != 'missing':
    payload = dict(schema=1, challenge=args.glint_crash_challenge, pid=os.getpid(),
                   profile=str(profile), acknowledged=True, workers=1,
                   scope='document-and-worker-cookie-prefix')
    if args.mode == 'foreign':
        payload['pid'] = args.foreign_pid
    if args.mode == 'wrong-challenge':
        payload['challenge'] = '0' * 64
    if args.mode == 'wrong-profile':
        payload['profile'] = str(profile.parent)
    destination = Path(args.glint_crash_ack)
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload), encoding='utf-8', newline='\n')
    os.replace(temporary, destination)
time.sleep(60)
