"""Prepare a Windows font-rasterization candidate outside active Chromium sources."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.native_build import LOCK


def replace_once(text: str, before: str, after: str) -> str:
    if text.count(before) != 1:
        raise ValueError("Font rasterization source anchor is not unique")
    return text.replace(before, after)


def prepare(source: Path, output: Path) -> dict:
    if source != source.resolve() or not source.is_dir():
        raise ValueError("Font draft requires canonical Chromium sources")
    if output != output.resolve() or output.exists() or output.is_relative_to(source):
        raise ValueError("Font draft requires a new canonical output outside Chromium sources")
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source,
                              check=True, capture_output=True, text=True).stdout.strip()
    if revision != LOCK["chromium_revision"]:
        raise ValueError("Font draft requires the pinned Chromium revision")
    originals = {}
    replacements = {}
    for name in ("ui/gfx/BUILD.gn", "ui/gfx/font_render_params_win.cc",
                 "content/browser/renderer_host/render_process_host_impl.cc"):
        path = source / name
        if path != path.resolve() or not path.is_file():
            raise ValueError("Font draft source files must be ordinary files")
        originals[name] = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    name = "ui/gfx/BUILD.gn"
    replacements[name] = replace_once(originals[name], '      "win/camouflow_font_configuration.h",\n',
        '      "win/camouflow_font_configuration.h",\n      "win/glint_font_rasterization_policy.h",\n')
    replacements[name] = replace_once(replacements[name], '      "font_render_params_win_unittest.cc",\n',
        '      "font_render_params_win_unittest.cc",\n      "win/glint_font_rasterization_policy_unittest.cc",\n')
    name = "ui/gfx/font_render_params_win.cc"
    replacements[name] = replace_once(originals[name], '#include "base/callback_list.h"\n',
        '#include "base/callback_list.h"\n#include "base/check.h"\n#include "base/command_line.h"\n'
        '#include "ui/gfx/win/glint_font_rasterization_policy.h"\n')
    anchor = "    skia::LegacyDisplayGlobals::SetCachedParams(\n"
    block = """    const auto* command = base::CommandLine::ForCurrentProcess();
    if (command->HasSwitch(glint::candidate::kWindowsFontRasterizationSwitch)) {
      const auto mode = glint::candidate::ParseWindowsFontRasterization(
          command->GetSwitchValueASCII(glint::candidate::kWindowsFontRasterizationSwitch));
      CHECK(mode.has_value()) << "Invalid Glint Windows font rasterization";
      CHECK(glint::candidate::ApplyWindowsFontRasterization(*params_, *mode));
    }

"""
    replacements[name] = replace_once(replacements[name], anchor, block + anchor)
    name = "content/browser/renderer_host/render_process_host_impl.cc"
    replacements[name] = replace_once(originals[name], '#include "build/build_config.h"\n',
        '#include "build/build_config.h"\n#if BUILDFLAG(IS_WIN)\n'
        '#include "ui/gfx/win/glint_font_rasterization_policy.h"\n#endif\n')
    anchor = "  // Native hardware limits must reach every renderer, including workers.\n"
    block = """#if BUILDFLAG(IS_WIN)
  if (browser_cmd.HasSwitch(glint::candidate::kWindowsFontRasterizationSwitch)) {
    const auto value = browser_cmd.GetSwitchValueASCII(
        glint::candidate::kWindowsFontRasterizationSwitch);
    CHECK(glint::candidate::ParseWindowsFontRasterization(value).has_value())
        << "Invalid Glint Windows font rasterization";
    renderer_cmd->AppendSwitchASCII(
        glint::candidate::kWindowsFontRasterizationSwitch, value);
  }
#endif

"""
    replacements[name] = replace_once(replacements[name], anchor, block + anchor)
    for filename, target in (("windows_font_rasterization_policy.h", "ui/gfx/win/glint_font_rasterization_policy.h"),
                             ("windows_font_rasterization_policy_unittest.cc", "ui/gfx/win/glint_font_rasterization_policy_unittest.cc")):
        if (source / target).exists():
            raise ValueError("Font rasterization candidate is already present")
        originals[target] = ""
        replacements[target] = (ROOT / "native/drafts/font-rendering" / filename).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    patch = ""
    for name, text in replacements.items():
        before = originals[name]
        patch += f"diff --git a/{name} b/{name}\n"
        if not before:
            patch += "new file mode 100644\n"
        patch += "".join(difflib.unified_diff(before.splitlines(True), text.splitlines(True),
                                             fromfile="a/" + name if before else "/dev/null", tofile="b/" + name))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(patch, encoding="utf-8", newline="\n")
    return {"prepared": True, "applied": False, "source_revision": revision,
            "patch_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "files": list(replacements), "scope": "Unregistered rendering candidate; native/runtime validation still required"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = prepare(args.source, args.output)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Font rendering draft failed: {error}\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
