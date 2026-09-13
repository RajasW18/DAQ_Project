from core.hardware import hw
import constants

# Force simulation off just for this test
constants.SIMULATION_MODE = False

print("Searching for hardware on USB ports...")
success = hw.detect_port()

if success:
    print(f"\n✅ SUCCESS! Connected to the ESP32 on: {hw.port_name}")
else:
    print("\n❌ FAILED. Could not find the ESP32.")
    print(f"Error details: {hw.last_error}")