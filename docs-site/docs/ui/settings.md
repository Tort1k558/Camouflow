# Settings

The **Settings** page shows application-level runtime information.

## AI provider

Configure the provider URL, API key, model and maximum step count. Provider fields
are saved together in one atomic settings update. A failed save shows an error
instead of a success message. **Test provider** makes a real request to the
configured service; a local fixture test is not proof of paid-model quality.

## Local storage recovery

Account and settings mutations refuse to overwrite malformed, wrongly shaped or
unreadable JSON. Restore `settings/accounts.json` or `settings/settings.json`
from a verified backup before retrying. Do not delete these files as a reset.
Missing files can initialize a new workspace. UTF-8 BOM documents are accepted;
updates use UTF-8 without BOM.

Onboarding/settings actions report persistence failures without silently
navigating away or dismissing the welcome dialog. These safeguards do not repair
corrupted files, encrypt storage, or provide cross-process transactions.

## App Settings

- **Data root** shows where CamouFlow stores local data:
  - profiles
  - scenarios
  - proxy pools
  - shared variables
  - browser settings
  - logs
  - outputs

## Browser settings moved to Browser

Browser engine settings are managed on the **Browser** page, not Settings.

The Browser page contains:

- Camoufox / CloakBrowser engine selection
- execution mode
- humanization
- locale and timezone
- persistent storage
- window and screen sizes
- navigator overrides
- WebGL/GPU settings
- network/rendering restrictions
- fonts, addons, extensions and launch args
