"""Compact resource labels with explicit measurement scope."""

import math


def _number(value):
    try:
        return type(value) in {int, float} and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def resource_presentation(resource):
    if not isinstance(resource, dict):
        return "", ""
    root = resource.get("memory_mb")
    root_valid = _number(root)
    root_details = [f"Limit-process working set: {root:g} MiB"] if root_valid else []
    limit = resource.get("memory_limit_mb")
    if _number(limit):
        root_details.append(f"Process memory limit: {limit:g} MiB" if limit else "Process memory limit: disabled")
    tree = resource.get("process_tree")
    if not isinstance(tree, dict):
        return (f"{root} MB" if root_valid else ""), "\n".join(root_details)
    totals = [tree.get(key) for key in ("working_set_sum_bytes", "private_commit_sum_bytes", "process_count")]
    if tree.get("state") == "ready" and all(type(value) is int and _number(value) for value in totals) and totals[2] > 0:
        working_set, private_commit, count = totals
        details = [f"Working-set sum: {working_set / 1048576:.1f} MiB (shared pages may be counted more than once)",
                   f"Private commit: {private_commit / 1048576:.1f} MiB", f"Processes: {count}"]
        cpu = tree.get("cpu")
        if isinstance(cpu, dict) and cpu.get("state") == "ready" and _number(cpu.get("mean_cpu_cores")):
            details.append(f"Observed CPU: {cpu['mean_cpu_cores']:.2f} cores (not host-normalized percent)")
        else:
            details.append("Observed CPU: interval unavailable")
        return f"Tree {working_set / 1048576:.0f} MiB", "\n".join(details + root_details)
    state = "waiting for connection" if tree.get("state") == "warming" else "unavailable"
    return (f"Process {root:g} MiB" if root_valid else "Resources unavailable"), "\n".join(
        ["Process-tree measurement: " + state] + root_details)
