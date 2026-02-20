### Burnki Configuration

- **wanikani_api_token**: Your WaniKani API token. Generate one at
  <https://www.wanikani.com/settings/personal_access_tokens>. Only
  read permissions are needed.

- **auto_sync_on_startup**: When `true`, Burnki automatically syncs
  burned items every time you open your Anki profile. Set to `false`
  to only sync manually via Tools → Burnki → Sync Now.

- **download_audio**: When `true`, audio is downloaded
  for vocabulary cards. Set to `false` to skip audio downloads.

- **last_sync_timestamp**: Tracks the last
  sync time so only new burns are fetched on subsequent syncs (managed automatically). Clear
  this value to force a full re-sync (or use Tools → Burnki → Full Re-Sync).
