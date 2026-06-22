import can
import time
import sys

def scan_can(interface):
    print(f"\n--- Scanning {interface} ---")
    try:
        # Initialize CAN-FD bus
        bus = can.interface.Bus(channel=interface, bustype='socketcan', fd=True)
        print(f"Connected to {interface}. Listening for 5 seconds...")
        
        start_time = time.time()
        found_ids = set()
        
        while time.time() - start_time < 5:
            message = bus.recv(0.5)
            if message:
                msg_id = hex(message.arbitration_id)
                if msg_id not in found_ids:
                    print(f"  [FOUND] Motor ID: {msg_id} | Data: {message.data.hex()}")
                    found_ids.add(msg_id)
        
        if not found_ids:
            print("  No messages received. Check cabling and power.")
        else:
            print(f"  Total unique IDs found: {len(found_ids)}")
            
        bus.shutdown()
    except Exception as e:
        print(f"  Error accessing {interface}: {e}")

if __name__ == "__main__":
    # Check if python-can is installed
    try:
        import can
    except ImportError:
        print("Error: 'python-can' is not installed. Run 'pip install python-can'")
        sys.exit(1)

    scan_can('can0')
    scan_can('can1')
