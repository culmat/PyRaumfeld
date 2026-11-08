# -*- coding: utf-8 -*-
"""Keep the Raumfeld zones that play FIP showing the song that plays.

FIP's Icecast streams carry no song details, and a zone keeps the description a stream
was started with. So the Raumfeld app would name only the station, or the first song,
for as long as a stream runs. The follower asks a fip-metadata service
(https://github.com/harperreed/fip-metadata-server) what each station a zone plays is
playing, and replaces the zone's description at every song change through
BendAVTransportURI, which leaves the stream playing. Music Assistant's Raumfeld provider
does the same for the streams it serves.

Song changes follow the rules of FIPlay's StationWatcher, so the zone names the same
song at the same moment as FIPlay's screen. Radio France's feed names a new song 20 to 40
seconds late and flickers around the change: a programme placeholder does not replace a
song, the old song is no news once the next one is shown, and the song the feed announced
as next is shown once the current one should be over on the speaker.

The description's item id is ``fiplay:<station>:<song start>``, the scheme FIPlay used
when it did this from the browser. A zone is only ever moved on to a later song of the
station it plays, so two writers with the same feed agree rather than swing it back and
forth.

This module imports neither raumfeld nor bottle: zones and the feed are handed in, so it
can be tested on its own.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
import xml.etree.ElementTree as ET
from contextlib import nullcontext
from urllib.parse import urlsplit

from didl import broadcast_didl

log = logging.getLogger(__name__)

# The stations FIPlay offers, by the key fip-metadata knows them under, with the name
# the Raumfeld app shows as album.
STATIONS = {
    'fip': 'FIP',
    'fip_reggae': 'FIP Reggae',
    'fip_jazz': 'FIP Jazz',
    'fip_world': 'FIP World',
    'fip_groove': 'FIP Groove',
    'fip_nouveautes': 'FIP Nouveautés',
    'fip_electro': 'FIP Electro',
    'fip_sacre_francais': 'FIP Sacré Français',
    'fip_rock': 'FIP Rock',
    'fip_metal': 'FIP Metal',
    'fip_hiphop': 'FIP Hiphop',
    'fip_pop': 'FIP Pop',
}

# The streams are https://icecast.radiofrance.fr/<slug>-<quality>.<ext>, where <slug> is
# the station key without underscores.
_BY_SLUG = {key.replace('_', ''): key for key in STATIONS}

ID_PREFIX = 'fiplay'

# Radio France serves a cover at the size its address ends with; the bare address is a
# 404. The size is the one Music Assistant gives the zone.
COVER_SIZE = '1000x1000'

# How long the audio trails the feed's clock, in seconds: the HLS live edge trails the
# studio by about five, and a player buffers a few more.
STREAM_DELAY = 8
# How often to ask again while the song shown is overdue.
OVERDUE = 3
# While the song shown came from the feed's "next", look for its confirmation this often.
CONFIRM = 10
MIN_DELAY = 1
MAX_DELAY = 120

# How often a zone that does not take a description is asked again for the same song.
BEND_TRIES = 3

_DIDL_ITEM = '{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}item'


def station_for(url):
    """The station key of a FIP Icecast stream, or None for any other stream."""
    parts = urlsplit(url or '')
    if parts.hostname != 'icecast.radiofrance.fr':
        return None
    return _BY_SLUG.get(parts.path.rsplit('/', 1)[-1].split('-')[0])


def _is_song(track):
    """A track with a start time is a song; without one it is a programme placeholder."""
    return bool(track and track.get('startTime'))


def _title(track, line):
    return ((track or {}).get(line) or {}).get('title') or None


def _same_track(a, b):
    """The same track: by the feed's id when both carry one, else by title and start."""
    if not a or not b:
        return False
    if a.get('songUuid') and b.get('songUuid'):
        return a['songUuid'] == b['songUuid']
    return _title(a, 'firstLine') == _title(b, 'firstLine') and a.get('startTime') == b.get('startTime')


def describe(station, song):
    """The details a zone playing the station should show for the song, or None without one.

    :param station: the station key, e.g. ``fip_jazz``
    :param song: the song in fip-metadata's shape, or None
    """
    if not _is_song(song) or not _title(song, 'firstLine'):
        return None
    cover = ((song.get('visuals') or {}).get('card') or {}).get('src')
    return {
        'title': _title(song, 'firstLine'),
        'artist': _title(song, 'secondLine'),
        'album': STATIONS[station],
        'art': '%s/%s' % (cover, COVER_SIZE) if cover else None,
        'item_id': '%s:%s:%s' % (ID_PREFIX, station, song['startTime']),
    }


def is_newer(wanted, held_id):
    """Whether a description names a later song than the item a zone holds.

    Anything the zone holds that was not described this way, or for another station, is
    replaced.
    """
    _, station, start = wanted['item_id'].split(':')
    held = (held_id or '').split(':')
    if len(held) < 2 or held[0] != ID_PREFIX or held[1] != station:
        return True
    try:
        return int(start) > int(held[2]) if len(held) > 2 else True
    except ValueError:
        return True


def held_item_id(didl):
    """The item id in a zone's CurrentURIMetaData, or None."""
    if not didl:
        return None
    try:
        item = ET.fromstring(didl.strip()).find(_DIDL_ITEM)
    except ET.ParseError:
        return None
    return item.get('id') if item is not None else None


def http_feed(base_url, timeout=5):
    """A feed that asks the fip-metadata service at ``base_url`` about one station."""
    base = base_url.rstrip('/')

    def fetch(station):
        with urllib.request.urlopen('%s/api/metadata/%s' % (base, station), timeout=timeout) as response:
            return json.load(response)

    return fetch


def _clamp(value, low, high):
    return min(max(value, low), high)


class StationWatcher:
    """The song to show for one station, from a feed that is late and noisy around changes.

    A port of FIPlay's src/StationWatcher.js, driven by tick() instead of timers.
    """

    def __init__(self, station, fetch, clock=time.time):
        self.station = station
        self.fetch = fetch
        self.clock = clock
        self.shown = None      # the song shown
        self.promoted = False  # whether it came from the feed's "next" rather than its "now"
        self.feed_now = None   # the last song the feed itself called current
        self.announced = None  # the last useful "next" the feed announced
        self.next_fetch = 0.0
        self.errors = 0

    def tick(self):
        """Ask the feed if it is time to, and take in its answer."""
        now = self.clock()
        if now < self.next_fetch:
            return
        try:
            answer = self.fetch(self.station)
        except Exception as err:  # the feed is a nicety: keep what is shown and try again
            self.errors += 1
            self.next_fetch = now + min(MAX_DELAY, OVERDUE * 2 ** self.errors)
            log.debug('No song details for %s: %s', self.station, err)
            return
        self.errors = 0
        self.adopt(answer, now)
        self.next_fetch = now + self.refresh_delay(answer, now)

    def refresh_delay(self, answer, now):
        """How long to wait before asking again.

        The feed's own delayToRefresh outlasts the song by half a minute or so, so ask
        when the song shown should be over on the speaker, and every few seconds while
        the answer is still the old one.
        """
        suggested = (answer.get('delayToRefresh') or 30000) / 1000
        if not _is_song(self.shown):
            return _clamp(suggested, OVERDUE, MAX_DELAY)
        wait = (self.shown.get('endTime') or 0) + STREAM_DELAY - now
        if wait <= 0:
            return OVERDUE
        return _clamp(min(suggested, wait, CONFIRM if self.promoted else MAX_DELAY), MIN_DELAY, MAX_DELAY)

    def adopt(self, answer, now):
        """Decide what an answer means for the song shown."""
        current = answer.get('now')
        old_news = self.promoted and _same_track(current, self.feed_now)
        placeholder = not _is_song(current) and _is_song(self.shown)
        if not old_news and not placeholder:
            if _is_song(current):
                self.feed_now = current
            self.shown, self.promoted = current, False
        self.remember(answer.get('next'))
        self.promote(now)

    def remember(self, upcoming):
        """Keep the last useful announcement of what follows."""
        shown = self.shown

        def stale(track):
            return _is_song(shown) and track['startTime'] <= shown['startTime']

        if self.announced and stale(self.announced):
            self.announced = None
        if _is_song(upcoming) and not stale(upcoming) and not _same_track(upcoming, shown):
            self.announced = upcoming

    def promote(self, now):
        """Move on to the announced next song once it is due."""
        upcoming = self.announced
        if self.promoted or not upcoming:
            return
        ends_at = (self.shown.get('endTime') or 0) if _is_song(self.shown) else 0
        if now < max(ends_at, upcoming['startTime']) + STREAM_DELAY:
            return
        log.debug('%s moves on to the announced next song before the feed does', self.station)
        self.announced = None
        self.shown, self.promoted = upcoming, True


class Follower:
    """Keeps each zone that plays a FIP stream showing the station's current song."""

    def __init__(self, fetch, clock=time.time):
        self.fetch = fetch
        self.clock = clock
        self.watchers = {}
        # zone UDN -> (item id last sent, how often)
        self.tries = {}
        self.active = set()

    def tick(self, zones, lock_for=lambda udn: nullcontext()):
        """Look at every zone once, and correct what a zone playing FIP shows.

        :param zones: the zones to look at
        :param lock_for: the lock a zone's playback commands take, so a zone is not
            described while it moves to another stream
        """
        self.active = set()
        for zone in zones:
            try:
                with lock_for(zone.UDN):
                    self.follow(zone)
            except Exception as err:  # one zone that does not answer must not stop the others
                log.warning('Could not follow %s: %s', getattr(zone, 'Name', zone), err)

    def next_due(self):
        """When a station a zone plays next wants its feed asked, or None."""
        due = [self.watchers[s].next_fetch for s in self.active]
        return min(due) if due else None

    def follow(self, zone):
        if zone.transport_info.get('CurrentTransportState') != 'PLAYING':
            return
        info = zone.media_info
        uri = info.get('CurrentURI') or ''
        station = station_for(uri)
        if not station:
            return  # another stream, such as Music Assistant's own, a Line-In or another app's
        self.active.add(station)
        watcher = self.watchers.get(station)
        if watcher is None:
            watcher = self.watchers[station] = StationWatcher(station, self.fetch, self.clock)
        watcher.tick()
        wanted = describe(station, watcher.shown)
        if not wanted or not is_newer(wanted, held_item_id(info.get('CurrentURIMetaData'))):
            return
        sent, count = self.tries.get(zone.UDN, (None, 0))
        count = count + 1 if sent == wanted['item_id'] else 1
        if count > BEND_TRIES:
            return
        self.tries[zone.UDN] = (wanted['item_id'], count)
        zone.bend(uri, broadcast_didl(uri, **wanted))
        log.info('%s now shows %s (%s)', zone.Name, wanted['title'], wanted['item_id'])
