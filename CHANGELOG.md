# Changelog

## HiBinds UI & Reliability update

- Added `.hibinds` import/export format with version metadata.
- Added startup health validation: broken JSON, missing files, invalid URLs, invalid delays, duplicate actions and duplicate hotkeys are detected.
- Added dashboard with counters: total binds, working binds and warnings.
- Added visible system-health panel and manual full check.
- Added Windows autostart switch using the current-user Run registry key.
- Added hotkey field with syntax validation for saved binds.
- Added search for bind names.
- Added modern dark/light/system appearance setting.
- Added animated hero highlight and refreshed card-based design.
- Kept settings and bind data in `%APPDATA%\\HiBinds`.
- Existing legacy `HIBinds.json` / `HIbinds.json` files are still migrated automatically.
