#!/usr/bin/env python3
"""Publish one explicitly selected recording to an S3-backed podcast RSS feed."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

IT = 'http://www.itunes.com/dtds/podcast-1.0.dtd'
ATOM = 'http://www.w3.org/2005/Atom'
VM = 'urn:voice-memos-to-podcast:v1'
for prefix, uri in [('itunes', IT), ('atom', ATOM), ('vm', VM)]:
    ET.register_namespace(prefix, uri)


def text(parent, tag, value, **attrs):
    node = ET.SubElement(parent, tag, attrs)
    node.text = str(value)
    return node


def https(value):
    parts = urlsplit(value)
    if (parts.scheme != 'https' or not parts.netloc or parts.username
            or parts.password or parts.query or parts.fragment
            or not value.isascii() or any(c.isspace() for c in value)):
        raise ValueError('Use a permanent public HTTPS URL without credentials or query strings.')
    return value


def validate(config):
    for field in ['show_id', 'title', 'description', 'author', 'email', 'language',
                  'category', 'website', 'public_base_url', 'bucket', 'prefix']:
        if not isinstance(config.get(field), str) or not config[field].strip():
            raise ValueError('Missing configuration: ' + field)
    if not re.fullmatch(r'[a-z0-9-]+', config['show_id']):
        raise ValueError('show_id must contain lowercase ASCII letters, digits or hyphens.')
    if not re.fullmatch(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*', config['prefix']):
        raise ValueError('prefix must be a nonempty relative ASCII storage path.')
    if type(config.get('explicit')) is not bool:
        raise ValueError('explicit must be a JSON boolean.')
    https(config['public_base_url'])
    https(config['website'])
    if config.get('endpoint_url'):
        https(config['endpoint_url'])
    return config


def key(config, name):
    return config['prefix'] + '/' + name


def public(config, name):
    # public_base_url maps directly to the storage prefix, not the bucket root.
    return config['public_base_url'].rstrip('/') + '/' + name


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def cover_asset(path):
    from PIL import Image
    with Image.open(path) as image:
        if (image.format not in ('JPEG', 'PNG') or image.mode != 'RGB'
                or image.width != image.height or not 1400 <= image.width <= 3000):
            raise ValueError('Cover must be RGB JPG/PNG, square, 1400–3000 pixels, without alpha.')
        image.verify()
        ext, mime = ('jpg', 'image/jpeg') if image.format == 'JPEG' else ('png', 'image/png')
    return 'cover-' + digest(path) + '.' + ext, mime


def new_feed(c, artwork):
    root = ET.Element('rss', {'version': '2.0'})
    channel = ET.SubElement(root, 'channel')
    for tag, value in [('title', c['title']), ('description', c['description']),
                       ('link', c['website']), ('language', c['language']),
                       ('{%s}author' % IT, c['author']),
                       ('{%s}explicit' % IT, str(c['explicit']).lower()),
                       ('{%s}type' % IT, 'episodic'), ('{%s}show' % VM, c['show_id'])]:
        text(channel, tag, value)
    ET.SubElement(channel, '{%s}category' % IT, {'text': c['category']})
    ET.SubElement(channel, '{%s}image' % IT, {'href': public(c, artwork)})
    owner = ET.SubElement(channel, '{%s}owner' % IT)
    text(owner, '{%s}name' % IT, c['author'])
    text(owner, '{%s}email' % IT, c['email'])
    ET.SubElement(channel, '{%s}link' % ATOM,
                  {'href': public(c, 'feed.xml'), 'rel': 'self', 'type': 'application/rss+xml'})
    return root


def episode(c, source_hash, audio_hash, size, title, description, explicit, date):
    node = ET.Element('item')
    text(node, 'title', title)
    text(node, 'description', description)
    text(node, 'guid', 'urn:vm:' + c['show_id'] + ':' + source_hash, isPermaLink='false')
    text(node, 'pubDate', date)
    text(node, '{%s}explicit' % IT, str(explicit).lower())
    text(node, '{%s}episodeType' % IT, 'full')
    ET.SubElement(node, 'enclosure', {'url': public(c, audio_hash + '.mp3'),
                                     'length': str(size), 'type': 'audio/mpeg'})
    return node


def merge(root, item, config):
    channel = root.find('channel')
    if root.tag != 'rss' or channel is None or channel.findtext('{%s}show' % VM) != config['show_id']:
        raise ValueError('Existing feed is not owned by this configuration; migration is not supported.')
    self_link = channel.find('{%s}link' % ATOM)
    if self_link is None or self_link.get('href') != public(config, 'feed.xml'):
        raise ValueError('Existing feed URL differs; do not silently migrate it.')
    for old in channel.findall('item'):
        if old.findtext('guid') == item.findtext('guid'):
            for field in ['title', 'description', '{%s}explicit' % IT]:
                if old.findtext(field) != item.findtext(field):
                    raise ValueError('Recording is already published with different metadata; editing requires a separate workflow.')
            return False
    channel.insert(0, item)
    return True


def xml(root):
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def parse_feed(raw):
    if len(raw) > 10 * 1024 * 1024 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('Unsupported or oversized RSS document.')
    return ET.fromstring(raw)


def check_asset(url, size, mime, opener=urlopen):
    with opener(Request(url, method='HEAD'), timeout=30) as response:
        if response.status != 200 or int(response.headers.get('Content-Length', -1)) != size:
            raise ValueError('Public asset HEAD/length check failed: ' + url)
        if response.headers.get('Content-Type', '').split(';')[0] != mime:
            raise ValueError('Public asset MIME check failed: ' + url)
    with opener(Request(url, headers={'Range': 'bytes=0-0'}), timeout=30) as response:
        if (response.status != 206 or response.headers.get('Content-Range') != f'bytes 0-0/{size}'
                or len(response.read(2)) != 1):
            raise ValueError('Public asset byte-range check failed: ' + url)


def error_code(exc):
    return getattr(exc, 'response', {}).get('Error', {}).get('Code', '')


def publish(client, c, item, audio, cover, artwork, cover_mime, check=check_asset):
    try:
        remote = client.get_object(Bucket=c['bucket'], Key=key(c, 'feed.xml'))
    except Exception as exc:
        if error_code(exc) != 'NoSuchKey':
            raise
        root, condition = new_feed(c, artwork), {'IfNoneMatch': '*'}
    else:
        with remote['Body'] as body:
            root = parse_feed(body.read(10 * 1024 * 1024 + 1))
        condition = {'IfMatch': remote['ETag']}
    if not merge(root, item, c):
        return {'status': 'already_in_feed', 'rss': public(c, 'feed.xml')}
    # Content-addressed assets go first; RSS is the only mutable publication pointer.
    for path, name, mime in [(audio, digest(audio) + '.mp3', 'audio/mpeg'),
                              (cover, artwork, cover_mime)]:
        with open(path, 'rb') as body:
            client.put_object(Bucket=c['bucket'], Key=key(c, name), Body=body,
                              ContentType=mime, CacheControl='public, max-age=31536000, immutable')
        check(public(c, name), Path(path).stat().st_size, mime)
    # Existing show metadata is preserved, including its previous cover.
    client.put_object(Bucket=c['bucket'], Key=key(c, 'feed.xml'), Body=xml(root),
                      ContentType='application/rss+xml; charset=utf-8',
                      CacheControl='public, max-age=60', **condition)
    return {'status': 'rss_written_platform_ingestion_pending', 'rss': public(c, 'feed.xml')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--audio', required=True)
    parser.add_argument('--cover', required=True)
    parser.add_argument('--title', required=True)
    parser.add_argument('--description', required=True)
    parser.add_argument('--explicit', choices=['true', 'false'], required=True)
    parser.add_argument('--out', required=True, help='New private output directory for this attempt')
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--publish', action='store_true', help='Authorize public audio and RSS writes')
    args = parser.parse_args()
    c = validate(json.loads(Path(args.config).read_text(encoding='utf-8')))
    source, cover = Path(args.audio).resolve(strict=True), Path(args.cover).resolve(strict=True)
    if not args.title.strip() or not args.description.strip():
        raise ValueError('Episode title and description cannot be empty.')
    artwork, mime = cover_asset(cover)
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    # Snapshot only the selected file so iCloud changes cannot alter it mid-conversion.
    import shutil
    with tempfile.TemporaryDirectory(prefix='vm-podcast-') as scratch:
        selected = Path(scratch) / ('selected' + source.suffix)
        shutil.copyfile(source, selected)
        source_hash = digest(selected)
        audio = out / 'episode.mp3'
        subprocess.run([args.ffmpeg, '-nostdin', '-v', 'error', '-i', str(selected),
                        '-map', '0:a:0', '-vn', '-map_metadata', '-1', '-c:a', 'libmp3lame',
                        '-b:a', '128k', '-ar', '44100', '-ac', '2', '-n', str(audio)], check=True)
    if audio.stat().st_size == 0 or audio.stat().st_size > 1024**3:
        raise ValueError('Audio must be nonempty and at most 1 GiB for this helper.')
    item = episode(c, source_hash, digest(audio), audio.stat().st_size, args.title,
                   args.description, args.explicit == 'true', format_datetime(datetime.now(timezone.utc)))
    preview = new_feed(c, artwork)
    merge(preview, item, c)
    (out / 'preview.xml').write_bytes(xml(preview))
    result = {'status': 'prepared_not_published', 'guid': item.findtext('guid'),
              'rss': public(c, 'feed.xml'), 'preview': str(out / 'preview.xml')}
    if args.publish:
        import boto3
        from botocore.config import Config
        client = boto3.client('s3', endpoint_url=c.get('endpoint_url'),
                              region_name=c.get('region', 'us-east-1'),
                              config=Config(retries={'total_max_attempts': 1},
                                            connect_timeout=15, read_timeout=60))
        result.update(publish(client, c, item, audio, cover, artwork, mime))
    (out / 'receipt.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Stopped ({type(exc).__name__}): {exc}\nIf a network write was attempted, its outcome may be uncertain. '
              'Inspect the remote RSS before retrying the same recording; never generate a new GUID to bypass a failure.', file=sys.stderr)
        sys.exit(1)
