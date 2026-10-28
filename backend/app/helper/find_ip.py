import socket

def get_private_ip():
    # Create a temporary UDP socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connect to a dummy public IP address and port.
        # This doesn't actually send any data or require an active connection,
        # but it forces the OS to pick the correct local network interface.
        s.connect(("8.8.8.8", 80))
        private_ip = s.getsockname()[0]
    except Exception:
        # Fallback to localhost if not connected to any network
        private_ip = "127.0.0.1"
    finally:
        s.close()
    return private_ip