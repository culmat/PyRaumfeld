#!/usr/bin/env python3
"""
Simple HTTP streaming server for GStreamer output
Serves MP3 stream with proper HTTP headers for Raumfeld
"""

import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import queue
import signal
import sys

# Configuration
PULSE_SOURCE = "raumfeld_sink.monitor"
LISTEN_PORT = 8080
BITRATE = 128  # Lower bitrate for less latency

# Queue for audio data - smaller queue = less buffering = lower latency
audio_queue = queue.Queue(maxsize=10)
gst_process = None

class StreamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/stream.mp3' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'audio/mpeg')
            self.send_header('Cache-Control', 'no-cache, no-store')
            self.send_header('Connection', 'close')
            self.send_header('icy-name', 'Raumfeld Stream')
            self.end_headers()
            
            try:
                while True:
                    chunk = audio_queue.get(timeout=5)
                    if chunk is None:
                        break
                    self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as e:
                print(f"Stream error: {e}")
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        print(f"[HTTP] {args[0]}")

def gstreamer_producer():
    """Run GStreamer and feed audio_queue"""
    global gst_process
    
    cmd = [
        'gst-launch-1.0',
        'pulsesrc', f'device={PULSE_SOURCE}',
        'buffer-time=20000',  # 20ms buffer (very low latency)
        'latency-time=10000',  # 10ms latency
        '!', 'audioconvert',
        '!', 'audioresample',
        '!', 'lamemp3enc', f'bitrate={BITRATE}', 'quality=9',  # quality=9 is faster encoding
        '!', 'fdsink', 'fd=1'
    ]
    
    print(f"Starting GStreamer: {' '.join(cmd)}")
    gst_process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0
    )
    
    try:
        while True:
            chunk = gst_process.stdout.read(2048)  # Smaller chunks for lower latency
            if not chunk:
                break
            # Non-blocking put with timeout to avoid excessive buffering
            try:
                audio_queue.put(chunk, timeout=0.1)
            except queue.Full:
                # Drop old data if queue is full to maintain low latency
                try:
                    audio_queue.get_nowait()
                    audio_queue.put(chunk, timeout=0.1)
                except:
                    pass
    except Exception as e:
        print(f"GStreamer error: {e}")
    finally:
        if gst_process:
            gst_process.terminate()

def signal_handler(sig, frame):
    """Handle Ctrl+C"""
    print("\nShutting down...")
    if gst_process:
        gst_process.terminate()
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start GStreamer producer thread
    producer = threading.Thread(target=gstreamer_producer, daemon=True)
    producer.start()
    
    # Start HTTP server
    server = HTTPServer(('0.0.0.0', LISTEN_PORT), StreamHandler)
    print(f"HTTP streaming server running on port {LISTEN_PORT}")
    print(f"Stream URL: http://192.168.178.20:{LISTEN_PORT}/stream.mp3")
    print("Press Ctrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        if gst_process:
            gst_process.terminate()

if __name__ == '__main__':
    main()
