#!/usr/bin/env python3
"""Prepare selected audio for Spotify UI publishing and verify RSS appearance."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from html.parser import HTMLParser
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

IT = '{http://www.itunes.com/dtds/podcast-1.0.dtd}'
LIMIT = 10 * 1024 * 1024


def fingerprint(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def feed(raw):
    if len(raw) > LIMIT or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('Unsupported RSS document')
    root = ET.fromstring(raw)
    channel = root.find('channel')
    if root.tag != 'rss' or channel is None or not channel.findtext('title'):
        raise ValueError('Expected podcast RSS 2.0 with a show title')
    return channel


def fetch(url):
    parts = urlsplit(url)
    if parts.scheme != 'https' or not parts.netloc or parts.username or parts.password:
        raise ValueError('RSS must use HTTPS without embedded credentials')
    with urlopen(Request(url, headers={'User-Agent': 'voice-memos-to-podcast/1.0'}), timeout=30) as response:
        if urlsplit(response.url).scheme != 'https':
            raise ValueError('RSS redirected away from HTTPS')
        return feed(response.read(LIMIT + 1))


class Plain(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(value):
    parser = Plain()
    parser.feed(value or '')
    return ' '.join(' '.join(parser.parts).split())


def prepare(audio, channel, rss, title, description, explicit):
    audio = Path(audio).resolve(strict=True)
    if audio.suffix.lower() not in ('.mp3', '.m4a', '.wav') or audio.stat().st_size == 0:
        raise ValueError('Select a nonempty M4A, MP3 or WAV file; check playback before upload')
    if not title.strip() or not description.strip() or type(explicit) is not bool:
        raise ValueError('Title, description and explicit boolean are required')
    return {'version': 1, 'status': 'prepared_not_published',
            'prepared_at': datetime.now(timezone.utc).isoformat(),
            'audio': str(audio), 'sha256': fingerprint(audio), 'bytes': audio.stat().st_size,
            'rss': rss, 'show_title': channel.findtext('title'),
            'title': title, 'description': description, 'explicit': explicit,
            'baseline_guids': [x.findtext('guid') for x in channel.findall('item') if x.findtext('guid')]}


def verify(manifest, channel):
    if channel.findtext('title') != manifest['show_title']:
        raise ValueError('Show title changed; reconcile the feed before verification')
    baseline = set(manifest['baseline_guids'])
    candidates = []
    for item in channel.findall('item'):
        guid = item.findtext('guid')
        enclosure = item.find('enclosure')
        if (guid and guid not in baseline and item.findtext('title') == manifest['title']
                and plain(item.findtext('description')) == plain(manifest['description'])
                and item.findtext(IT + 'explicit') == str(manifest['explicit']).lower()
                and enclosure is not None and enclosure.get('url')):
            candidates.append({'guid': guid, 'episode_url': item.findtext('link'),
                               'audio_url': enclosure.get('url')})
    if len(candidates) == 1:
        return {'status': 'rss_observed_audio_identity_requires_host_check',
                'apple_status': 'not_verified', **candidates[0]}
    return {'status': 'pending' if not candidates else 'ambiguous', 'matches': len(candidates),
            'action': 'Inspect host drafts/published episodes; do not republish automatically.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    for name in ('audio', 'rss', 'title', 'description', 'out'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--explicit', choices=['true', 'false'], required=True)
    v = sub.add_parser('verify')
    v.add_argument('--manifest', required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.audio, fetch(args.rss), args.rss, args.title,
                         args.description, args.explicit == 'true')
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents losing the original pre-publication baseline.
        import os
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        print(json.dumps({'status': result['status'], 'manifest': str(path),
                          'show_title': result['show_title']}, ensure_ascii=False))
    else:
        manifest = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
        if fingerprint(manifest['audio']) != manifest['sha256']:
            raise ValueError('Selected file changed after preparation; reconcile before upload')
        result = verify(manifest, fetch(manifest['rss']))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result['status'] in ('pending', 'ambiguous'):
            sys.exit(2)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Stopped: {exc}', file=sys.stderr)
        sys.exit(1)
