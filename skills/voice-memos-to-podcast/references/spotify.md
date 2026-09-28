# Existing Spotify-hosted show

## Choose a mode

Choose once for the current run before the first publication. If the user has not chosen, use **Spotify only** so v1 behavior is preserved.

- `spotify-only`: publish and verify exactly as before. On “Episode published!”, click **Done** and continue.
- `spotify-x-facebook`: after every successfully published, immediately live episode, share from the “Episode published!” screen to X and Facebook, complete each platform's final action, return to Spotify, click **Done**, and continue.

The social mode is per run, not a permanent account setting. It does not apply to the S3 workflow, existing episodes, drafts, failed uploads, or scheduled episodes that are not live.

## Batch preparation and recovery

For one or more user-selected files, sort the exact paths by filename and create a private ledger outside Git before opening Spotify. One file is one episode. Keep one ledger for the run and reuse it after interruption; never initialize a new ledger to restart already completed files. The helper rejects out-of-order progress and changed audio bytes.

For a local Voice Memos folder, the helper selects only direct `.m4a` files, sorted by filename. It does not recurse into subfolders or include unrelated files:

```sh
python3 skills/voice-memos-to-podcast/scripts/batch.py init --mode spotify-x-facebook \
  --folder '/absolute/path/Voice Memos' --out '/private/path/batch.json'
python3 skills/voice-memos-to-podcast/scripts/batch.py status --ledger '/private/path/batch.json'
python3 skills/voice-memos-to-podcast/scripts/batch.py mark --ledger '/private/path/batch.json' \
  --index 1 --stage spotify --value attempted
```

Use `--mode spotify-only` or omit `--mode` for the v1 route. Explicit paths in filename order remain supported instead of `--folder`. For each episode, mark `spotify`, then `x` and `facebook` in social mode, then `done`. Mark each stage `attempted` immediately before its final button and `confirmed` only after visible success. Mark `failed` only after verifying that the action did not complete. An `attempted` stage is uncertain: inspect Spotify/X/Facebook before retrying it. If social sharing fails conclusively, mark that platform failed, continue to the other share and Done, then move to the next file. The `status` output reports totals, per-file stages and the next episode; share that concise progress with the user after each episode or failure. The ledger and v1 release manifests are private state, not repository files.

1. Read the supplied RSS to identify show, host and existing GUIDs. Do not expose the owner's email. RSS is a read endpoint, not an upload endpoint.
2. Prepare the selected local audio and manifest. Spotify supports M4A, MP3 and WAV with mono/stereo audio. Check playback when local media tools exist; rename alone does not convert codecs.
3. Discover a suitable official connector; otherwise use the agent's supported authenticated browser. This skill supplies adaptive UI instructions, not a hard-coded headless uploader. The ordinary Spotify Web API cannot substitute for episode uploading.
4. Open Spotify for Creators. Verify the show against the RSS, inspect existing drafts/episodes, then New episode → Select a file. Upload exactly the selected recording through the supported file chooser.
5. Wait for processing. Fill title, description and content checks from approved data. Verify full episode vs trailer, explicit content, any promotional-content question and public vs subscriber-only. Free RSS distribution does not publish subscriber audio.
6. Choose Now or the requested schedule; check the UI timezone. Mark Spotify `attempted`, then Publish once under episode-specific authorization. Save the episode URL and host status privately; mark Spotify `confirmed` after visible success. If uncertain, inspect existing episodes before retrying.
7. Handle the “Episode published!” screen according to the selected mode. In `spotify-only`, click **Done**. In `spotify-x-facebook`, complete [Social sharing](#social-sharing), then click **Done**. Record Done in the ledger and advance to the next file only after it is confirmed.
8. Run `release.py verify` against the same RSS. Scheduled episodes may not appear yet. Pending ingestion does not justify another publish attempt.
9. Find the show in Apple Podcasts Connect using the existing RSS. If absent and distribution was requested, submit the same RSS once, verify details and follow review. If access is missing, request sign-in; do not claim it is connected.

## Social sharing

Run this only when the user chose `spotify-x-facebook` and Spotify visibly confirms the episode was published. An explicit mode choice authorizes the final posting actions for the selected episode(s); do not pause at a filled composer merely because **Post** or **Share** is externally mutating.

1. On Spotify's “Episode published!” screen, select the built-in **X** share action. Follow the new tab/window without losing the Spotify success screen.
2. Verify the intended X account is active and the composer contains the just-published episode link. Prefer Spotify's prefilled link and copy unless the user approved custom copy. Mark X `attempted`, select **Post**, wait for a success indication, mark X `confirmed`, then return to the Spotify tab.
3. From the same Spotify success screen, select the built-in **Facebook** share action.
4. Verify the intended Facebook destination/profile and audience, and that the just-published episode link is present. Mark Facebook `attempted`, select the final **Post** or **Share** action, wait for a success indication, mark Facebook `confirmed`, then return to Spotify.
5. On Spotify, mark Done `attempted`, select **Done**, and mark Done `confirmed` after Spotify exits the success screen. Only then begin the next episode.

UI labels may vary by locale or platform redesign; follow the semantic actions for X, Facebook, the final post/share control, and Spotify's completion control. Manually copy the episode link only if a built-in share flow fails and the user still wants that platform shared; reconcile any uncertain share first.

If login, checkpoint or CAPTCHA requires human action, pause for that action and then resume from the same stage. For an account/destination ambiguity, disabled final control or missing share control, inspect the available options and report a specific unresolved choice if needed. A failed social share does not change the episode's Spotify publication; record it and continue safely. Never repeat a social Post/Share while its ledger state is `attempted` or `confirmed`.

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
