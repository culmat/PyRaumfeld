# -*- coding: utf-8 -*-
"""The DIDL-Lite description a stream is started or bent with."""

from xml.sax.saxutils import escape, quoteattr


def broadcast_didl(uri, title, artist=None, album=None, art=None, item_id=None):
    """Describe a stream as a broadcast item.

    As a broadcast the Raumfeld app shows these details, and the host follows the
    stream's ICY titles, which it ignores for a stream started without metadata. The
    host keeps the item id as given, so a client can recognise the item it described.

    :param uri: the stream
    :param title: what plays, shown as the title
    :param artist: its artist, if known
    :param album: its album, or the station, if known
    :param art: the address of its cover, if known
    :param item_id: the item's id, '0' when not given
    """
    path = uri.split('?')[0]
    mime = 'audio/mpeg' if path.endswith('.mp3') else 'audio/aac' if path.endswith('.aac') else '*'

    def tag(name, value):
        return '<' + name + '>' + escape(value) + '</' + name + '>' if value else ''

    return ('<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" '
            'xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/">'
            '<item id=' + quoteattr(item_id or '0') + ' parentID="0" restricted="1">'
            + tag('dc:title', title)
            + tag('upnp:artist', artist)
            + tag('upnp:album', album)
            + tag('upnp:albumArtURI', art) +
            '<upnp:class>object.item.audioItem.audioBroadcast</upnp:class>'
            '<res protocolInfo="http-get:*:' + mime + ':*">' + escape(uri) + '</res>'
            '</item></DIDL-Lite>')
