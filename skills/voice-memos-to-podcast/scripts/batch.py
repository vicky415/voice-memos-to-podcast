#!/usr/bin/env python3
"""Private batch progress ledger for browser-driven Spotify publishing."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile


STAGES = ("spotify", "x", "facebook", "done")
VALUES = ("attempted", "confirmed", "failed")


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ordered_audio(paths):
    files = [Path(path).resolve(strict=True) for path in paths]
    if not files or len(set(files)) != len(files):
        raise ValueError("Select one or more distinct audio files.")
    if files != sorted(files, key=lambda path: (path.name.casefold(), str(path))):
        raise ValueError("Audio files must be supplied in filename order.")
    for path in files:
        if path.suffix.lower() not in (".m4a", ".mp3", ".wav") or path.stat().st_size == 0:
            raise ValueError(f"Not a nonempty supported audio file: {path}")
    return files


def folder_audio(folder):
    directory = Path(folder).resolve(strict=True)
    if not directory.is_dir():
        raise ValueError(f"Not a folder: {directory}")
    files = sorted(
        (path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".m4a"),
        key=lambda path: (path.name.casefold(), str(path)),
    )
    if not files:
        raise ValueError(f"No .m4a files found directly in: {directory}")
    return ordered_audio(files)


def initialize(paths, mode):
    return {
        "version": 2,
        "mode": mode,
        "episodes": [
            {
                "audio": str(path),
                "sha256": fingerprint(path),
                "spotify": "pending",
                "x": "not_applicable" if mode == "spotify-only" else "pending",
                "facebook": "not_applicable" if mode == "spotify-only" else "pending",
                "done": "pending",
            }
            for path in ordered_audio(paths)
        ],
    }


def progress(ledger):
    episodes = ledger["episodes"]
    next_index = next((index for index, episode in enumerate(episodes, 1) if episode["done"] != "confirmed"), None)
    return {
        "total": len(episodes),
        "completed": sum(episode["done"] == "confirmed" for episode in episodes),
        "next_episode": next_index,
        "episodes": [
            {
                "index": index,
                "filename": Path(episode["audio"]).name,
                "spotify": episode["spotify"],
                "x": episode["x"],
                "facebook": episode["facebook"],
                "done": episode["done"],
            }
            for index, episode in enumerate(episodes, 1)
        ],
    }


def write_new(path, ledger):
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        json.dump(ledger, stream, indent=2)
        stream.write("\n")


def replace(path, ledger):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".batch-", delete=False) as stream:
        temporary = Path(stream.name)
        os.chmod(temporary, 0o600)
        json.dump(ledger, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load(path):
    ledger = json.loads(path.read_text(encoding="utf-8"))
    if ledger.get("version") != 2 or ledger.get("mode") not in ("spotify-only", "spotify-x-facebook"):
        raise ValueError("Unsupported batch ledger.")
    for episode in ledger["episodes"]:
        audio = Path(episode["audio"])
        if not audio.is_file() or fingerprint(audio) != episode["sha256"]:
            raise ValueError(f"Selected audio changed or disappeared: {audio}")
    return ledger


def mark(ledger, index, stage, value):
    episodes = ledger["episodes"]
    if not 1 <= index <= len(episodes):
        raise ValueError("Episode index is out of range.")
    episode = episodes[index - 1]
    if stage not in STAGES or value not in VALUES:
        raise ValueError("Invalid stage or value.")
    if any(previous["done"] != "confirmed" for previous in episodes[: index - 1]):
        raise ValueError("Complete prior episodes before this one.")
    current = episode[stage]
    if current in ("confirmed", "not_applicable"):
        raise ValueError(f"{stage} is already {current}; do not repeat it.")
    if value == "attempted" and current == "attempted":
        raise ValueError(f"{stage} outcome is uncertain; inspect the platform before retrying.")
    if stage != "spotify" and episode["spotify"] != "confirmed":
        raise ValueError("Spotify publication must be confirmed first.")
    if stage == "x" and ledger["mode"] != "spotify-x-facebook":
        raise ValueError("X sharing is disabled in Spotify-only mode.")
    if stage == "facebook" and episode["x"] not in ("confirmed", "failed"):
        raise ValueError("Resolve the X step before Facebook.")
    if stage == "done" and (
        episode["x"] not in ("confirmed", "failed", "not_applicable")
        or episode["facebook"] not in ("confirmed", "failed", "not_applicable")
    ):
        raise ValueError("Resolve social steps before clicking Done.")
    if value == "confirmed" and current != "attempted":
        raise ValueError(f"Record {stage} as attempted before confirming it.")
    if value == "failed" and current != "attempted":
        raise ValueError(f"Record {stage} as attempted before marking failure.")
    episode[stage] = value
    episode[stage + "_updated_at"] = datetime.now(timezone.utc).isoformat()
    return ledger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("init")
    create.add_argument("--mode", choices=("spotify-only", "spotify-x-facebook"), default="spotify-only")
    create.add_argument("--out", type=Path, required=True)
    create.add_argument("--folder", type=Path, help="Select .m4a files directly in this folder, in filename order")
    create.add_argument("audio", nargs="*", help="Explicit audio paths in filename order (M4A, MP3 or WAV)")
    status = commands.add_parser("status")
    status.add_argument("--ledger", type=Path, required=True)
    update = commands.add_parser("mark")
    update.add_argument("--ledger", type=Path, required=True)
    update.add_argument("--index", type=int, required=True)
    update.add_argument("--stage", choices=STAGES, required=True)
    update.add_argument("--value", choices=VALUES, required=True)
    args = parser.parse_args()
    if args.command == "init":
        if bool(args.folder) == bool(args.audio):
            parser.error("Choose exactly one of --folder or explicit audio paths.")
        ledger = initialize(folder_audio(args.folder) if args.folder else args.audio, args.mode)
        write_new(args.out, ledger)
    else:
        ledger = load(args.ledger)
        if args.command == "mark":
            mark(ledger, args.index, args.stage, args.value)
            replace(args.ledger, ledger)
    print(json.dumps({"progress": progress(ledger), "ledger": ledger}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        sys.exit(1)
