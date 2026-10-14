from pathlib import Path
import subprocess

import pytest

from scripts import prepare_native_font_rendering as draft


def source_fixture(tmp_path, monkeypatch):
    source = tmp_path / "source"
    files = {
        "ui/gfx/BUILD.gn": '      "win/camouflow_font_configuration.h",\n      "font_render_params_win_unittest.cc",\n',
        "ui/gfx/font_render_params_win.cc": '#include "base/callback_list.h"\n    skia::LegacyDisplayGlobals::SetCachedParams(\n',
        "content/browser/renderer_host/render_process_host_impl.cc": '#include "build/build_config.h"\n  // Native hardware limits must reach every renderer, including workers.\n',
        "content/renderer/render_thread_impl.cc": '#include "third_party/blink/public/web/web_view.h"\n  blink::Initialize();\n  if (!command_line.HasSwitch(switches::kDisableThreadedCompositing))\n',
    }
    for name, text in files.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    real_run = subprocess.run

    def run(arguments, **kwargs):
        if arguments == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(arguments, 0, draft.LOCK["chromium_revision"] + "\n")
        return real_run(arguments, **kwargs)

    monkeypatch.setattr(draft.subprocess, "run", run)
    return source, files


def test_font_draft_replays_without_changing_original_sources(tmp_path, monkeypatch):
    source, originals = source_fixture(tmp_path, monkeypatch)
    patch = tmp_path / "font.patch"
    report = draft.prepare(source, patch)
    assert report["prepared"] and not report["applied"]
    assert len(report["files"]) == 6
    assert b"\r\n" not in patch.read_bytes()
    assert all((source / name).read_text(encoding="utf-8") == text for name, text in originals.items())
    replay = tmp_path / "replay"
    for name, text in originals.items():
        path = replay / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    subprocess.run(["git", "apply", "--check", str(patch)], cwd=replay, check=True)
    subprocess.run(["git", "apply", str(patch)], cwd=replay, check=True)
    render = (replay / "content/browser/renderer_host/render_process_host_impl.cc").read_text(encoding="utf-8")
    assert render.index("ParseWindowsFontRasterization(value)") < render.index("renderer_cmd->AppendSwitchASCII")
    cache = (replay / "ui/gfx/font_render_params_win.cc").read_text(encoding="utf-8")
    assert cache.index("ApplyWindowsFontRasterization") < cache.index("LegacyDisplayGlobals::SetCachedParams")
    startup = (replay / "content/renderer/render_thread_impl.cc").read_text(encoding="utf-8")
    assert startup.index("blink::Initialize") < startup.index("SetAntialiasedTextEnabled")
    assert startup.index("SetLCDTextEnabled") < startup.index("kDisableThreadedCompositing")
    assert "*mode != glint::candidate::WindowsFontRasterization::kNative" in startup
    subprocess.run(["git", "apply", "--reverse", str(patch)], cwd=replay, check=True)
    assert all((replay / name).read_text(encoding="utf-8") == text for name, text in originals.items())
    with pytest.raises(ValueError, match="new canonical output"):
        draft.prepare(source, patch)


def test_font_draft_rejects_missing_source_anchor(tmp_path, monkeypatch):
    source, _ = source_fixture(tmp_path, monkeypatch)
    (source / "ui/gfx/BUILD.gn").write_text("unexpected upstream\n", encoding="utf-8")
    with pytest.raises(ValueError, match="anchor is not unique"):
        draft.prepare(source, tmp_path / "font.patch")


def test_font_draft_rejects_output_inside_active_source(tmp_path, monkeypatch):
    source, _ = source_fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="outside Chromium"):
        draft.prepare(source, source / "font.patch")
