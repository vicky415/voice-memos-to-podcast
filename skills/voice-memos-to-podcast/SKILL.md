---
name: voice-memos-to-podcast
description: Publish selected iPhone or iPad Voice Memos to an existing Spotify-hosted podcast and distribute through its RSS to Apple Podcasts, or publish a user-selected S3-backed RSS show. Use for recording export, episode preparation, publishing and verification; not music distribution or silent access to an iOS recording library.
---

# Voice Memos to Podcast

Publish only the user-selected recording. Preserve the existing show, host and RSS URL. A skill runs in an agent session; it cannot silently read iOS app storage or act as an always-on iOS service.

## Routing

- Existing Spotify/Anchor-hosted show: follow [Spotify workflow](references/spotify.md). Spotify generates its RSS; never upload XML to an Anchor URL or use the ordinary Spotify Web API as an episode-upload API.
- Other existing host: use its documented upload API or authenticated UI. Preserve RSS and GUIDs; do not replace the host for convenience.
- Explicitly chosen new self-hosted show: use [S3 workflow](references/self-hosted.md). This optional helper is not a migration tool.

## Selected input and metadata

Use the supplied local audio path or ask the user to share the named recording to Files/iCloud Drive/AirDrop. See [iOS handoff](references/ios.md). Voice Memos iCloud sync is not a Files folder. Do not scan private databases or choose an unrelated “latest” recording. Prefer flattened audio over editable layered projects.

For Spotify retain playable M4A/MP3/WAV; conversion is optional. Do not transcribe, edit or send recordings to extra services outside task scope. Obtain title, description, explicit-content choice and timing from the user or established defaults. Do not invent content checks or episode descriptions from filenames.

## Execution

Prepare a private release manifest with `scripts/release.py prepare`; it fingerprints the selected file and snapshots RSS GUIDs. Review show, file, metadata and timing before the external mutation. A clear request to publish this episode is authorization; do not repeatedly ask. Creating/testing this skill does not authorize publishing sample recordings.

Use an available authorized connector or browser for Spotify, following its environment-specific browser and upload instructions. If login, CAPTCHA or absent upload capability blocks progress, preserve preparation and state the exact user action needed. Never use unofficial session-token endpoints as a workaround.

Before retrying an uncertain publish, inspect drafts, published episodes and RSS. Do not blindly click Publish again. `release.py verify` identifies new matching RSS items; use host playback/file details to verify audio identity, especially if titles collide. Record distinct states: prepared, host published, RSS observed, Apple observed. RSS success does not prove Apple ingestion.

Submit the existing RSS to Apple Podcasts Connect once if not already listed. Handle login and any agreement at the required user boundary. Subsequent public episodes use the same RSS; do not create duplicate shows for delayed ingestion or create recurring monitors unless requested.

## Open source

Keep actual recordings, personal configurations, RSS snapshots, receipts and credentials outside Git. Read [release packaging](references/open-source.md) when publishing this skill. Recheck [official sources](references/sources.md) when platform behavior changes.
