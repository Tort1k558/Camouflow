"""Attempt an early breakaway only inside the host controller's owned job."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--user-data-dir', required=True)
parser.add_argument('--glint-crash-challenge', required=True)
parser.add_argument('--glint-crash-ack', required=True)
args = parser.parse_args()
profile = Path(args.user_data_dir)
try:
    escaped = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
        creationflags=subprocess.CREATE_BREAKAWAY_FROM_JOB | subprocess.CREATE_NO_WINDOW)
except OSError as error:
    (profile / 'early-breakaway.json').write_text(json.dumps(dict(winerror=error.winerror)), encoding='utf-8')
    if error.winerror != 5:
        raise
else:
    # Defensive cleanup if the tested job policy is ever accidentally relaxed.
    escaped.terminate()
    escaped.wait(timeout=5)
    raise SystemExit('A supposedly non-breakaway child escaped its owned job')
ack = dict(schema=1, pid=os.getpid(), challenge=args.glint_crash_challenge,
           profile=str(profile), acknowledged=True, workers=1,
           scope='document-and-worker-cookie-prefix')
destination = Path(args.glint_crash_ack)
temporary = destination.with_suffix('.tmp')
temporary.write_text(json.dumps(ack), encoding='utf-8')
os.replace(temporary, destination)
time.sleep(60)
