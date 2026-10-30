"""Explicit WebGPU backend for the shared owned GPU worker lifecycle checks."""
from functools import partial

import retained_gpu_worker_objects as common
import retained_webgpu_objects as backend

lifecycle = common.lifecycle
service = common.service
worker_read = partial(common.worker_read, backend=backend)
validate_phase = partial(common.validate_phase, backend=backend)
validate_pair = partial(common.validate_pair, backend=backend)
validate_restart_pair = partial(common.validate_restart_pair, backend=backend)
validate_runs = partial(common.validate_runs, backend=backend)
force_service_restarts = partial(common.force_service_restarts, backend=backend)
validate_forced_cases = partial(common.validate_forced_cases, backend=backend)
