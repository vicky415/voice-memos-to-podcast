# GitHub release

Use a standalone repository. Verify authenticated GitHub owner against the requested destination. Include reusable source, synthetic examples, tests and MIT license. Exclude personal configurations, RSS snapshots, recordings, receipts and credentials.

Run `python3 -m unittest discover -s tests -v`, inspect the exact file list, then use authenticated GitHub CLI or supported browser upload. Example for a new repository, from package root:

```sh
git init -b main
git add README.md LICENSE .gitignore requirements-self-hosted.txt examples skills tests .github
git commit -m "Add Voice Memos podcast publishing skill"
gh repo create OWNER/voice-memos-to-podcast --public --source=. --remote=origin --push
```

Inspect any existing repository before updating; never force push. If authentication is missing, keep the completed local package and request sign-in, not tokens in chat. Verify the public repository and source files before claiming publication.
