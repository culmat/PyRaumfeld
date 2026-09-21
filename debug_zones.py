#!/usr/bin/env python3
"""
Debug script for Raumfeld zone issues
Helps diagnose why getZones() returns empty array
"""

import sys
import logging
import raumfeld

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)

def main():
    print("Raumfeld Zone Debug Script")
    print("=" * 60)
    
    # Enable debug logging
    print_section("1. Enabling Debug Logging")
    raumfeld.setLogging(logging.DEBUG)
    print("✓ Debug logging enabled")
    
    # Initialize the library
    print_section("2. Initializing Raumfeld Library")
    try:
        # Try auto-discovery first
        print("Attempting auto-discovery...")
        raumfeld.init()
        print(f"✓ Initialized successfully")
    except Exception as e:
        print(f"✗ Auto-discovery failed: {e}")
        print("\nTrying with explicit host IP...")
        host_ip = input("Enter Raumfeld host IP (or press Enter to skip): ").strip()
        if host_ip:
            try:
                raumfeld.init(hostIP=host_ip)
                print(f"✓ Initialized with host: {host_ip}")
            except Exception as e:
                print(f"✗ Failed to initialize: {e}")
                return 1
        else:
            print("Skipping initialization with host IP")
            return 1
    
    # Check host base URL
    print_section("3. Host Information")
    try:
        print(f"Host Base URL: {raumfeld.hostBaseURL}")
    except Exception as e:
        print(f"✗ Could not get host URL: {e}")
    
    # Check for zones
    print_section("4. Checking Zones")
    try:
        zones = raumfeld.getZones()
        print(f"Number of zones found: {len(zones)}")
        
        if zones:
            print("\nZone Details:")
            for i, zone in enumerate(zones, 1):
                print(f"\n  Zone {i}:")
                print(f"    Name: {zone.Name}")
                print(f"    UDN: {zone.UDN}")
                print(f"    Location: {zone.Location}")
                print(f"    Address: {zone.Address}")
                
                # Get rooms in zone
                try:
                    rooms = zone.getRooms()
                    print(f"    Rooms in zone: {len(rooms)}")
                    for room in rooms:
                        print(f"      - {room.Name} (UDN: {room.UDN})")
                except Exception as e:
                    print(f"    ✗ Could not get rooms: {e}")
        else:
            print("⚠ No zones found (empty array)")
    except Exception as e:
        print(f"✗ Error getting zones: {e}")
        import traceback
        traceback.print_exc()
    
    # Check for unassigned rooms
    print_section("5. Checking Unassigned Rooms")
    try:
        unassigned = raumfeld.getUnassignedRooms()
        print(f"Number of unassigned rooms: {len(unassigned)}")
        
        if unassigned:
            print("\nUnassigned Room Details:")
            for i, room in enumerate(unassigned, 1):
                print(f"\n  Room {i}:")
                print(f"    Name: {room.Name}")
                print(f"    UDN: {room.UDN}")
                
                # Try to get renderers
                try:
                    renderers = room.getRenderers()
                    print(f"    Renderers: {len(renderers)}")
                    for renderer in renderers:
                        print(f"      - {renderer.Name}")
                except Exception as e:
                    print(f"    ✗ Could not get renderers: {e}")
        else:
            print("No unassigned rooms found")
    except Exception as e:
        print(f"✗ Error getting unassigned rooms: {e}")
        import traceback
        traceback.print_exc()
    
    # Check media server
    print_section("6. Checking Media Server")
    try:
        media_server = raumfeld.getMediaServer()
        if media_server:
            print(f"Media Server UDN: {media_server.UDN}")
            print(f"Media Server Location: {media_server.Location}")
        else:
            print("⚠ No media server found")
    except Exception as e:
        print(f"✗ Error getting media server: {e}")
    
    # Summary
    print_section("7. Summary & Recommendations")
    
    try:
        zones = raumfeld.getZones()
        unassigned = raumfeld.getUnassignedRooms()
        
        if not zones and not unassigned:
            print("⚠ ISSUE: No zones AND no unassigned rooms found!")
            print("\nPossible causes:")
            print("  1. Raumfeld system is not reachable")
            print("  2. Network/firewall issues")
            print("  3. Raumfeld service not running")
            print("\nRecommendations:")
            print("  - Check if Raumfeld devices are powered on")
            print("  - Verify network connectivity to the host")
            print("  - Try restarting the Raumfeld host device")
            print("  - Check firewall settings")
        
        elif not zones and unassigned:
            print("✓ DIAGNOSIS: Rooms exist but are not grouped into zones")
            print(f"  Found {len(unassigned)} unassigned room(s)")
            print("\nRecommendations:")
            print("  - Use the Raumfeld app to group rooms into zones")
            print("  - OR use connectRoomToZone() to create zones programmatically:")
            if unassigned:
                print(f"\n  Example:")
                print(f"    raumfeld.connectRoomToZone('{unassigned[0].UDN}')")
        
        elif zones:
            print(f"✓ SUCCESS: Found {len(zones)} zone(s)")
            if unassigned:
                print(f"  Also found {len(unassigned)} unassigned room(s)")
    
    except Exception as e:
        print(f"Could not generate summary: {e}")
    
    print("\n" + "=" * 60)
    print("Debug script completed")
    print("=" * 60 + "\n")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
