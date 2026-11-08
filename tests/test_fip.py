# -*- coding: utf-8 -*-
"""Tests for the FIP follower. Run from the repository root: python3 -m unittest discover tests"""

import unittest

import fip

ICECAST = 'https://icecast.radiofrance.fr/'
FIP = ICECAST + 'fip-hifi.aac'


def song(start, title='Antidote', length=200, uuid=None):
    return {
        'startTime': start,
        'endTime': start + length,
        'firstLine': {'title': title},
        'secondLine': {'title': 'Chick Corea'},
        'visuals': {'card': {'src': 'https://img/abc'}},
        'songUuid': uuid or '%s-%s' % (title, start),
    }


PLACEHOLDER = {'startTime': None, 'endTime': None, 'firstLine': {'title': 'Le direct'}, 'songUuid': None}


class Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


class Feed:
    """Answers with whatever the test last set, per station, and counts the questions."""

    def __init__(self):
        self.answers = {}
        self.asked = []

    def set(self, station, now, upcoming=None, delay=30000):
        self.answers[station] = {'now': now, 'next': upcoming, 'delayToRefresh': delay}

    def __call__(self, station):
        self.asked.append(station)
        answer = self.answers[station]
        if isinstance(answer, Exception):
            raise answer
        return answer


def host_didl(item_id, title='FIP'):
    """A description the way the Raumfeld host hands it back."""
    return ('<?xml version="1.0"?>\n<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" '
            'xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
            'xmlns:dlna="urn:schemas-dlna-org:metadata-1-0/" xmlns:pv="http://www.pv.com/pvns/">'
            '<item id="%s" parentID="0" restricted="1"><dc:title>%s</dc:title>'
            '<upnp:class>object.item.audioItem.audioBroadcast</upnp:class></item></DIDL-Lite>\n'
            % (item_id, title))


class Zone:
    """A zone renderer that keeps what it is bent with, unless it refuses."""

    def __init__(self, uri=FIP, state='PLAYING', item_id='0', refuses=False, name='Living'):
        self.UDN = 'uuid:' + name
        self.Name = name
        self.state = state
        self.uri = uri
        self.didl = host_didl(item_id)
        self.refuses = refuses
        self.bent = []

    @property
    def transport_info(self):
        return {'CurrentTransportState': self.state}

    @property
    def media_info(self):
        return {'CurrentURI': self.uri, 'CurrentURIMetaData': self.didl}

    def bend(self, uri, meta):
        self.bent.append(meta)
        if not self.refuses:
            self.didl = meta


class StationsTest(unittest.TestCase):

    def test_a_fip_stream_names_its_station(self):
        self.assertEqual(fip.station_for(ICECAST + 'fipjazz-hifi.aac'), 'fip_jazz')
        self.assertEqual(fip.station_for(ICECAST + 'fip-midfi.mp3'), 'fip')
        self.assertEqual(fip.station_for(ICECAST + 'fipsacrefrancais-hifi.aac?id=1'), 'fip_sacre_francais')

    def test_any_other_stream_names_none(self):
        self.assertIsNone(fip.station_for('http://192.168.1.2:8097/flow/s/raumfeld_x/i/p.flac'))
        self.assertIsNone(fip.station_for(ICECAST + 'franceinter-hifi.aac'))
        self.assertIsNone(fip.station_for('https://example.org/fip-hifi.aac'))
        self.assertIsNone(fip.station_for(None))


class DescribeTest(unittest.TestCase):

    def test_a_song_is_described_with_its_station_as_album_and_a_sized_cover(self):
        self.assertEqual(fip.describe('fip_jazz', song(100)), {
            'title': 'Antidote', 'artist': 'Chick Corea', 'album': 'FIP Jazz',
            'art': 'https://img/abc/1000x1000', 'item_id': 'fiplay:fip_jazz:100',
        })

    def test_no_song_no_description(self):
        self.assertIsNone(fip.describe('fip', PLACEHOLDER))
        self.assertIsNone(fip.describe('fip', None))
        self.assertIsNone(fip.describe('fip', dict(song(5), firstLine={'title': ''})))

    def test_only_a_later_song_of_the_same_station_replaces_what_a_zone_shows(self):
        wanted = fip.describe('fip_jazz', song(200))
        self.assertTrue(fip.is_newer(wanted, 'fiplay:fip_jazz:100'))
        self.assertFalse(fip.is_newer(wanted, 'fiplay:fip_jazz:200'))
        self.assertFalse(fip.is_newer(wanted, 'fiplay:fip_jazz:300'))
        self.assertTrue(fip.is_newer(wanted, 'fiplay:fip_jazz'))
        self.assertTrue(fip.is_newer(wanted, 'fiplay:fip_rock:900'))
        self.assertTrue(fip.is_newer(wanted, '0'))
        self.assertTrue(fip.is_newer(wanted, None))

    def test_the_item_id_is_read_from_what_the_host_hands_back(self):
        self.assertEqual(fip.held_item_id(host_didl('fiplay:fip:42')), 'fiplay:fip:42')
        self.assertIsNone(fip.held_item_id(''))
        self.assertIsNone(fip.held_item_id('not xml'))


class StationWatcherTest(unittest.TestCase):

    def setUp(self):
        self.clock = Clock()
        self.feed = Feed()
        self.watcher = fip.StationWatcher('fip', self.feed, self.clock)

    def tick_at(self, now):
        self.clock.now = now
        self.watcher.next_fetch = 0
        self.watcher.tick()
        return self.watcher.shown

    def test_a_placeholder_does_not_replace_a_song(self):
        self.feed.set('fip', song(900))
        self.tick_at(1000)
        self.feed.set('fip', PLACEHOLDER)
        self.assertEqual(self.tick_at(1010)['startTime'], 900)

    def test_a_placeholder_is_shown_while_there_was_no_song(self):
        self.feed.set('fip', PLACEHOLDER)
        self.assertIs(self.tick_at(1000), PLACEHOLDER)

    def test_the_announced_song_is_shown_once_the_current_one_is_over_on_the_speaker(self):
        a, b = song(900, 'A', 200), song(1100, 'B')
        self.feed.set('fip', a, b)
        self.assertEqual(self.tick_at(1000)['firstLine']['title'], 'A')
        # the feed still says A, but A ended at 1100 and the speaker plays 8 s behind
        self.assertEqual(self.tick_at(1107)['firstLine']['title'], 'A')
        self.assertEqual(self.tick_at(1108)['firstLine']['title'], 'B')
        self.assertTrue(self.watcher.promoted)

    def test_the_old_song_is_no_news_once_the_next_one_is_shown(self):
        a, b = song(900, 'A', 200), song(1100, 'B')
        self.feed.set('fip', a, b)
        self.tick_at(1000)
        self.tick_at(1108)
        # around the change the feed swings back to A, with A again as "next"
        self.feed.set('fip', a, a)
        self.assertEqual(self.tick_at(1115)['firstLine']['title'], 'B')
        self.feed.set('fip', b)
        self.assertEqual(self.tick_at(1130)['firstLine']['title'], 'B')
        self.assertFalse(self.watcher.promoted)

    def test_it_asks_again_when_the_song_should_be_over(self):
        self.clock.now = 1000
        self.feed.set('fip', song(900, length=200), delay=300000)
        self.watcher.tick()
        self.assertEqual(self.watcher.next_fetch, 1108)

    def test_it_asks_every_few_seconds_while_the_song_is_overdue(self):
        self.clock.now = 1200
        self.feed.set('fip', song(900, length=200))
        self.watcher.tick()
        self.assertEqual(self.watcher.next_fetch, 1200 + fip.OVERDUE)

    def test_it_does_not_ask_before_it_is_due(self):
        self.feed.set('fip', song(900))
        self.clock.now = 1000
        self.watcher.tick()
        self.watcher.tick()
        self.assertEqual(len(self.feed.asked), 1)

    def test_a_feed_that_fails_keeps_the_song_and_backs_off(self):
        self.feed.set('fip', song(900))
        self.tick_at(1000)
        self.feed.answers['fip'] = OSError('down')
        self.assertEqual(self.tick_at(1010)['startTime'], 900)
        self.assertGreater(self.watcher.next_fetch, 1010)


class FollowerTest(unittest.TestCase):

    def setUp(self):
        self.clock = Clock()
        self.feed = Feed()
        self.feed.set('fip', song(900))
        self.follower = fip.Follower(self.feed, self.clock)

    def test_a_zone_playing_fip_is_told_the_song_once(self):
        zone = Zone()
        self.follower.tick([zone])
        self.follower.tick([zone])
        self.assertEqual(len(zone.bent), 1)
        self.assertIn('<dc:title>Antidote</dc:title>', zone.bent[0])
        self.assertIn('<upnp:album>FIP</upnp:album>', zone.bent[0])
        self.assertEqual(fip.held_item_id(zone.didl), 'fiplay:fip:900')

    def test_a_new_song_is_told_too(self):
        zone = Zone()
        self.follower.tick([zone])
        self.feed.set('fip', song(1100, 'B'))
        self.clock.now = 2000
        self.follower.tick([zone])
        self.assertEqual(len(zone.bent), 2)
        self.assertEqual(fip.held_item_id(zone.didl), 'fiplay:fip:1100')

    def test_other_zones_are_left_alone(self):
        paused = Zone(state='PAUSED_PLAYBACK', name='Kitchen')
        music_assistant = Zone(uri='http://nas:8097/flow/s/raumfeld_x/i/p.flac', name='Bar')
        line_in = Zone(uri='http://192.168.1.40:8888/stream.flac', name='Office')
        self.follower.tick([paused, music_assistant, line_in])
        self.assertEqual(paused.bent + music_assistant.bent + line_in.bent, [])
        self.assertEqual(self.feed.asked, [])

    def test_a_zone_that_refuses_is_not_asked_forever(self):
        zone = Zone(refuses=True)
        for _ in range(6):
            self.follower.tick([zone])
        self.assertEqual(len(zone.bent), fip.BEND_TRIES)

    def test_two_zones_on_one_station_share_one_question(self):
        self.follower.tick([Zone(name='Living'), Zone(name='Bar')])
        self.assertEqual(self.feed.asked, ['fip'])
        self.assertEqual(self.follower.next_due(), self.follower.watchers['fip'].next_fetch)

    def test_a_zone_that_fails_does_not_stop_the_others(self):
        class Broken(Zone):
            @property
            def transport_info(self):
                raise OSError('gone')

        good = Zone(name='Bar')
        with self.assertLogs('fip', 'WARNING'):
            self.follower.tick([Broken(), good])
        self.assertEqual(len(good.bent), 1)

    def test_no_zone_on_fip_nothing_is_due(self):
        self.follower.tick([Zone(state='STOPPED')])
        self.assertIsNone(self.follower.next_due())


if __name__ == '__main__':
    unittest.main()
