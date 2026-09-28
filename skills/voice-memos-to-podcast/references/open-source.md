# GitHub release

Use a standalone repository. Verify the authenticated GitHub owner against the requested destination. Include the reusable skill source and its documentation. Exclude personal configurations, RSS snapshots, recordings, receipts and credentials.

For v2 releases, verify that `VERSION`, the `metadata.version` value in `SKILL.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, and the GitHub release/tag all agree. Confirm that Spotify-only remains the default and that the optional X/Facebook instructions are documented as a post-publication branch rather than a replacement upload path.

Run the skill validator, Python syntax checks and tests, then inspect the exact file list before pushing to the existing authenticated GitHub remote. Never create a new repository for an upgrade.

```sh
python3 -m unittest discover -s tests -v
git status
git diff --check
git add README.md CHANGELOG.md RELEASE_NOTES.md VERSION .gitignore skills tests
git diff --cached
git commit -m "feat: add X and Facebook sharing workflow for v2.0"
git push
```

Inspect the branch and remote before updating; never force push. Publish a `v2.0.0` GitHub release titled “Voice Memos to Podcast Skill v2.0” using `RELEASE_NOTES.md`. If authentication or the remote is missing, stop after preparing the local commit and request the single needed action. Verify the remote source files and release URL before claiming publication.
