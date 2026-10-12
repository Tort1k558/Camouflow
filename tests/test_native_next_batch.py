from pathlib import Path

import pytest

from scripts.verify_native_next_batch import (
    CANONICAL,
    DRAFTS,
    EXISTING_PATHS,
    PATCHES,
    validate_patch_paths,
)


def added_sources(text):
    result = {}
    relative = None
    added = False
    body = []
    for line in text.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if added:
                result[relative] = "".join(body)
            relative = line.rstrip().split(" b/", 1)[1]
            added = False
            body = []
        elif line.startswith("new file mode "):
            added = True
        elif added and line.startswith("+") and not line.startswith("+++ "):
            body.append(line[1:])
    if added:
        result[relative] = "".join(body)
    return result


def test_next_batch_patch_coverage_and_canonical_sources():
    paths = set()
    additions = {}
    for name in PATCHES:
        text = (DRAFTS / name).read_text(encoding="utf-8-sig")
        current_paths = validate_patch_paths(text)
        assert paths.isdisjoint(current_paths)
        paths.update(current_paths)
        additions.update(added_sources(text))
    assert paths == EXISTING_PATHS | set(CANONICAL.values())
    assert set(additions) == set(CANONICAL.values())
    for name, relative in CANONICAL.items():
        assert additions[relative] == (DRAFTS / name).read_text(encoding="utf-8-sig")


@pytest.mark.parametrize("relative", [
    "../outside.cc", "unrelated/source.cc", "content/browser/unknown.cc",
    "C:/outside.cc", "third_party\\blink\\fake.cc",
])
def test_next_batch_refuses_unknown_or_unsafe_paths(relative):
    with pytest.raises(ValueError):
        validate_patch_paths(f"diff --git a/{relative} b/{relative}\n")


def test_gpu_metadata_candidate_does_not_drop_subgroup_capabilities():
    text = (DRAFTS / "gpu/gpu_metadata_minimization.patch").read_text(encoding="utf-8-sig")
    assert "+    info = MakeGarbageCollected<GPUAdapterInfo>(" in text
    assert "+    return MakeGarbageCollected<GPUAdapterInfo>(" not in text
    assert "base::FEATURE_DISABLED_BY_DEFAULT" in text
    assert "is_fallback_adapter);" in text


def test_audio_and_surface_helpers_do_not_enable_api_hooks():
    audio = validate_patch_paths((DRAFTS / PATCHES[1]).read_text(encoding="utf-8-sig"))
    assert not any(Path(path).name == "offline_audio_context.cc" for path in audio)
    policy = validate_patch_paths((DRAFTS / PATCHES[2]).read_text(encoding="utf-8-sig"))
    assert not any(path.endswith(".mojom") for path in policy)
    producer = (DRAFTS / "policy/surface_policy_producer.cc").read_text(encoding="utf-8-sig")
    for surface in ("canvas", "webgl", "webgpu", "audio"):
        assert f'DeriveNativePrivacyKey(context, trusted_partition, "{surface}")' in producer
