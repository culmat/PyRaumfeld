#!/usr/bin/env python3
"""Play a stream on Raumfeld zone with diagnostics"""

import sys
import time
import raumfeld

STREAM_URL = "http://192.168.178.20:8080/stream.mp3"

# Metadata for the stream
METADATA = '''<?xml version="1.0"?>
<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" 
           xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" 
           xmlns:dc="http://purl.org/dc/elements/1.1/">
  <item id="1" parentID="0" restricted="1">
    <dc:title>Local Audio Stream</dc:title>
    <upnp:class>object.item.audioItem.audioBroadcast</upnp:class>
    <res protocolInfo="http-get:*:audio/mpeg:*">%s</res>
  </item>
</DIDL-Lite>''' % STREAM_URL

# Initialize
print("Initializing Raumfeld...")
raumfeld.init()

# Get zones
zones = raumfeld.getZones()
if not zones:
    print("No zones found!")
    sys.exit(1)

# Use the first zone
zone = zones[0]
print(f"Found zone: {zone.Name}")
print(f"Zone address: {zone.Address}")

# Check current state
print(f"\nCurrent volume: {zone.volume}")
print(f"Muted: {zone.mute}")
print(f"Transport state: {zone.transport_info['CurrentTransportState']}")

# Unmute and set volume if needed
if zone.mute:
    print("Unmuting zone...")
    zone.mute = False

if zone.volume < 20:
    print(f"Setting volume to 30 (was {zone.volume})...")
    zone.volume = 30

# Play the stream with metadata
print(f"\nPlaying stream: {STREAM_URL}")
print("With proper DIDL-Lite metadata...")
zone.play(uri=STREAM_URL, meta=METADATA)

# Monitor status for a few seconds
for i in range(5):
    time.sleep(1)
    state = zone.transport_info['CurrentTransportState']
    print(f"[{i+1}s] Transport state: {state}")
    if state == "PLAYING":
        print("\n✓ Stream is PLAYING!")
        break
    elif state == "STOPPED":
        print("\n✗ Stream STOPPED - Raumfeld couldn't play the stream")
        print("Possible issues:")
        print("  1. Raumfeld device can't reach 192.168.178.20:8080")
        print("  2. Stream format not supported")
        print("  3. Missing proper HTTP headers")
        break
else:
    print(f"\n⚠ Still in state: {zone.transport_info['CurrentTransportState']}")
    print("\nCurrent media info:")
    print(f"  URI: {zone.media_info['CurrentURI']}")
    print(f"  Duration: {zone.media_info['MediaDuration']}")
    
print("\nTip: Test if Raumfeld can reach the stream:")
print(f"  From Raumfeld device, try: curl http://192.168.178.20:8080/")