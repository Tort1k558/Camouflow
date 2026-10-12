from pathlib import Path

import pytest

from scripts import verify_native_document_drafts as drafts


def test_document_candidate_order_and_canonical_paths():
    assert len(drafts.PATCHES) == 5
    assert drafts.PATCHES[0] == "document_canvas_seed_handoff.patch"
    assert drafts.PATCHES[-1] == "document_navigation_integration_tests.patch"
    paths = set().union(*(drafts.patch_paths((drafts.DRAFTS / name).read_text(encoding="utf-8-sig"))
                         for name in drafts.PATCHES))
    assert len(paths) == 27
    assert set(drafts.CANONICAL.values()) <= paths


@pytest.mark.parametrize("path", ["../escape.cc", "/absolute.cc", "C:/escape.cc", "a\\escape.cc", "a/./b.cc"])
def test_patch_paths_reject_unsafe_paths(path):
    with pytest.raises(ValueError, match="Unsafe"):
        drafts.patch_paths(f"diff --git a/{path} b/{path}\n")


@pytest.mark.parametrize("text", ["", "not a patch", "diff --git a/one.cc b/two.cc\n"])
def test_patch_paths_reject_missing_or_renamed_paths(text):
    with pytest.raises(ValueError):
        drafts.patch_paths(text)


def test_digest_preserves_missing_vs_empty(tmp_path):
    path = tmp_path / "input.cc"
    assert drafts.digest(path) is None
    path.write_bytes(b"")
    assert drafts.digest(path) is not None


@pytest.mark.parametrize("suffix", ["new file mode 120000", "new mode 160000", "GIT binary patch"])
def test_patch_paths_reject_non_source_changes(suffix):
    with pytest.raises(ValueError):
        drafts.patch_paths(f"diff --git a/one.cc b/one.cc\n{suffix}\n")


@pytest.fixture
def replay_fixture(tmp_path, monkeypatch):
    source = tmp_path / "chromium/src"
    (source / "src").mkdir(parents=True)
    (source / "src/value.cc").write_text("before\n", encoding="utf-8")
    candidates = tmp_path / "candidates"
    candidates.mkdir()
    (candidates / "value.cc").write_text("after\n", encoding="utf-8")
    (candidates / "update.patch").write_text(
        "diff --git a/src/value.cc b/src/value.cc\n"
        "--- a/src/value.cc\n+++ b/src/value.cc\n@@ -1 +1 @@\n-before\n+after\n",
        encoding="utf-8", newline="\n",
    )
    monkeypatch.setattr(drafts, "DRAFTS", candidates)
    monkeypatch.setattr(drafts, "PATCHES", ("update.patch",))
    monkeypatch.setattr(drafts, "CANONICAL", {"value.cc": "src/value.cc"})
    original_run = drafts.build.run

    def run(args, cwd, env, *, capture=False):
        if args == ["git", "rev-parse", "HEAD"]:
            return drafts.build.LOCK["chromium_revision"]
        return original_run(args, cwd, env, capture=capture)

    monkeypatch.setattr(drafts.build, "run", run)
    monkeypatch.setattr(drafts.build, "source_patches", lambda *_: [])
    monkeypatch.setattr(drafts.build, "v8_source_patches", lambda *_: [])
    return tmp_path, source, candidates


def test_ordered_replay_uses_real_git_without_changing_source(replay_fixture):
    workspace, source, _ = replay_fixture
    result = drafts.verify(workspace, workspace / "proof.json")
    assert result["passed"]
    assert result["active_sources_unchanged"]
    assert result["patch_order"] == ["update.patch"]
    assert result["verifier_sha256"] == drafts.digest(Path(drafts.__file__))
    assert (source / "src/value.cc").read_text() == "before\n"


def test_canonical_mismatch_does_not_publish_success(replay_fixture):
    workspace, source, candidates = replay_fixture
    (candidates / "value.cc").write_text("different\n", encoding="utf-8")
    report = workspace / "proof.json"
    with pytest.raises(ValueError, match="canonical candidate"):
        drafts.verify(workspace, report)
    assert not report.exists()
    assert (source / "src/value.cc").read_text() == "before\n"


def test_verify_refuses_report_inside_source_before_git(tmp_path):
    source = tmp_path / "chromium/src"
    source.mkdir(parents=True)
    with pytest.raises(ValueError, match="outside both"):
        drafts.verify(tmp_path, source / "report.json")


def test_verify_refuses_existing_evidence_before_git(tmp_path):
    (tmp_path / "chromium/src").mkdir(parents=True)
    report = tmp_path / "report.json"
    report.write_text("existing evidence", encoding="utf-8")
    with pytest.raises(ValueError, match="overwrite"):
        drafts.verify(tmp_path, report)
    assert report.read_text() == "existing evidence"


def test_verify_refuses_relative_report_before_git(tmp_path):
    (tmp_path / "chromium/src").mkdir(parents=True)
    with pytest.raises(ValueError, match="canonical report"):
        drafts.verify(tmp_path, Path("report.json"))
