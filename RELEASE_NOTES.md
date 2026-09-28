# Spotify Publishing Skill v2.0

Version: v2.0.0

- Added optional X sharing through Spotify's published-episode share button.
- Added optional Facebook sharing through Spotify's published-episode share button.
- Added the Spotify → X → Facebook → Done sequence for each published episode.
- Added private batch progress tracking to prevent duplicate episodes and social posts after interruption.
- Preserved Spotify-only mode as the default.
- Improved filename-order multi-file publishing and recovery from failed or uncertain steps.

The existing Spotify upload, RSS verification, Apple Podcasts and optional S3 publishing scripts are unchanged. Browser posting still requires authenticated sessions and cannot be verified by local automated tests.
