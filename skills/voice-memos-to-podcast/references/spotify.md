# Existing Spotify-hosted show

1. Read the supplied RSS to identify show, host and existing GUIDs. Do not expose the owner's email. RSS is a read endpoint, not an upload endpoint.
2. Prepare the selected local audio and manifest. Spotify supports M4A, MP3 and WAV with mono/stereo audio. Check playback when local media tools exist; rename alone does not convert codecs.
3. Discover a suitable official connector; otherwise use the agent's supported authenticated browser. This skill supplies adaptive UI instructions, not a hard-coded headless uploader. The ordinary Spotify Web API cannot substitute for episode uploading.
4. Open Spotify for Creators. Verify the show against the RSS, inspect existing drafts/episodes, then New episode → Select a file. Upload exactly the selected recording through the supported file chooser.
5. Wait for processing. Fill title, description and content checks from approved data. Verify full episode vs trailer, explicit content, any promotional-content question and public vs subscriber-only. Free RSS distribution does not publish subscriber audio.
6. Choose Now or the requested schedule; check the UI timezone. Publish once under episode-specific authorization. Save the episode URL and host status privately. If uncertain, inspect existing episodes before retrying.
7. Run `release.py verify` against the same RSS. Scheduled episodes may not appear yet. Pending ingestion does not justify another publish attempt.
8. Find the show in Apple Podcasts Connect using the existing RSS. If absent and distribution was requested, submit the same RSS once, verify details and follow review. If access is missing, request sign-in; do not claim it is connected.

Example from repository root:

```sh
python3 skills/voice-memos-to-podcast/scripts/release.py prepare \
  --audio '/absolute/path/selected.m4a' --rss 'https://host.example/feed.xml' \
  --title 'Episode title' --description 'Approved description' \
  --explicit false --out '/private/path/release.json'
python3 skills/voice-memos-to-podcast/scripts/release.py verify \
  --manifest '/private/path/release.json'
```

Verification exits 2 for pending/ambiguous results. Match host playback/file details separately: XML matching alone cannot prove the uploaded audio content. Browser automation requires an authenticated session and file-upload support. When unavailable, hand off the prepared file and metadata honestly.
