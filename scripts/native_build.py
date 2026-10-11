"""Pinned Chromium checkout/build. Large downloads stay in an owned workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "native/build-lock.json").read_text(encoding="utf-8-sig"))


def run(args: list[str], cwd: Path, env: dict[str, str], *, capture: bool = False) -> str:
    result = subprocess.run(args, cwd=cwd, env=env, check=True, text=True,
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else ""


def preflight(workspace: Path, *, backing_volume: Path | None = None) -> dict:
    if not workspace.is_absolute() or workspace != workspace.resolve():
        raise ValueError("Build workspace must be absolute and must not contain links")
    if workspace == ROOT or workspace.is_relative_to(ROOT):
        raise ValueError("Chromium checkout must stay outside the application repository")
    if os.name == "nt" and workspace.drive.upper() != "D:":
        raise ValueError("This Windows build must use the approved D: workspace")
    if shutil.which("git") is None:
        raise ValueError("Git is required")
    ancestor = workspace
    while not ancestor.exists():
        if ancestor.parent == ancestor:
            raise ValueError("Build workspace has no existing filesystem root")
        ancestor = ancestor.parent
    free = shutil.disk_usage(ancestor).free / (1024 ** 3)
    backing = {}
    if backing_volume is not None:
        if not backing_volume.is_absolute() or backing_volume != backing_volume.resolve() or not backing_volume.is_dir():
            raise ValueError("Backing volume must be an existing absolute directory without links")
        backing_free = shutil.disk_usage(backing_volume).free / (1024 ** 3)
        backing = {"backing_volume": str(backing_volume), "workspace_free_gib": round(free, 1),
                   "backing_free_gib": round(backing_free, 1)}
        free = min(free, backing_free)
    if free < LOCK["minimum_free_gib"]:
        raise ValueError(f"Need at least {LOCK['minimum_free_gib']} GiB free; found {free:.1f}")
    return {"workspace": str(workspace), "free_gib": round(free, 1),
            "cpu_count": os.cpu_count(), "chromium_revision": LOCK["chromium_revision"],
            "depot_tools_revision": LOCK["depot_tools_revision"], **backing}


def environment(workspace: Path) -> dict[str, str]:
    env = dict(os.environ)
    temporary = workspace / "tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    git_config = workspace / "build.gitconfig"
    if git_config.is_symlink() or git_config != git_config.resolve():
        raise ValueError("Build Git configuration must remain in the owned workspace")
    if not git_config.exists():
        git_config.write_text("[depot-tools]\nallowGlobalGitConfig = false\n", encoding="utf-8")
    env.update({"DEPOT_TOOLS_UPDATE": "0", "DEPOT_TOOLS_WIN_TOOLCHAIN": "0", "DEPOT_TOOLS_METRICS": "0",
                "CIPD_CACHE_DIR": str(workspace / "cipd-cache"),
                "VPYTHON_VIRTUALENV_ROOT": str(workspace / "vpython-cache"),
                "GIT_CONFIG_GLOBAL": str(git_config),
                "TEMP": str(temporary), "TMP": str(temporary), "TMPDIR": str(temporary),
                "PATH": str(workspace / "depot_tools") + os.pathsep + env.get("PATH", "")})
    if os.name == "nt":
        sdk_python = workspace / "depot_tools/.cipd_bin/3.11/bin/python3.exe"
        if sdk_python.is_file():
            env["PATH"] = str(sdk_python.parent) + os.pathsep + env["PATH"]
        count = int(env.get("GIT_CONFIG_COUNT", "0"))
        env.update({"GIT_CONFIG_COUNT": str(count + 1),
                    f"GIT_CONFIG_KEY_{count}": "http.sslBackend",
                    f"GIT_CONFIG_VALUE_{count}": "openssl"})
        vpython = workspace / "depot_tools/.cipd_bin/vpython3.exe"
        if vpython.is_file():
            launchers = workspace / "tool-launchers"
            if launchers != launchers.resolve():
                raise ValueError("Build tool launchers must not contain links")
            launchers.mkdir(exist_ok=True)
            launcher = launchers / "vpython3.bat"
            contents = f'@echo off\n"{vpython}" %*\n'
            if launcher.is_symlink() or (launcher.exists() and launcher.read_text(encoding="utf-8-sig") != contents):
                raise ValueError("Refusing to overwrite an unrelated vpython launcher")
            launcher.write_text(contents, encoding="utf-8")
            env["PATH"] = str(launchers) + os.pathsep + env["PATH"]
    return env


def checkout(path: Path, repository: str, revision: str, env: dict[str, str]) -> None:
    if path != path.resolve():
        raise ValueError(f"Checkout must not contain links: {path}")
    if not (path / ".git").exists():
        if path.exists() and any(path.iterdir()):
            raise ValueError(f"Refusing to reuse an unrelated directory: {path}")
        path.mkdir(parents=True, exist_ok=True)
        run(["git", "init", str(path)], path.parent, env)
        run(["git", "remote", "add", "origin", repository], path, env)
    if run(["git", "remote", "get-url", "origin"], path, env, capture=True) != repository:
        raise ValueError(f"Unexpected Git origin in {path}")
    run(["git", "config", "core.autocrlf", "false"], path, env)
    run(["git", "config", "core.longpaths", "true"], path, env)
    if run(["git", "status", "--porcelain"], path, env, capture=True):
        raise ValueError(f"Uncommitted source changes in {path}; refusing to overwrite")
    current = subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, env=env,
                             capture_output=True, text=True, check=False)
    if current.returncode != 0 or current.stdout.strip() != revision:
        run(["git", "-c", "protocol.version=2", "fetch", "--depth=1", "--no-tags", "origin", revision], path, env)
        run(["git", "checkout", "--detach", revision], path, env)
    if run(["git", "rev-parse", "HEAD"], path, env, capture=True) != revision:
        raise ValueError("Source revision verification failed")


def depot_command(name: str, workspace: Path) -> list[str]:
    if os.name == "nt" and name in {"gn", "autoninja"}:
        python = workspace / "depot_tools/.cipd_bin/3.11/bin/python3.exe"
        if not python.is_file():
            raise ValueError("Bootstrap the pinned depot_tools Python package first")
        return [str(python), str(workspace / "depot_tools" / (name + ".py"))]
    if os.name == "nt" and name == "cipd":
        client = workspace / "depot_tools/.cipd_client.exe"
        if not client.is_file():
            raise ValueError("Bootstrap the pinned CIPD client first")
        return [str(client)]
    if os.name == "nt" and name == "gclient":
        vpython = workspace / "depot_tools/.cipd_bin/vpython3.exe"
        if not vpython.is_file():
            raise ValueError("Bootstrap the pinned depot_tools vpython package first")
        return [str(vpython), str(workspace / "depot_tools/gclient.py")]
    tool = workspace / "depot_tools" / (name + ".bat" if os.name == "nt" else name)
    return ["cmd.exe", "/d", "/c", str(tool)] if os.name == "nt" else [str(tool)]


def bootstrap_windows_git(workspace: Path, env: dict[str, str]) -> None:
    script = ("import runpy,sys; m=runpy.run_path(sys.argv[1]); "
              "i=m['search_win_git_directory'](); "
              "assert i is not None, 'Git installation not found'; "
              "t=m['Template'].empty()._replace(GIT_PATH_PREPEND=i.path_prepend, "
              "GIT_BASH_EXE=i.bash_exe, GIT_BASH_LAUNCHER=i.bash_launcher); "
              "m['git_postprocess'](t,i)")
    run([sys.executable, "-c", script, str(workspace / "depot_tools/bootstrap/bootstrap.py")], workspace, env)


def source_patches(source: Path, env: dict[str, str]) -> list[dict[str, str]]:
    changed = set(run(["git", "diff", "HEAD", "--name-only"], source, env, capture=True).splitlines())
    changed.update(run(["git", "ls-files", "--others", "--exclude-standard"], source, env, capture=True).splitlines())
    if not changed:
        return []
    patches = []
    expected = set()
    for name in ("0001-native-hardware-privacy-limits.patch", "0002-midl-locale-name-hashes.patch",
                 "0003-native-webrtc-routing-policy.patch", "0004-native-automation-exposure.patch"):
        patch = ROOT / "native/patches" / name
        contents = patch.read_text(encoding="utf-8-sig")
        files = {line.split(" b/", 1)[1] for line in contents.splitlines() if line.startswith("diff --git ")}
        if changed.intersection(files):
            expected.update(files)
            patches.append(patch)
    if changed != expected:
        raise ValueError("Unrecognized Chromium source changes; refusing an unrepeatable build")
    with tempfile.TemporaryDirectory(prefix="native-patch-index-", dir=source.parent) as owned:
        index_env = {**env, "GIT_INDEX_FILE": str(Path(owned) / "index")}
        run(["git", "read-tree", "--empty"], source, index_env)
        baseline = run(["git", "ls-tree", "HEAD", "--", *sorted(expected)], source, index_env, capture=True)
        for entry in baseline.splitlines():
            metadata, path = entry.split("\t", 1)
            mode, kind, blob = metadata.split()
            if kind != "blob":
                raise ValueError("Native patches must only change ordinary source files")
            run(["git", "update-index", "--add", "--cacheinfo", mode + "," + blob + "," + path], source, index_env)
        for patch in patches:
            run(["git", "apply", "--cached", str(patch)], source, index_env)
        run(["git", "diff", "--exit-code", "--", *sorted(expected)], source, index_env)
    return [{"name": patch.name, "sha256": hashlib.sha256(patch.read_bytes()).hexdigest()} for patch in patches]


def stage_identity(chromium: Path, stage: str) -> dict:
    return {"schema": 1, "stage": stage, "platform": sys.platform,
            "chromium_revision": LOCK["chromium_revision"],
            "depot_tools_revision": LOCK["depot_tools_revision"],
            "deps_sha256": hashlib.sha256((chromium / "src/DEPS").read_bytes()).hexdigest(),
            "gclient_sha256": hashlib.sha256((chromium / ".gclient").read_bytes()).hexdigest(),
            "dependency_snapshots_sha256": {
                name: hashlib.sha256((chromium / name).read_bytes()).hexdigest()
                for name in ("camouflow-git-revisions.json", "camouflow-cipd-installed.json")}}


def snapshot_dependencies(chromium: Path, workspace: Path, env: dict[str, str]) -> None:
    git_snapshot = chromium / "camouflow-git-revisions.json"
    cipd_snapshot = chromium / "camouflow-cipd-installed.json"
    for target in (git_snapshot, cipd_snapshot):
        if target != target.resolve():
            raise ValueError("Dependency snapshots must not contain links")
    run(depot_command("gclient", workspace) + ["revinfo", "-a", "--ignore-dep-type", "cipd",
                                             "--output-json", str(git_snapshot)], chromium, env)
    run(depot_command("cipd", workspace) + ["installed", "-root", str(chromium),
                                           "-json-output", str(cipd_snapshot)], chromium, env)


def check_patch_dependencies(source: Path, env: dict[str, str]) -> None:
    run(["git", "diff", "--check"], source, env)
    for directory in ("third_party/blink/renderer/core/frame", "content/browser/renderer_host"):
        run([sys.executable, str(source / "buildtools/checkdeps/checkdeps.py"),
             "--root", os.path.normcase(str(source)), os.path.normcase(str(source / directory))], source, env)
    script = ("import sys; from pathlib import Path; "
              "root=Path(sys.argv[1]); sys.path.insert(0,str(root/'buildtools/checkdeps')); "
              "from checkdeps import DepsChecker; "
              "file=root/'chrome/browser/renderer_preferences_util.cc'; "
              "problems=DepsChecker(str(root)).CheckAddedCppIncludes([(str(file),file.read_text(encoding='utf-8-sig').splitlines())]); "
              "print(problems); sys.exit(bool(problems))")
    run([sys.executable, "-c", script, os.path.normcase(str(source))], source, env)


def stage_path(chromium: Path, stage: str) -> Path:
    if stage not in {"sync", "hooks"}:
        raise ValueError("Unknown Native build stage")
    target = chromium / f"camouflow-{stage}.json"
    if chromium != chromium.resolve() or target.is_symlink() or target != target.resolve():
        raise ValueError("Native build stage records must not contain links")
    return target


def record_stage(chromium: Path, stage: str) -> None:
    target = stage_path(chromium, stage)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=chromium,
                                         prefix=f"camouflow-{stage}-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(stage_identity(chromium, stage), stream, indent=2)
        temporary.replace(target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def require_stage(chromium: Path, stage: str) -> None:
    target = stage_path(chromium, stage)
    if not target.is_file():
        raise ValueError(f"Run {stage} to successful completion before the next build stage")
    try:
        identity = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        raise ValueError(f"Invalid Native {stage} stage record") from error
    if identity != stage_identity(chromium, stage):
        raise ValueError(f"Native {stage} inputs changed; rerun that stage")


def execute(action: str, workspace: Path, *, backing_volume: Path | None = None, jobs: int | None = None) -> None:
    jobs = LOCK["build_jobs"] if jobs is None else jobs
    if type(jobs) is not int or not 1 <= jobs <= LOCK["build_jobs"]:
        raise ValueError(f"Native jobs must be between 1 and {LOCK['build_jobs']}")
    print(json.dumps(preflight(workspace, backing_volume=backing_volume)), flush=True)
    if action == "preflight":
        return
    workspace.mkdir(parents=True, exist_ok=True)
    env = environment(workspace)
    checkout(workspace / "depot_tools", LOCK["depot_tools_repository"], LOCK["depot_tools_revision"], env)
    if os.name == "nt":
        bootstrap_windows_git(workspace, env)
    if action == "bootstrap":
        launcher = workspace / "depot_tools" / ("gclient.bat" if os.name == "nt" else "gclient")
        command = ["cmd.exe", "/d", "/c", str(launcher)] if os.name == "nt" else [str(launcher)]
        run(command + ["help"], workspace, env)
        return
    chromium = workspace / "chromium"
    chromium.mkdir(exist_ok=True)
    source = chromium / "src"
    if chromium != chromium.resolve() or source != source.resolve():
        raise ValueError("Chromium workspace/source must not contain links")
    if action == "sync":
        for stage in ("sync", "hooks"):
            stage_path(chromium, stage).unlink(missing_ok=True)
        checkout(source, LOCK["chromium_repository"], LOCK["chromium_revision"], env)
        config = ("solutions = " + repr([{"name": "src", "url": LOCK["chromium_repository"],
                   "managed": False, "custom_deps": {}, "custom_vars": {}}]) + "\n")
        config_path = chromium / ".gclient"
        if config_path.exists() and config_path.read_text(encoding="utf-8-sig") != config:
            raise ValueError("Refusing to overwrite an unrelated gclient configuration")
        config_path.write_text(config, encoding="utf-8")
        if os.name == "nt":
            run([depot_command("gclient", workspace)[0], str(workspace / "depot_tools/gsutil.py"), "version"], chromium, env)
        run(depot_command("gclient", workspace) + ["sync", "--no-history", "--nohooks",
            "--revision", "src@" + LOCK["chromium_revision"], "-j", str(jobs)], chromium, env)
        snapshot_dependencies(chromium, workspace, env)
        record_stage(chromium, "sync")
        return
    if not (chromium / ".gclient").is_file() or not (source / "DEPS").is_file():
        raise ValueError("Run sync before hooks/build")
    if run(["git", "rev-parse", "HEAD"], source, env, capture=True) != LOCK["chromium_revision"]:
        raise ValueError("Chromium revision does not match the build lock")
    require_stage(chromium, "sync")
    if action == "hooks":
        stage_path(chromium, "hooks").unlink(missing_ok=True)
        run(depot_command("gclient", workspace) + ["runhooks"], chromium, env)
        record_stage(chromium, "hooks")
        return
    require_stage(chromium, "hooks")
    patches = source_patches(source, env)
    if patches:
        check_patch_dependencies(source, env)
    output = source / "out/CamouFlowNative"
    output.mkdir(parents=True, exist_ok=True)
    output.joinpath("args.gn").write_text((ROOT / "native/args.gn").read_text(encoding="utf-8-sig"), encoding="utf-8")
    run(depot_command("gn", workspace) + ["gen", "out/CamouFlowNative"], source, env)
    run(depot_command("autoninja", workspace) + ["-C", "out/CamouFlowNative", "-j", str(jobs), "chrome"], source, env)
    relative_binary = {"win32": "chrome.exe", "linux": "chrome",
                       "darwin": "Chromium.app/Contents/MacOS/Chromium"}[sys.platform]
    binary = output / relative_binary
    with binary.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    receipt = {"schema": 1, "native_version": LOCK["native_version"],
               "chromium_revision": LOCK["chromium_revision"],
               "depot_tools_revision": LOCK["depot_tools_revision"],
               "platform": sys.platform, "binary": relative_binary, "build_jobs": jobs,
               "binary_sha256_measured": checksum,
               "args_sha256": hashlib.sha256(output.joinpath("args.gn").read_bytes()).hexdigest(),
               "fingerprint_patched": False, "patches": patches,
               "native_patch_runtime_verified": False}
    output.joinpath("camouflow-build.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "bootstrap", "sync", "hooks", "build"))
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--backing-volume", type=Path, help="Also require free space on this backing volume (WSL: /mnt/d)")
    parser.add_argument("--jobs", type=int, choices=range(1, LOCK["build_jobs"] + 1), help="Parallel jobs for sync/build; defaults to the build lock")
    args = parser.parse_args()
    try:
        execute(args.action, args.workspace, backing_volume=args.backing_volume, jobs=args.jobs)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Native build failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
