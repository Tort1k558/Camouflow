# Profiles

The **Profiles** page manages local browser profiles, tags, profile variables, cookies and batch scenario runs.

## Profile list

- **New Profile** creates an empty profile.
- **Import** opens bulk import.
- **Tags** opens tag management.
- Search filters by profile name, tags and proxy label.
- Each row can start/stop a browser session, open profile settings or delete the profile.
- Right-click a profile for quick actions: settings, open browser, variables, cookies, run selected scenario or delete.

## Bulk import

Use **Import** to add many profiles at once:

- Paste profiles, one per line.
- Set the account parse template, for example:

```text
{email};{password};{secret_key};{extra};{twofa_url}
```

- Set an optional default tag.
- Pick an optional proxy pool. CamouFlow assigns an available, unassigned,
  non-quarantined connection from that pool to each imported profile.

A selected pool is a requirement, not a preference: exhausted pools and failed
cloud reads stop affected imports instead of creating direct-connection profiles.
Malformed or timezone-naive quarantine timestamps remain blocked until explicitly
released. Choose **All pools** only when no pool assignment is intended.

After partial failure, the dialog stays open with only failed lines. Correct
those lines or change the pool before importing again; successfully imported
rows are not resubmitted. Error logs identify line numbers rather than the
credential-bearing input lines. Unexpected exception details can still contain
sensitive data, so review logs before sharing them.

Imported fields are saved as profile variables and can be used in scenarios as `{{email}}`, `{{password}}`, etc.

## Local profile archives

**Selected actions** can export metadata-only archives without secrets or browser
sessions. **Backup & restore** offers separate options for browser files and
sensitive profile metadata. Close the profile's browser before export and store
archives outside its browser directory. Existing archives are never overwritten.

Archives are unencrypted. Browser session files can contain cookies or passwords
even when profile metadata secrets are excluded. Checksums detect corruption,
not a malicious author; restore only trusted archives under a new local name.
Existing profiles and global settings remain unchanged. Archived engine defaults
apply only to the restored profile. Optional scenarios receive new names and
references within the archive are rewritten; external references are unchanged.
Browser-encrypted sessions may not transfer to another user or machine.

Archive verification is bounded to 2 GiB / 50,000 browser files; metadata and
manifest documents each have an 8 MiB limit. These are safety limits, not quotas.

## Profile settings

The settings dialog edits:

- name
- tag
- proxy host / port / user / password
- per-profile browser overrides: locale, timezone, user agent, WebGL/GPU vendor, CPU cores

## Variables and cookies

From profile settings or the context menu:

- **Vars** edits profile variables as a JSON object.
- **Cookies** is available in local mode only. It reads the selected engine's storage and replaces cookies through that profile's browser context.

Blank input, invalid cookie fields and Chromium `<encrypted>` preview values are
rejected before launching a browser. To clear cookies, enter `[]` and confirm;
cancel leaves the current jar unchanged. Profiles already running, starting or
reserved by another operation cannot be edited. Failed replacement attempts to
restore the original jar; this is not a crash-safe transaction.

Preview expiration timestamps use Unix seconds, including Chromium's Windows
epoch and Firefox schema 16/17 millisecond conversion. Unsupported Firefox
schemas and corrupt storage produce an error rather than an empty preview.
The preview is not a complete browser-session export: use a trusted profile
archive to preserve browser storage, and never share cookie values publicly.

## Run scenario for tag

The bottom panel runs a selected scenario for profiles matching a tag:

- **Tag** selects the profile tag. `All tags` runs across all profiles.
- **Scenario** selects the scenario.
- **Max** limits the number of profiles processed.
- **Run for tag** starts the batch run.

## Shared variables

The **Variables** button opens the shared variables editor. Shared variables are available to all profiles and scenarios.

### Dedicated browser storage

New/renamed profile names must map to a valid, distinct browser directory.
Reserved Windows names, workspace-root identities and names that sanitize to
another profile's directory are rejected. Browser launch, cookie reads/resets,
profile-directory deletion and restore targets validate their storage boundary.
Profile-root links and linked engine directories are not accepted.

Existing ambiguous/unsafe names are not automatically migrated or deleted.
Preserve the workspace and review a verified backup before recovering those
records; do not reset or remove shared browser files. Renames refuse an existing
unmanaged target directory. A failed metadata save attempts to move a renamed
directory back. These guards do not provide crash-safe multi-file transactions,
protect against arbitrary local Python, or namespace cloud storage by team.
