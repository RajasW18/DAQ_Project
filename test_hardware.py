"""
Test the hardware module in simulation mode.
Run from SpectraSoft/ folder:  python test_hardware.py

Does NOT need any hardware connected.
SIMULATION_MODE must be True in constants.py (it is by default).

Expected output:
  [1] Simulation mode check ... PASS
  [2] Port detection (sim mode) ... PASS
  [3] Command building ... PASS — X commands, Y read points
  [4] Full simulation run ... 
      Step updates received: X
      ADC results received:  Y elements
      Sample results: FE|273.0 = XXXX, C|193.0 = XXXX ...
  [5] Progress callback ... PASS — reached 100%
  All tests passed.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Make sure simulation mode is on before importing hardware
import constants
assert constants.SIMULATION_MODE, \
    "Set SIMULATION_MODE = True in constants.py before running this test."

from core.hardware import hw, HardwareError

# ── Sample technique data (LAS 2023 Page 1 + Page 2 + Page 4 subset) ──────
SAMPLE_GROUP_DATA = {
    "page_01_condition": {
        "analytical_method": "P:PDA+Integ. Mode",
        "purge_seq1":   "3",
        "source_seq1":  "3 Peak Spark",
        "source_seq2":  "Normal Spark",
        "source_seq3":  "Lamp",
        "source_clean": "Cleaning",
        "preburn_seq1": "200",
        "preburn_seq2": "200",
        "preburn_seq3": "0",
        "integ_seq1":   "300",
        "integ_seq2":   "23",
        "integ_seq3":   "0",
        "clean_value":  "0",
    },
    "page_02_attenuator": {
        "rows": [
            {"element": "FE", "wavelength": "273.0",   "att_value": 78},
            {"element": "C",  "wavelength": "193.0",   "att_value": 49},
            {"element": "SI", "wavelength": "212.4",   "att_value": 41},
            {"element": "MN", "wavelength": "293.3",   "att_value": 40},
            {"element": "P",  "wavelength": "178.3",   "att_value": 81},
        ]
    },
    "page_04_channel": {
        "rows": [
            {"ele_name": "FE", "w_length": "273.0", "seq": "1", "w_no": ""},
            {"ele_name": "C",  "w_length": "193.0", "seq": "2", "w_no": ""},
            {"ele_name": "SI", "w_length": "212.4", "seq": "2", "w_no": ""},
            {"ele_name": "MN", "w_length": "293.3", "seq": "2", "w_no": ""},
            {"ele_name": "P",  "w_length": "178.3", "seq": "1", "w_no": ""},
        ]
    },
}


def run_tests():
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            print(f"  [PASS] {name}" + (f" — {detail}" if detail else ""))
            passed += 1
        else:
            print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))
            failed += 1

    print("\n" + "="*55)
    print("  SpectraSoft Hardware Module Tests (Simulation)")
    print("="*55 + "\n")

    # ── Test 1: Simulation mode is on ────────────────────────────────
    print("[1] Simulation mode check")
    check("SIMULATION_MODE is True", constants.SIMULATION_MODE)

    # ── Test 2: Port detection in sim mode ───────────────────────────
    print("\n[2] Port detection (simulation mode)")
    result = hw.detect_port()
    check("detect_port() returns False in sim mode", result == False)
    check("is_connected is False in sim mode", hw.is_connected == False)

    # ── Test 3: Command building ──────────────────────────────────────
    print("\n[3] Command building from technique data")
    try:
        commands, read_points = hw._build_commands(SAMPLE_GROUP_DATA)
        check("Commands generated (list not empty)", len(commands) > 0,
              f"{len(commands)} commands")
        check("Read points generated", len(read_points) > 0,
              f"{len(read_points)} read points")

        # Check command format
        output_cmds = [c for c in commands if c.startswith("O,")]
        delay_cmds  = [c for c in commands if c.startswith("T,")]
        read_cmds   = [c for c in commands if c.startswith("I")]
        check("Output commands present", len(output_cmds) > 0,
              f"{len(output_cmds)} output cmds")
        check("Delay commands present", len(delay_cmds) > 0,
              f"{len(delay_cmds)} delay cmds")
        check("Read commands match read points",
              len(read_cmds) == len(read_points))

        # Check purge delay is correct (3 seconds = 3000ms)
        purge_delay = [c for c in commands if "T,3000" in c]
        check("Purge delay is 3000ms", len(purge_delay) > 0)

    except Exception as e:
        check("Command building did not raise exception", False, str(e))
        commands, read_points = [], []

    # ── Test 4: Full simulation run ───────────────────────────────────
    print("\n[4] Full simulation run")
    steps_received = []
    final_pct      = [0]

    def progress(msg, pct):
        steps_received.append((msg, pct))
        final_pct[0] = pct

    try:
        results = hw.run_analysis(SAMPLE_GROUP_DATA, progress_cb=progress)

        check("run_analysis returned a dict", isinstance(results, dict))
        check("Progress steps received", len(steps_received) > 0,
              f"{len(steps_received)} steps")
        check("Final progress is 100%", final_pct[0] == 100)
        check("ADC results received", len(results) > 0,
              f"{len(results)} elements")

        # ADC values should be in 0–4095 range
        all_valid = all(0 <= v <= 4095 for v in results.values())
        check("All ADC values in 0–4095 range", all_valid)

        # Show sample results
        if results:
            print("\n     Sample ADC results:")
            for key, val in list(results.items())[:5]:
                print(f"       {key:20s} = {val}")
            if len(results) > 5:
                print(f"       ... and {len(results)-5} more")

    except HardwareError as e:
        check("run_analysis did not raise HardwareError", False, str(e))
    except Exception as e:
        check("run_analysis did not raise exception", False, str(e))

    # ── Test 5: Error when not in sim mode and not connected ──────────
    print("\n[5] HardwareError raised when disconnected (non-sim)")
    import core.hardware  # Import the module so we can change its local variable
    original_sim = core.hardware.SIMULATION_MODE
    core.hardware.SIMULATION_MODE = False   # temporarily disable sim directly in the module
    try:
        hw.is_connected = False
        hw.run_analysis(SAMPLE_GROUP_DATA)
        check("Should have raised HardwareError", False)
    except HardwareError:
        check("HardwareError raised correctly", True)
    except Exception as e:
        check("HardwareError raised correctly", False, f"Got {type(e).__name__}: {e}")
    finally:
        core.hardware.SIMULATION_MODE = original_sim  # restore

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "="*55)
    print(f"  Results: {passed} passed, {failed} failed")
    print("="*55 + "\n")

    if failed == 0:
        print("  All tests passed. Hardware module is working correctly.")
        print("  When SIMULATION_MODE = False and hardware is connected,")
        print("  the same run_analysis() call will use real serial comms.\n")
    else:
        print("  Some tests failed. Check output above.\n")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)