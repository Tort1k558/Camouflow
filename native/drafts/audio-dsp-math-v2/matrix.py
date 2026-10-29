# Copyright 2026 CamouFlow contributors.
# SPDX-License-Identifier: MIT
"""Run bounded DSP cases in separate processes; never grant browser admission."""

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys

FIELDS = ("signal", "graph", "channels", "frames", "rate", "seed", "amplitude",
          "threshold", "knee", "ratio", "attack", "release")


def load_cases(path: Path) -> tuple[bytes, list[dict]]:
    raw = path.read_bytes()
    if len(raw) > 256 * 1024:
        raise ValueError("Case manifest is too large")
    data = json.loads(raw)
    if (not isinstance(data, dict) or set(data) != {"schema", "scope", "cases"}
            or not isinstance(data["scope"], str)):
        raise ValueError("Invalid fixture container")
    if type(data["schema"]) is not int or data["schema"] != 1 or not isinstance(data["cases"], list):
        raise ValueError("Invalid fixture schema")
    cases = data["cases"]
    if not 1 <= len(cases) <= 32:
        raise ValueError("Expected 1..32 bounded cases")
    names = set()
    for row in cases:
        if not isinstance(row, dict) or set(row) != {"id", *FIELDS}:
            raise ValueError("Case requires exactly the documented fields")
        name = row["id"]
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9-]{1,48}", name) or name in names:
            raise ValueError("Invalid or duplicate case ID")
        names.add(name)
        if (not isinstance(row["signal"], str) or not isinstance(row["graph"], str)
                or row["signal"] not in {"random", "silence", "constant", "impulse", "triangle", "burst"}
                or row["graph"] not in {"compressor", "direct"}):
            raise ValueError("Unsupported signal or graph")
        for field, lower, upper in (("channels", 1, 2), ("frames", 256, 131072),
                                    ("rate", 8000, 96000), ("seed", 0, 0xffffffff)):
            if type(row[field]) is not int or not lower <= row[field] <= upper:
                raise ValueError("Invalid integer field: " + field)
        for field, lower, upper in (("amplitude", -2, 2), ("threshold", -100, 0), ("knee", 0, 40),
                                    ("ratio", 1, 20), ("attack", 0, 1), ("release", 0, 1)):
            value = row[field]
            if type(value) not in (float, int) or not lower <= value <= upper or not math.isfinite(value):
                raise ValueError("Invalid finite field: " + field)
    if "random-default" not in names:
        raise ValueError("The default calibration case is required")
    return raw, cases


def verify(args: argparse.Namespace) -> dict:
    root = Path(__file__).resolve().parent
    case_path = root / "cases.json"
    raw, cases = load_cases(case_path)
    source_inputs = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                     for name in ("matrix.py", "probe.py", "driver.cc", "compressor_math_policy.h", "cases.json")}
    spec = importlib.util.spec_from_file_location("glint_compressor_base_probe", root / "probe.py")
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load explicit sibling probe")
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    baseline = base.verify(args)
    output = args.output.resolve()
    executable = output / "probe.exe"
    executable_hash = hashlib.sha256(executable.read_bytes()).hexdigest()
    baseline_hashes = {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                       for name in ("native148.f32", "native156.f32", "float32.f32")}
    report = {"schema": 1, "scope": __doc__, "measurement_complete": False, "passed": False,
              "compiled_browser": False, "native156_runtime_verified": False, "production_admitted": False,
              "variant_device_cohort_verified": False, "default_case_consistent": False,
              "case_manifest_sha256": hashlib.sha256(raw).hexdigest(),
              "driver_sha256": baseline["driver_sha256"], "policy_sha256": baseline["policy_sha256"],
              "source_inputs_sha256": source_inputs, "cases": []}

    def save() -> None:
        (output / "matrix-report.json").write_text(json.dumps(report, indent=2) + "\n",
                                                  encoding="utf-8", newline="\n")

    save()
    try:
        for row in cases:
            owned = output / "cases" / row["id"]
            owned.mkdir(parents=True, exist_ok=False)
            measured = {"id": row["id"], "configuration": row, "passed": False}
            report["cases"].append(measured)
            try:
                result = subprocess.run([str(executable), *[str(row[name]) for name in FIELDS]],
                                        cwd=owned, capture_output=True, text=True, timeout=60)
                (owned / "stdout.log").write_text(result.stdout, encoding="utf-8")
                (owned / "stderr.log").write_text(result.stderr, encoding="utf-8")
                measured["exit_code"] = result.returncode
                if result.returncode == 0:
                    metrics = json.loads(result.stdout)
                    measured["metrics"] = metrics
                    measured["sample_sha256"] = {name: hashlib.sha256((owned / name).read_bytes()).hexdigest()
                                                 for name in baseline_hashes}
                    measured["passed"] = (
                        metrics["frames"] == row["frames"] and metrics["sample_rate"] == row["rate"]
                        and metrics["channels"] == 2 and all(metrics[key] == 0 for key in (
                            "legacy_native_different_samples", "segmentation_differences",
                            "interleaved_differences", "pow_edge_category_mismatches")))
            except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
                measured["error"] = type(error).__name__ + ": " + str(error)
            save()
        default = next(row for row in report["cases"] if row["id"] == "random-default")
        report["default_case_consistent"] = default.get("sample_sha256") == baseline_hashes
        report["measurement_complete"] = True
    finally:
        report["inputs_unchanged"] = (
            case_path.read_bytes() == raw
            and hashlib.sha256(executable.read_bytes()).hexdigest() == executable_hash
            and all(hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
                    for name, digest in baseline_hashes.items())
            and all(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
                    for name, digest in source_inputs.items()))
        report["passed"] = (report["measurement_complete"] and report["inputs_unchanged"]
                            and report["default_case_consistent"]
                            and all(row["passed"] for row in report["cases"]))
        save()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-156", "source-148", "fdlibm-object", "vs-installation", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    try:
        report = verify(parser.parse_args())
    except (OSError, ValueError, AssertionError, subprocess.SubprocessError) as error:
        print(f"DSP matrix failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"passed": report["passed"], "cases": len(report["cases"]),
                      "failures": [row["id"] for row in report["cases"] if not row["passed"]],
                      "native156_runtime_verified": False, "production_admitted": False}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
