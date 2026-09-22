import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/voice-memos-to-podcast/scripts'))
import podcast as p
import release as r


class StorageError(Exception):
    def __init__(self, code):
        self.response = {'Error': {'Code': code}}


class Tests(unittest.TestCase):
    def setUp(self):
        self.c = json.loads((ROOT / 'examples/show.example.json').read_text())
        self.item = p.episode(self.c, 'source-hash', 'audio-hash', 12,
                              '中文 & title', 'Description <safe>', False,
                              'Tue, 22 Sep 2026 00:00:00 +0000')

    def test_xml_roundtrip_and_stable_guid(self):
        root = p.new_feed(self.c, 'cover.jpg')
        self.assertTrue(p.merge(root, self.item, self.c))
        self.assertEqual(p.parse_feed(p.xml(root)).findtext('channel/item/title'), '中文 & title')
        again = copy.deepcopy(self.item)
        again.find('pubDate').text = 'Wed, 23 Sep 2026 00:00:00 +0000'
        self.assertFalse(p.merge(root, again, self.c))
        self.assertEqual(len(root.findall('channel/item')), 1)

    def test_metadata_conflict_does_not_duplicate(self):
        root = p.new_feed(self.c, 'cover.jpg')
        p.merge(root, self.item, self.c)
        changed = copy.deepcopy(self.item)
        changed.find('title').text = 'Changed'
        with self.assertRaises(ValueError):
            p.merge(root, changed, self.c)
        self.assertEqual(len(root.findall('channel/item')), 1)

    def test_foreign_feed_rejected(self):
        root = ET.fromstring('<rss><channel><title>Existing Anchor Show</title></channel></rss>')
        with self.assertRaises(ValueError):
            p.merge(root, self.item, self.c)

    def test_feed_url_change_rejected(self):
        root = p.new_feed(self.c, 'cover.jpg')
        changed = dict(self.c, public_base_url='https://other.example.org')
        with self.assertRaises(ValueError):
            p.merge(root, self.item, changed)

    def test_xml_entity_rejected(self):
        for parser in (p.parse_feed, r.feed):
            with self.assertRaises(ValueError):
                parser(b'<!DOCTYPE rss [<!ENTITY x "bad">]><rss/>')

    def test_config_validation(self):
        self.assertEqual(p.validate(self.c), self.c)
        for changes in ({'explicit': 'false'}, {'prefix': '../escape'},
                        {'public_base_url': 'http://example.org'},
                        {'public_base_url': 'https://user:secret@example.org'}):
            with self.assertRaises(ValueError):
                p.validate(dict(self.c, **changes))

    def test_public_range_failure(self):
        head = Mock(status=200, headers={'Content-Length': '12', 'Content-Type': 'audio/mpeg'})
        ranged = Mock(status=200, headers={})
        class Response:
            def __init__(self, response): self.response = response
            def __enter__(self): return self.response
            def __exit__(self, *args): pass
        opener = Mock(side_effect=[Response(head), Response(ranged)])
        with self.assertRaises(ValueError):
            p.check_asset('https://example.org/audio.mp3', 12, 'audio/mpeg', opener)

    def storage_run(self, client, check):
        with tempfile.TemporaryDirectory() as folder:
            audio, cover = Path(folder) / 'audio.mp3', Path(folder) / 'cover.jpg'
            audio.write_bytes(b'audio')
            cover.write_bytes(b'cover')
            return p.publish(client, self.c, self.item, audio, cover, 'cover.jpg', 'image/jpeg', check)

    def test_create_assets_before_conditional_feed(self):
        client = Mock()
        client.get_object.side_effect = StorageError('NoSuchKey')
        self.storage_run(client, Mock())
        calls = client.put_object.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertTrue(calls[0].kwargs['Key'].endswith('.mp3'))
        self.assertEqual(calls[-1].kwargs['IfNoneMatch'], '*')

    def test_access_denied_not_treated_as_empty_feed(self):
        client = Mock()
        client.get_object.side_effect = StorageError('AccessDenied')
        with self.assertRaises(StorageError):
            self.storage_run(client, Mock())
        client.put_object.assert_not_called()

    def test_asset_failure_never_writes_feed(self):
        client = Mock()
        client.get_object.side_effect = StorageError('NoSuchKey')
        with self.assertRaises(ValueError):
            self.storage_run(client, Mock(side_effect=ValueError('bad range')))
        self.assertEqual(len(client.put_object.call_args_list), 1)

    def test_existing_feed_retains_old_items_with_etag(self):
        root = p.new_feed(self.c, 'cover.jpg')
        old = copy.deepcopy(self.item)
        old.find('guid').text = 'old-guid'
        p.merge(root, old, self.c)
        client = Mock()
        client.get_object.return_value = {'Body': io.BytesIO(p.xml(root)), 'ETag': 'original-etag'}
        self.storage_run(client, Mock())
        write = client.put_object.call_args_list[-1].kwargs
        self.assertEqual(write['IfMatch'], 'original-etag')
        self.assertEqual(len(p.parse_feed(write['Body']).findall('channel/item')), 2)

    def test_conflicting_write_stops_without_retry(self):
        client = Mock()
        client.get_object.side_effect = StorageError('NoSuchKey')
        client.put_object.side_effect = [None, None, StorageError('PreconditionFailed')]
        with self.assertRaises(StorageError):
            self.storage_run(client, Mock())
        self.assertEqual(client.put_object.call_count, 3)

    def test_already_published_has_no_writes(self):
        root = p.new_feed(self.c, 'cover.jpg')
        p.merge(root, self.item, self.c)
        client = Mock()
        client.get_object.return_value = {'Body': io.BytesIO(p.xml(root)), 'ETag': 'etag'}
        self.assertEqual(self.storage_run(client, Mock())['status'], 'already_in_feed')
        client.put_object.assert_not_called()

    def test_manifest_fingerprint_and_verification(self):
        root = p.new_feed(self.c, 'cover.jpg')
        with tempfile.TemporaryDirectory() as folder:
            selected = Path(folder) / 'selected.m4a'
            selected.write_bytes(b'synthetic fixture, not playable audio')
            m = r.prepare(selected, root.find('channel'), 'https://example.org/feed.xml',
                          '中文 & title', 'Description <safe>', False)
            self.assertEqual(len(m['sha256']), 64)
            self.assertEqual(r.verify(m, root.find('channel'))['status'], 'pending')
            p.merge(root, self.item, self.c)
            self.assertTrue(r.verify(m, root.find('channel'))['status'].startswith('rss_observed'))
            m['baseline_guids'] = [self.item.findtext('guid')]
            self.assertEqual(r.verify(m, root.find('channel'))['status'], 'pending')

    def test_verification_ambiguity(self):
        root = p.new_feed(self.c, 'cover.jpg')
        p.merge(root, self.item, self.c)
        second = copy.deepcopy(self.item)
        second.find('guid').text = 'another'
        p.merge(root, second, self.c)
        m = {'show_title': self.c['title'], 'baseline_guids': [], 'title': '中文 & title',
             'description': 'Description <safe>', 'explicit': False}
        self.assertEqual(r.verify(m, root.find('channel'))['status'], 'ambiguous')


if __name__ == '__main__':
    unittest.main()
