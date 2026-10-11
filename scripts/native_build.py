"""Pinned Chromium checkout/build. Large downloads stay in an owned workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "native/build-lock.json").read_text(encoding="utf-8-sig"))


def run(args: list[str], cwd: Path, env: dict[str, str], *, capture: bool = False) -> str:
    result = subprocess.run(args, cwd=cwd, env=env, check=True, text=True,
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else ""


def preflight(workspace: Path) -> dict:
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
        ancestor = ancestor.parent
    free = shutil.disk_usage(ancestor).free / (1024 ** 3)
    if free < LOCK["minimum_free_gib"]:
        raise ValueError(f"Need at least {LOCK['minimum_free_gib']} GiB free; found {free:.1f}")
    return {"workspace": str(workspace), "free_gib": round(free, 1),
            "cpu_count": os.cpu_count(), "chromium_revision": LOCK["chromium_revision"],
            "depot_tools_revision": LOCK["depot_tools_revision"]}


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
        count = int(env.get("GIT_CONFIG_COUNT", "0"))
        env.update({"GIT_CONFIG_COUNT": str(count + 1),
                    f"GIT_CONFIG_KEY_{count}": "http.sslBackend",
                    f"GIT_CONFIG_VALUE_{count}": "openssl"})
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
                             capture_output=True, text=True)
    if current.returncode != 0 or current.stdout.strip() != revision:
        run(["git", "-c", "protocol.version=2", "fetch", "--depth=1", "--no-tags", "origin", revision], path, env)
        run(["git", "checkout", "--detach", revision], path, env)
    if run(["git", "rev-parse", "HEAD"], path, env, capture=True) != revision:
        raise ValueError("Source revision verification failed")


def depot_command(name: str, workspace: Path) -> list[str]:
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


def execute(action: str, workspace: Path) -> None:
    print(json.dumps(preflight(workspace)), flush=True)
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
    if action == "sync":
        checkout(source, LOCK["chromium_repository"], LOCK["chromium_revision"], env)
        config = ("solutions = " + repr([{"name": "src", "url": LOCK["chromium_repository"],
                   "managed": False, "custom_deps": {}, "custom_vars": {}}]) + "\n")
        config_path = chromium / ".gclient"
        if config_path.exists() and config_path.read_text(encoding="utf-8-sig") != config:
            raise ValueError("Refusing to overwrite an unrelated gclient configuration")
        config_path.write_text(config, encoding="utf-8")
        run(depot_command("gclient", workspace) + ["sync", "--no-history", "--nohooks",
            "--revision", "src@" + LOCK["chromium_revision"], "-j", str(LOCK["build_jobs"])], chromium, env)
        run(depot_command("gclient", workspace) + ["revinfo", "-a"], chromium, env)
        return
    if not (chromium / ".gclient").is_file() or not (source / "DEPS").is_file():
        raise ValueError("Run sync before hooks/build")
    if run(["git", "rev-parse", "HEAD"], source, env, capture=True) != LOCK["chromium_revision"]:
        raise ValueError("Chromium revision does not match the build lock")
    if action == "hooks":
        run(depot_command("gclient", workspace) + ["runhooks"], chromium, env)
        return
    output = source / "out/CamouFlowNative"
    output.mkdir(parents=True, exist_ok=True)
    output.joinpath("args.gn").write_text((ROOT / "native/args.gn").read_text(encoding="utf-8-sig"), encoding="utf-8")
    run(depot_command("gn", workspace) + ["gen", "out/CamouFlowNative"], source, env)
    run(depot_command("autoninja", workspace) + ["-C", "out/CamouFlowNative", "-j", str(LOCK["build_jobs"]), "chrome"], source, env)
    relative_binary = {"win32": "chrome.exe", "linux": "chrome",
                       "darwin": "Chromium.app/Contents/MacOS/Chromium"}[sys.platform]
    binary = output / relative_binary
    with binary.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    receipt = {"schema": 1, "native_version": LOCK["native_version"],
               "chromium_revision": LOCK["chromium_revision"],
               "depot_tools_revision": LOCK["depot_tools_revision"],
               "platform": sys.platform, "binary": relative_binary,
               "binary_sha256_measured": checksum,
               "args_sha256": hashlib.sha256(output.joinpath("args.gn").read_bytes()).hexdigest(),
               "fingerprint_patched": False, "patches": []}
    output.joinpath("camouflow-build.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "bootstrap", "sync", "hooks", "build"))
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    try:
        execute(args.action, args.workspace)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Native build failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
