"""Archive privacy, integrity and rollback use disposable local workspaces."""

import hashlib
import json
import stat
import zipfile

import pytest

from app.services import profile_backup
from app.storage import db


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    for name, relative in [("SETTINGS_DIR", "settings"), ("PROFILES_DIR", "profiles"),
                           ("SCENARIOS_DIR", "scenarios"), ("OUTPUTS_DIR", "outputs")]:
        directory = tmp_path / relative
        directory.mkdir()
        monkeypatch.setattr(db, name, directory)
    monkeypatch.setattr(db, "ACCOUNTS_FILE", db.SETTINGS_DIR / "accounts.json")
    monkeypatch.setattr(db, "SETTINGS_FILE", db.SETTINGS_DIR / "settings.json")
    db.db_add_account({"name": "original", "stage": "QA", "password": "synthetic-secret",
                       "_browser_engine": "camoufox", "extra_fields": {"private": "synthetic-private"}})
    db.db_set_setting("unrelated", "keep")
    browser = db.profile_dir_for_email("original")
    browser.mkdir()
    (browser / "session.dat").write_bytes(b"synthetic browser session")
    (browser / "parent.lock").write_bytes(b"locked")
    return tmp_path


def archive_with(source, metadata=None, entries=None, hashes=None):
    payload = {"profile.json": json.dumps(metadata or {"profile": {"name": "original"}, "settings": {}}).encode()}
    payload.update(entries or {})
    manifest = {"format": 1, "sha256": hashes or {name: hashlib.sha256(value).hexdigest() for name, value in payload.items()}}
    with zipfile.ZipFile(source, "w") as archive:
        for name, content in payload.items():
            entry = zipfile.ZipInfo("synthetic")
            entry.filename = name
            entry.orig_filename = name
            archive.writestr(entry, content)
        archive.writestr("manifest.json", json.dumps(manifest))


@pytest.mark.parametrize("sessions", [False, True])
@pytest.mark.parametrize("secrets", [False, True])
def test_export_restore_roundtrip_preserves_original_and_privacy(workspace, sessions, secrets):
    target = workspace / "profile.zip"
    original_accounts = db.ACCOUNTS_FILE.read_bytes()
    profile_backup.export_profile("original", target, sessions, secrets)
    with zipfile.ZipFile(target) as archive:
        metadata = json.loads(archive.read("profile.json"))
        assert ("password" in metadata["profile"]) is secrets
        assert ("extra_fields" in metadata["profile"]) is secrets
        assert ("browser/session.dat" in archive.namelist()) is sessions
        assert "browser/parent.lock" not in archive.namelist()
        assert "synthetic-secret" not in archive.read("profile.json").decode() or secrets
    restored = profile_backup.restore_profile(target, "restored")
    assert restored.is_dir()
    assert (restored / "session.dat").exists() is sessions
    if sessions:
        assert (restored / "session.dat").read_bytes() == b"synthetic browser session"
    assert db.db_get_setting("unrelated") == "keep"
    assert next(account for account in db.db_get_accounts() if account["name"] == "original")["password"] == "synthetic-secret"
    assert db.profile_dir_for_email("original").joinpath("session.dat").read_bytes() == b"synthetic browser session"
    assert original_accounts != db.ACCOUNTS_FILE.read_bytes()
    assert not list(db.PROFILES_DIR.glob(".restore-*"))


@pytest.mark.parametrize("name", ["../outside", "/absolute", "browser/../../outside", "browser\\outside",
                                 "browser/data:stream", "browser/CON", "browser/trailing."])
def test_unsafe_archive_paths_leave_workspace_unchanged(workspace, name):
    source = workspace / "unsafe.zip"
    archive_with(source, entries={name: b"synthetic"})
    before = db.ACCOUNTS_FILE.read_bytes()
    with pytest.raises(ValueError):
        profile_backup.restore_profile(source, "restored")
    assert db.ACCOUNTS_FILE.read_bytes() == before
    assert not db.profile_dir_for_email("restored").exists()
    assert not list(db.PROFILES_DIR.glob(".restore-*"))


def test_checksum_mismatch_is_rejected_before_publication(workspace):
    source = workspace / "corrupt.zip"
    archive_with(source, hashes={"profile.json": "0" * 64})
    with pytest.raises(ValueError, match="checksum mismatch"):
        profile_backup.restore_profile(source, "restored")
    assert [account["name"] for account in db.db_get_accounts()] == ["original"]
    assert not db.profile_dir_for_email("restored").exists()


def test_case_colliding_entries_are_rejected(workspace):
    source = workspace / "collision.zip"
    archive_with(source, entries={"browser/File": b"one", "browser/file": b"two"})
    with pytest.raises(ValueError, match="Unsafe archive path"):
        profile_backup.restore_profile(source, "restored")


def test_archive_symbolic_link_is_rejected(workspace):
    source = workspace / "link.zip"
    archive_with(source)
    entry = zipfile.ZipInfo("browser/link")
    entry.create_system = 3
    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(source, "a") as archive:
        archive.writestr(entry, "../../outside")
    with pytest.raises(ValueError, match="Unsafe archive path"):
        profile_backup.restore_profile(source, "restored")


def test_existing_archive_is_not_replaced(workspace):
    target = workspace / "existing.zip"
    target.write_bytes(b"existing user artifact")
    with pytest.raises(FileExistsError):
        profile_backup.export_profile("original", target, False, False)
    assert target.read_bytes() == b"existing user artifact"


def test_existing_profile_cannot_be_restored_over(workspace):
    source = workspace / "profile.zip"
    profile_backup.export_profile("original", source, True, True)
    before = db.ACCOUNTS_FILE.read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        profile_backup.restore_profile(source, "ORIGINAL")
    assert db.ACCOUNTS_FILE.read_bytes() == before


def test_restore_account_write_failure_rolls_back_files_and_scenarios(workspace, monkeypatch):
    source = workspace / "profile.zip"
    metadata = {"profile": {"name": "original"}, "settings": {},
                "scenarios": [{"name": "Synthetic task", "steps": [{"action": "wait", "value": "1"}]}]}
    archive_with(source, metadata=metadata, entries={"browser/session.dat": b"synthetic"})
    before = db.ACCOUNTS_FILE.read_bytes()
    monkeypatch.setattr(db, "db_add_account", lambda account: (_ for _ in ()).throw(OSError("Synthetic disk error")))
    with pytest.raises(OSError, match="Synthetic disk error"):
        profile_backup.restore_profile(source, "restored", import_scenarios=True)
    assert db.ACCOUNTS_FILE.read_bytes() == before
    assert not db.profile_dir_for_email("restored").exists()
    assert not list(db.SCENARIOS_DIR.glob("*.json"))
    assert not list(db.PROFILES_DIR.glob(".restore-*"))


def test_engine_defaults_are_local_to_restored_profile(workspace):
    db.db_set_setting("camoufox_defaults", '{"locale":"en-US"}')
    source = workspace / "profile.zip"
    metadata = {"profile": {"name": "original", "camoufox_settings": {"timezone": "UTC"}},
                "settings": {"camoufox_defaults": '{"locale":"ru-RU"}'}}
    archive_with(source, metadata=metadata)
    profile_backup.restore_profile(source, "restored")
    restored = next(account for account in db.db_get_accounts() if account["name"] == "restored")
    assert restored["camoufox_settings"] == {"locale": "ru-RU", "timezone": "UTC"}
    assert db.db_get_setting("camoufox_defaults") == '{"locale":"en-US"}'


def test_export_inside_browser_profile_is_rejected(workspace):
    target = db.profile_dir_for_email("original") / "inside.zip"
    with pytest.raises(ValueError, match="outside the browser profile"):
        profile_backup.export_profile("original", target, True, False)
    assert not target.exists()


@pytest.mark.parametrize("limit", ["MAX_BYTES", "MAX_FILES"])
def test_export_safety_limit_leaves_no_partial_archive(workspace, monkeypatch, limit):
    monkeypatch.setattr(profile_backup, limit, 0)
    target = workspace / "limited.zip"
    with pytest.raises(ValueError, match="safety limit"):
        profile_backup.export_profile("original", target, True, False)
    assert not target.exists()


def test_restore_size_limit_does_not_publish_a_profile(workspace, monkeypatch):
    source = workspace / "profile.zip"
    archive_with(source)
    monkeypatch.setattr(profile_backup, "MAX_BYTES", 1)
    with pytest.raises(ValueError, match="safety limits"):
        profile_backup.restore_profile(source, "restored")
    assert [account["name"] for account in db.db_get_accounts()] == ["original"]
    assert not list(db.PROFILES_DIR.glob(".restore-*"))


def test_export_detects_changed_session_and_removes_only_new_archive(workspace, monkeypatch):
    target = workspace / "changing.zip"
    original_open = zipfile.ZipFile.open

    def open_entry(archive, name, mode="r", *args, **kwargs):
        if name == "browser/session.dat" and mode == "w":
            with (db.profile_dir_for_email("original") / "session.dat").open("ab") as session:
                session.write(b" changed")
        return original_open(archive, name, mode, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "open", open_entry)
    with pytest.raises(ValueError, match="changed during export"):
        profile_backup.export_profile("original", target, True, False)
    assert not target.exists()
    assert db.profile_dir_for_email("original").exists()
    assert [account["name"] for account in db.db_get_accounts()] == ["original"]


def test_imported_scenario_references_are_rewritten_without_overwriting_existing(workspace):
    db.db_save_scenario("restored restore 1", [{"action": "wait", "value": "original"}])
    original = db._scenario_path("restored restore 1").read_bytes()
    source = workspace / "profile.zip"
    archive_with(source, metadata={"profile": {"name": "original"}, "settings": {}, "scenarios": [
        {"name": "A", "steps": [{"action": "run_scenario", "value": "B"}]},
        {"name": "B", "steps": [{"action": "run_scenario", "value": "external"}]},
    ]})
    profile_backup.restore_profile(source, "restored", import_scenarios=True)
    scenarios = {scenario.name: scenario.steps for scenario in db.db_get_scenarios()}
    assert scenarios["restored restore 1 (2)"][0]["value"] == "restored restore 2"
    assert scenarios["restored restore 2"][0]["value"] == "external"
    assert db._scenario_path("restored restore 1").read_bytes() == original
