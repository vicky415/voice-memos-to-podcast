# Changelog

## 2.0.0 — 2026-09-28

- Added an explicit per-run choice between Spotify-only and Spotify + X + Facebook.
- Added post-publication direct sharing from Spotify's “Episode published!” screen, including the final X Post and Facebook Post/Share actions.
- Added deterministic return-to-Spotify, **Done**, and next-episode sequencing.
- Added a private progress ledger with duplicate-post protection and filename-order batch recovery.
- Added direct local-folder `.m4a` selection and per-episode progress/status output.
- Added safeguards for login, identity, destination, CAPTCHA, pop-up, and partial-share failures without republishing the episode.
- Preserved the v1 upload, manifest schema, RSS verification, Apple Podcasts, and S3-backed workflows.
