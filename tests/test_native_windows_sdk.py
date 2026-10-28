import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import zipfile

import pytest

from scripts import native_windows_sdk as sdk


@pytest.fixture
def local_toolchain_fixture(tmp_path):
    from scripts import native_build as build

    workspace = tmp_path / "workspace"
    root = workspace / "toolchain/local"
    sdk_root = root / "Windows Kits/10"
    vc = root / "VC"
    version = "14.51.12345"
    spec = json.loads((build.ROOT / "native/toolchain/windows-sdk-28000.json").read_text(encoding="utf-8"))

    def put(path, content=b"owned input"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    put(vc / "Auxiliary/Build/Microsoft.VCToolsVersion.default.txt", version.encode())
    for name in build.WINDOWS_DIA_FILES:
        put(root / "DIA SDK" / name)
    for cpu in ("x86", "x64"):
        (vc / "Redist/MSVC" / version / cpu / "Microsoft.VC145.CRT").mkdir(parents=True)
        for name in ("cl.exe", "link.exe"):
            put(vc / "Tools/MSVC" / version / "bin/Hostx64" / cpu / name)
    entries = []
    for relative in ("Include/10.0.28000.0/um/Windows.h", "Lib/10.0.28000.0/um/x64/kernel32.lib"):
        path = put(sdk_root / relative)
        entries.append({"path": relative, "sha256": sdk.sha256(path)})
    debuggers = []
    for cpu in ("x86", "x64"):
        for name in ("dbghelp.dll", "dbgcore.dll", "symsrv.dll"):
            relative = f"Debuggers/{cpu}/{name}"
            path = put(sdk_root / relative)
            debuggers.append({"path": relative, "sha256": sdk.sha256(path)})
    for name in ("SetEnv.cmd", "SetEnv.x86.json", "SetEnv.x64.json"):
        put(sdk_root / "bin" / name)
    provenance = {"layout_verified": True, "sdk_package_version": spec["version"],
                  "packages": [{"package": p["package"], "sha256": p["sha256"]} for p in spec["packages"]],
                  "files": entries, "debuggers": debuggers}
    put(sdk_root / "glint-sdk-provenance.json", json.dumps(provenance).encode())
    config = {"path": str(root), "version": "2026", "win_sdk": str(sdk_root), "wdk": "",
              "runtime_dirs": [str(vc / "Redist/MSVC" / version / cpu / "Microsoft.VC145.CRT")
                               for cpu in ("x64", "x86")] + ["Arm64Unused"]}
    put(workspace / "chromium/src/build/win_toolchain.json", json.dumps(config).encode())
    return workspace, sdk_root, vc, config, provenance


@pytest.mark.skipif(os.name != "nt", reason="Windows local toolchain environment")
@pytest.mark.parametrize("mutation", [None, "sdk-file", "package", "missing-files", "duplicate", "escape",
                                     "missing-script", "sdk-path", "runtime", "version", "dia-header", "dia-library", "dia-runtime"])
def test_local_toolchain_validates_owned_layout_and_every_recorded_sdk_input(local_toolchain_fixture, mutation):
    from scripts import native_build as build

    workspace, sdk_root, vc, config, provenance = local_toolchain_fixture
    if mutation == "sdk-file":
        (sdk_root / provenance["files"][0]["path"]).write_bytes(b"changed SDK")
    elif mutation == "package":
        provenance["packages"][0]["sha256"] = "f" * 64
    elif mutation == "missing-files":
        provenance["files"] = []
    elif mutation == "duplicate":
        provenance["files"].append(dict(provenance["files"][0]))
    elif mutation == "escape":
        path = sdk_root.parent / "outside"
        path.write_bytes(b"outside")
        provenance["files"][0] = {"path": "../outside", "sha256": sdk.sha256(path)}
    elif mutation == "missing-script":
        (sdk_root / "bin/SetEnv.cmd").unlink()
    elif mutation == "sdk-path":
        config["win_sdk"] = str(sdk_root.parent)
    elif mutation == "runtime":
        config["runtime_dirs"].reverse()
    elif mutation == "version":
        config["version"] = "2022"
    elif mutation in ("dia-header", "dia-library", "dia-runtime"):
        relative = {"dia-header": "include/dia2.h", "dia-library": "lib/amd64/diaguids.lib",
                    "dia-runtime": "bin/amd64/msdia140.dll"}[mutation]
        (vc.parent / "DIA SDK" / relative).unlink()
    (workspace / "chromium/src/build/win_toolchain.json").write_text(json.dumps(config), encoding="utf-8")
    (sdk_root / "glint-sdk-provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    if mutation:
        with pytest.raises(ValueError):
            build.environment(workspace, local_toolchain=True)
        assert not (workspace / "tmp").exists() and not (workspace / "build.gitconfig").exists()
    else:
        before = dict(os.environ)
        selected = build.environment(workspace, local_toolchain=True)
        assert selected["DEPOT_TOOLS_WIN_TOOLCHAIN"] == "1"
        assert selected["WINDOWSSDKDIR"] == str(sdk_root)
        assert selected["vs2026_install"] == str(vc.parent)
        assert len(selected["GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256"]) == 64
        assert dict(os.environ) == before
        assert build.environment(workspace)["DEPOT_TOOLS_WIN_TOOLCHAIN"] == "0"
        assert build.local_windows_toolchain(workspace)["GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256"] == selected["GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256"]


@pytest.mark.skipif(os.name != "nt", reason="Windows local toolchain environment")
@pytest.mark.parametrize("input_name", ["SetEnv.cmd", "SetEnv.x64.json", "cl.exe", "dia2.h", "diaguids.lib", "msdia140.dll"])
def test_local_toolchain_snapshot_detects_environment_and_compiler_drift(local_toolchain_fixture, input_name):
    from scripts import native_build as build

    workspace, sdk_root, vc, _, _ = local_toolchain_fixture
    before = build.local_windows_toolchain(workspace)["GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256"]
    path = (vc / "Tools/MSVC/14.51.12345/bin/Hostx64/x64/cl.exe" if input_name == "cl.exe"
            else sdk_root / "bin" / input_name)
    if input_name in ("dia2.h", "diaguids.lib", "msdia140.dll"):
        relative = {"dia2.h": "include/dia2.h", "diaguids.lib": "lib/amd64/diaguids.lib",
                    "msdia140.dll": "bin/amd64/msdia140.dll"}[input_name]
        path = vc.parent / "DIA SDK" / relative
    path.write_bytes(b"changed toolchain input")
    assert build.local_windows_toolchain(workspace)["GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256"] != before


@pytest.mark.skipif(os.name != "nt", reason="Windows junction regression")
def test_local_toolchain_rejects_vc_junction_before_environment_changes(local_toolchain_fixture):
    import _winapi
    from scripts import native_build as build

    workspace, _, vc, _, _ = local_toolchain_fixture
    original = workspace / "installed-VC"
    vc.rename(original)
    _winapi.CreateJunction(str(original), str(vc))
    assert vc.is_junction()
    try:
        with pytest.raises(ValueError, match="materialized without junctions"):
            build.environment(workspace, local_toolchain=True)
        assert not (workspace / "tmp").exists()
        assert not (workspace / "build.gitconfig").exists()
        assert (original / "Auxiliary/Build/Microsoft.VCToolsVersion.default.txt").read_text() == "14.51.12345"
    finally:
        vc.rmdir()


@pytest.mark.parametrize("action,candidate", [("hooks", "upstream-156"), ("sync", "upstream-156"),
                                           ("preflight", "upstream-156"), ("build", None)])
def test_local_toolchain_is_never_an_implicit_sdk_fallback(tmp_path, action, candidate):
    from scripts import native_build as build

    workspace = tmp_path / "not-created"
    with pytest.raises(ValueError, match="explicit.*candidate build"):
        build.execute(action, workspace, candidate_name=candidate, local_toolchain=True)
    assert not workspace.exists()


def test_build_script_sdk_import_works_without_project_on_pythonpath(tmp_path):
    from scripts import native_build as build

    script = """import runpy,sys
from pathlib import Path
module = runpy.run_path(sys.argv[1])
try:
    module['local_windows_toolchain'](Path(sys.argv[2]))
except ValueError as error:
    assert 'Windows' in str(error) or 'win_toolchain.json' in str(error), str(error)
else:
    raise AssertionError('An unprepared toolchain must not be accepted')
"""
    result = subprocess.run([sys.executable, "-I", "-c", script, str(build.ROOT / "scripts/native_build.py"), str(tmp_path)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture
def toolchain_preparation_fixture(local_toolchain_fixture, monkeypatch):
    from scripts import native_build as build
    from scripts import native_windows_toolchain as prep

    workspace, sdk_root, vc, _, _ = local_toolchain_fixture
    (workspace / "chromium/src/build/win_toolchain.json").unlink()
    candidate = build.load_candidate("upstream-156")
    (workspace / "glint-build-candidate.json").write_text(json.dumps({
        "schema": 1, "candidate": candidate["name"], "chromium_revision": candidate["lock"]["chromium_revision"],
    }), encoding="utf-8")
    monkeypatch.setattr(prep, "APPROVED_DRIVE", workspace.drive.upper())
    for name in ("SetEnv.cmd", "SetEnv.x86.json", "SetEnv.x64.json"):
        (sdk_root / "bin" / name).unlink()
    directories = [vc / "Tools/MSVC/14.51.12345/include", sdk_root / "bin/10.0.28000.0/x64",
                   sdk_root / "UnionMetadata/10.0.28000.0", sdk_root / "References/10.0.28000.0"]
    directories += [sdk_root / "Include/10.0.28000.0" / name for name in ("ucrt", "shared", "um", "winrt", "cppwinrt")]
    for cpu in ("x86", "x64"):
        directories += [vc / "Tools/MSVC/14.51.12345/lib" / cpu,
                        sdk_root / "Lib/10.0.28000.0/ucrt" / cpu, sdk_root / "Lib/10.0.28000.0/um" / cpu]
    for path in directories:
        path.mkdir(parents=True, exist_ok=True)
    return workspace, vc.parent, sdk_root, workspace / "toolchain/prepared"


@pytest.mark.skipif(os.name != "nt", reason="Windows toolchain preparation")
def test_prepares_materialized_toolchain_with_exact_environment_and_provenance(toolchain_preparation_fixture):
    from scripts import native_build as build
    from scripts import native_windows_toolchain as prep

    workspace, installation, sdk_root, output = toolchain_preparation_fixture
    original_version = installation / "VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt"
    before = original_version.read_bytes()
    report = prep.prepare(workspace, installation, sdk_root, output, candidate_name="upstream-156")
    assert report["layout_verified"] and not report["compiled"] and not report["runtime_verified"]
    assert build.local_windows_toolchain(workspace)["GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256"] == report["toolchain_sha256"]
    assert original_version.read_bytes() == before
    assert not (output / "VC").is_junction()
    for cpu in ("x86", "x64"):
        env = json.loads((output / "Windows Kits/10/bin" / f"SetEnv.{cpu}.json").read_text(encoding="utf-8"))["env"]
        assert env["VSINSTALLDIR"] == [[str(output)]]
        assert env["INCLUDE"][0] == [str(output / "VC/Tools/MSVC/14.51.12345/include")]
        assert env["PATH"][0] == [str(output / "VC/Tools/MSVC/14.51.12345/bin/Hostx64" / cpu)]
    assert all(sdk.sha256(output / row["path"]) == row["sha256"] for row in report["files"])
    assert not (output / "glint-toolchain-provenance.json").read_bytes().startswith(b"\xef\xbb\xbf")


@pytest.mark.skipif(os.name != "nt", reason="Windows toolchain preparation")
@pytest.mark.parametrize("mutation", ["existing-config", "existing-output", "sdk-changed", "prepared-sdk", "version", "candidate", "low-space", "missing-dia"])
def test_toolchain_preparation_rejects_invalid_inputs_without_replacing_config(toolchain_preparation_fixture, monkeypatch, mutation):
    from scripts import native_windows_toolchain as prep

    workspace, installation, sdk_root, output = toolchain_preparation_fixture
    config = workspace / "chromium/src/build/win_toolchain.json"
    if mutation == "existing-config":
        config.write_bytes(b"user config")
    elif mutation == "existing-output":
        output.mkdir()
        (output / "keep").write_bytes(b"user file")
    elif mutation == "sdk-changed":
        (sdk_root / "Include/10.0.28000.0/um/Windows.h").write_bytes(b"changed SDK")
    elif mutation == "prepared-sdk":
        (sdk_root / "bin/SetEnv.cmd").write_bytes(b"existing environment")
    elif mutation == "version":
        (installation / "VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt").write_bytes(b"14.44.1")
    elif mutation == "missing-dia":
        (installation / "DIA SDK/include/dia2.h").unlink()
    elif mutation == "candidate":
        (workspace / "glint-build-candidate.json").write_text("{}", encoding="utf-8")
    elif mutation == "low-space":
        from collections import namedtuple
        usage = namedtuple("usage", "total used free")
        monkeypatch.setattr(prep.shutil, "disk_usage", lambda _: usage(100, 99, 1))
    with pytest.raises(ValueError):
        prep.prepare(workspace, installation, sdk_root, output, candidate_name="upstream-156")
    assert config.read_bytes() == b"user config" if mutation == "existing-config" else not config.exists()
    if mutation == "existing-output":
        assert (output / "keep").read_bytes() == b"user file"
    if mutation == "sdk-changed":
        assert not json.loads((output / "glint-toolchain-provenance.json").read_text())["layout_verified"]


@pytest.mark.skipif(os.name != "nt", reason="Windows toolchain preparation")
@pytest.mark.parametrize("failure", ["copy-drift", "final-drift", "foreign-config", "foreign-config-no-error", "locked"])
def test_toolchain_preparation_retains_failed_evidence_and_foreign_edits(toolchain_preparation_fixture, monkeypatch, failure):
    from contextlib import nullcontext
    from scripts import native_build as build
    from scripts import native_windows_toolchain as prep

    workspace, installation, sdk_root, output = toolchain_preparation_fixture
    config = workspace / "chromium/src/build/win_toolchain.json"
    if failure == "copy-drift":
        original = prep.shutil.copy2
        def copy_then_mutate(source, target):
            result = original(source, target)
            if Path(source).name == "Windows.h":
                Path(source).write_bytes(b"changed during copy")
            return result
        monkeypatch.setattr(prep.shutil, "copy2", copy_then_mutate)
    elif failure in ("final-drift", "foreign-config", "foreign-config-no-error"):
        original = build.local_windows_toolchain
        def mutate_after_validation(path):
            result = original(path)
            if failure == "final-drift":
                (output / "VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt").write_bytes(b"changed after copy")
            else:
                config.write_bytes(b"concurrent user config")
                if failure == "foreign-config":
                    raise ValueError("concurrent config edit")
            return result
        monkeypatch.setattr(build, "local_windows_toolchain", mutate_after_validation)
    with build.workspace_lock(workspace) if failure == "locked" else nullcontext():
        with pytest.raises(ValueError):
            prep.prepare(workspace, installation, sdk_root, output, candidate_name="upstream-156")
    if failure.startswith("foreign-config"):
        assert config.read_bytes() == b"concurrent user config"
    else:
        assert not config.exists()
    if failure == "locked":
        assert not output.exists()
    else:
        assert not json.loads((output / "glint-toolchain-provenance.json").read_text())["layout_verified"]


@pytest.mark.skipif(os.name != "nt", reason="Windows toolchain preparation")
@pytest.mark.parametrize("limit", ["bytes", "files"])
def test_toolchain_preparation_enforces_materialization_bounds(toolchain_preparation_fixture, monkeypatch, limit):
    from scripts import native_windows_toolchain as prep

    workspace, installation, sdk_root, output = toolchain_preparation_fixture
    monkeypatch.setattr(prep, "MAX_BYTES" if limit == "bytes" else "MAX_FILES", 1)
    with pytest.raises(ValueError, match="size/file bound"):
        prep.prepare(workspace, installation, sdk_root, output, candidate_name="upstream-156")
    assert not (workspace / "chromium/src/build/win_toolchain.json").exists()
    assert not json.loads((output / "glint-toolchain-provenance.json").read_text())["layout_verified"]


def test_toolchain_preparation_cli_works_from_an_external_directory(tmp_path):
    from scripts import native_windows_toolchain as prep

    result = subprocess.run([sys.executable, "-I", str(prep.ROOT / "scripts/native_windows_toolchain.py"), "--help"],
                            cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "--candidate {upstream-156}" in result.stdout
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("name", ["c/../escape", "c/a/../../escape", "c/a\\escape", "c/D:escape", "c//empty", "c/./dot", "/c/absolute"])
def test_rejects_unsafe_archive_paths(name):
    with pytest.raises(ValueError, match="Unsafe"):
        sdk.sdk_relative_path(name, common=True, version="10.0.28000.0")


def test_maps_architecture_libraries_without_changing_version():
    assert sdk.sdk_relative_path("c/um/x64/kernel32.Lib", common=False, version="10.0.28000.0").as_posix() == "Lib/10.0.28000.0/um/x64/kernel32.Lib"
    assert sdk.sdk_relative_path("c/Include/10.0.28000.0/um/Windows.h", common=True, version="10.0.28000.0").as_posix() == "Include/10.0.28000.0/um/Windows.h"
    with pytest.raises(ValueError, match="architecture"):
        sdk.sdk_relative_path("c/Include/old.h", common=False, version="10.0.28000.0")


def test_extraction_retains_exact_bytes_and_provenance(tmp_path):
    archive = tmp_path / "package.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("c/um/x64/kernel32.Lib", b"measured fixture bytes")
        stream.writestr("package/metadata", b"not part of the SDK")
    output = tmp_path / "sdk"
    output.mkdir()
    files, remaining = sdk.extract_package(archive, output, common=False, version="10.0.28000.0", remaining=1024)
    assert files == [{"path": "Lib/10.0.28000.0/um/x64/kernel32.Lib", "archive_path": "c/um/x64/kernel32.Lib",
                      "sha256": hashlib.sha256(b"measured fixture bytes").hexdigest()}]
    assert (output / files[0]["path"]).read_bytes() == b"measured fixture bytes"
    assert remaining == 1024 - len(b"measured fixture bytes")
    assert not (output / "package").exists()


@pytest.mark.parametrize("kind", ["link", "traversal", "size", "collision"])
def test_extraction_rejects_unsafe_or_conflicting_entries(tmp_path, kind):
    archive = tmp_path / "package.zip"
    output = tmp_path / "sdk"
    output.mkdir()
    with zipfile.ZipFile(archive, "w") as stream:
        if kind == "link":
            entry = zipfile.ZipInfo("c/link")
            entry.create_system = 3
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            stream.writestr(entry, "outside")
        elif kind == "traversal":
            stream.writestr("c/../escape", b"escape")
        else:
            stream.writestr("c/fixture", b"original")
            if kind == "collision":
                (output / "fixture").write_bytes(b"keep")
    with pytest.raises(ValueError):
        sdk.extract_package(archive, output, common=True, version="10.0.28000.0", remaining=1 if kind == "size" else 1024)
    assert not (tmp_path / "escape").exists()
    if kind == "collision":
        assert (output / "fixture").read_bytes() == b"keep"


def test_existing_output_is_never_overwritten(tmp_path):
    packages = tmp_path / "packages"
    debuggers = tmp_path / "debuggers"
    output = tmp_path / "sdk"
    for path in (packages, debuggers, output):
        path.mkdir()
    marker = output / "keep"
    marker.write_bytes(b"existing SDK")
    with pytest.raises(ValueError, match="new, external"):
        sdk.validate_inputs(packages, output, debuggers)
    assert marker.read_bytes() == b"existing SDK"


def test_rejects_output_nested_in_package_input(tmp_path):
    packages = tmp_path / "packages"
    debuggers = tmp_path / "debuggers"
    packages.mkdir()
    debuggers.mkdir()
    with pytest.raises(ValueError, match="new, external"):
        sdk.validate_inputs(packages, packages / "output", debuggers)


def test_pinned_packages_are_version_coherent_and_microsoft_hosted():
    spec = json.loads(sdk.SPEC.read_text(encoding="utf-8"))
    assert spec["version"] == "10.0.28000.2270"
    assert spec["directory_version"] == "10.0.28000.0"
    assert {row["package"] for row in spec["packages"]} == {
        "Microsoft.Windows.SDK.CPP", "Microsoft.Windows.SDK.CPP.x64",
        "Microsoft.Windows.SDK.CPP.x86", "Microsoft.Windows.SDK.CPP.arm64",
    }
    for row in spec["packages"]:
        assert row["url"].startswith("https://api.nuget.org/v3-flatcontainer/")
        assert "/" + spec["version"] + "/" in row["url"]
        assert len(bytes.fromhex(row["sha256"])) == 32
        assert row["bytes"] > 0


@pytest.fixture
def assembly_fixture(tmp_path, monkeypatch):
    packages = tmp_path / "packages"
    packages.mkdir()
    archive = packages / "fixture.nupkg"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("c/fixture.exe", b"must not execute")
    spec = {"version": "test", "directory_version": "test", "minimum_debugger_version": "10.0.26100.3323",
            "repository_signer_sha256": "ab" * 32,
            "packages": [{"package": "Microsoft.Windows.SDK.CPP", "url": "https://api.nuget.org/fixture.nupkg",
                          "sha256": sdk.sha256(archive), "bytes": archive.stat().st_size}]}
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    monkeypatch.setattr(sdk, "SPEC", path)
    monkeypatch.setattr(sdk, "validate_inputs", lambda *args: None)
    monkeypatch.setattr(sdk.sys, "platform", "win32")
    monkeypatch.setattr(sdk.shutil, "which", lambda _: "dotnet")
    monkeypatch.setattr(sdk, "verify_debugger", lambda *args: {"sha256": "unused until copy"})
    return packages, tmp_path / "output", tmp_path / "debuggers", archive


def test_rejects_changed_package_before_creating_output(assembly_fixture):
    packages, output, debuggers, archive = assembly_fixture
    archive.write_bytes(b"changed bytes")
    with pytest.raises(ValueError, match="changed pinned"):
        sdk.assemble(packages, output, debuggers)
    assert not output.exists()


def test_signature_failure_never_extracts_tools(assembly_fixture, monkeypatch):
    packages, output, debuggers, _ = assembly_fixture
    monkeypatch.setattr(sdk.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, b"signature rejected", b""))
    with pytest.raises(ValueError, match="signature verification failed"):
        sdk.assemble(packages, output, debuggers)
    report = json.loads((output / "glint-sdk-provenance.json").read_text(encoding="utf-8"))
    assert report["layout_verified"] is False
    assert report["compiled"] is False
    assert report["files"] == []
    assert not (output / "fixture.exe").exists()
    assert 'allowUntrustedRoot="false"' in (output / "NuGet.Config").read_text(encoding="utf-8")


def test_package_mutation_after_verification_is_rejected(assembly_fixture, monkeypatch):
    packages, output, debuggers, archive = assembly_fixture

    def mutate(command, **kwargs):
        archive.write_bytes(b"changed during verification")
        return subprocess.CompletedProcess(command, 0, b"fixture signature accepted", b"")

    monkeypatch.setattr(sdk.subprocess, "run", mutate)
    with pytest.raises(ValueError, match="changed during signature"):
        sdk.assemble(packages, output, debuggers)
    report = json.loads((output / "glint-sdk-provenance.json").read_text(encoding="utf-8"))
    assert report["layout_verified"] is False
    assert not (output / "fixture.exe").exists()


@pytest.mark.parametrize("status,version", [("NotSigned", "10.0.26100.7705"), ("HashMismatch", "10.0.26100.7705"), ("Valid", "10.0.26100.1")])
def test_debugger_signature_and_minimum_version_are_required(tmp_path, monkeypatch, status, version):
    path = tmp_path / "dbghelp.dll"
    path.write_bytes(b"debugger fixture")
    result = subprocess.CompletedProcess([], 0, json.dumps({"Status": status, "Version": version}), "")
    monkeypatch.setattr(sdk.subprocess, "run", lambda *args, **kwargs: result)
    with pytest.raises(ValueError, match="signature or servicing"):
        sdk.verify_debugger(path, "10.0.26100.3323")
