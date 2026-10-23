import hashlib
import json
import stat
import subprocess
import zipfile

import pytest

from scripts import native_windows_sdk as sdk


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
