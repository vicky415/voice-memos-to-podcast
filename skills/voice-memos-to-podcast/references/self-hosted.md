# Optional new S3-backed show

Only use when the user chooses a new self-hosted show. For an existing Spotify show use `spotify.md`. The helper refuses unrelated feeds and changed feed URLs.

Requires Python 3.10+, FFmpeg with libmp3lame, `requirements-self-hosted.txt`, and an already configured S3-compatible bucket/public HTTPS CDN. The provider must enforce conditional PutObject IfMatch/IfNoneMatch. Use Boto3's environment/profile credential chain, never credentials in JSON. Storage/CDN setup and costs are separate.

Copy `examples/show.example.json` to private `show.local.json`. `public_base_url` maps to the object prefix, e.g. prefix `my-show` → `https://cdn.example.org/my-show`. Fill real metadata and a valid Apple category. Cover: RGB JPG/PNG, square, 1400–3000 pixels, no transparency. The owner email becomes public in RSS.

```sh
python3 skills/voice-memos-to-podcast/scripts/podcast.py \
  --config '/private/path/show.local.json' --audio '/private/path/selected.m4a' \
  --cover '/private/path/cover.jpg' --title 'Episode title' \
  --description 'Episode description' --explicit false --out '/private/path/attempt-001'
```

Default: local MP3, single-episode preview and receipt only. Preview is not a replacement for an existing feed. Add `--publish` for an authorized release, using a new output directory. Assets upload first, public HEAD/byte-range checks follow, then RSS is merged and conditionally written. Existing show metadata is preserved; JSON changes do not update published show metadata.

Same source bytes retain the episode GUID. Edited/re-exported files may have new bytes; reconcile before republishing. The helper stops on failed checks or uncertain writes. On 409/412 inspect current RSS before retrying; never disable conditional writes. Partial asset uploads may remain after failures. Successful RSS writing does not prove public CDN or platform ingestion; confirm the GUID from public RSS and platform listings separately.

Submit this permanent RSS once to Spotify and Apple. Account verification/review remains necessary. The helper does not create storage, migrate episodes, schedule releases or manage platform accounts.
