# Profiles

The **Profiles** tab is the main workspace for managing profiles (accounts) and running scenarios.

## What is a profile

A profile is an account record plus related fields (description, proxy, tag, and extra variables). Profiles are stored in `settings/accounts.json`, and browser data is stored in `profiles/`.

## Main elements

### Add profiles

The **Add profiles** button opens the import window:

- Paste accounts (one per line).
- Set the *Account parse template*.
- Choose a *Default tag* (optional).
- Choose a *Proxy pool* (optional).

#### Account import template

The template defines field order, for example:

```
{email};{password};{secret_key};{extra};{twofa_url}
```

The separator is derived from the template (first chunk between placeholders), usually `;`.

Example line for the template above:

```
user@example.com;pass123;SOMESECRET;note;https://2fa.example.com/
```

Each field becomes a profile variable and is available in scenarios as `{{email}}`, `{{password}}`, `{{secret_key}}`, etc.

### Profile list

The list shows:

- **Name** - profile name (ID).
- **Proxy** - current proxy (if assigned) and pool.
- **Tags** - current profile tag.
- **Actions** - quick actions (for example, launch browser).

#### Profile context menu (right-click)

- **Profile settings** - profile settings (variables/Camoufox overrides/cookies).
- **Open browser** - open the browser for the profile (persistent profile).
- **Delete account** - delete the profile and its folder in `profiles/`.
- **Assign tag** - assign a tag.
- **Run scenario** - run a scenario for this profile only.

### Profile settings window

The profile window includes:

- **Variables** - edit all profile fields (key/value). Available in scenarios as `{{key}}`.
- **Camoufox** - override global Camoufox settings for this profile (Auto/Set).
- **Cookies** - view and edit profile cookies.

### Search and tag filters

- The search box filters by name/description/tag/field preview.
- **Tags** buttons filter by the selected tag.

### Run scenario for a tag

Bottom panel:

- **Tag** - select a profile tag
- **Scenario** - select a scenario
- **Max** - max number of profiles to process per run
- **Run for tag** - start execution

### Shared variables

The **Shared variables** button opens a shared variables editor. They are available to all profiles and scenarios (see `scenarios/variables.md`).
