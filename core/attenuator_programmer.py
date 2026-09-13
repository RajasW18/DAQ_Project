"""
SpectraSoft — Attenuator Programmer
Programs attenuator values for all elements.
"""

import time
from typing import Dict, List, Optional
from core.uart_manager import UARTManager

class AttenuatorProgrammer:
    """Programs attenuator values for all 45 elements."""

    ATT_OFFSET = 0x40      # att_value 0 → 0x40, 63 → 0x7F
    TOTAL_ELEMENTS = 45    # ele1...ele45 → indices 0x00...0x2C
    ELEM_DELAY = 0.100     # 100ms between commands

    def __init__(self, uart: UARTManager):
        self.uart = uart

    def program_all(self, att_rows: List[Dict], progress_cb: Optional[callable] = None) -> int:
        """
        Program attenuator values for all elements.

        Args:
            att_rows: List of dicts with 'itg_no' and 'att_value'
            progress_cb: Optional callback function taking (message, percentage)

        Returns:
            Number of elements successfully programmed.
        """
        success_count = 0

        # Sort by ITG No. (primary key)
        att_map = {}
        for row in att_rows:
            itg = row.get("itg_no", 0)
            att = row.get("att_value", 0)
            att_map[itg] = att

        for idx in range(self.TOTAL_ELEMENTS):
            itg = idx + 1
            att_val = att_map.get(itg, 0)
            att_cmd_byte = att_val + self.ATT_OFFSET

            elem_cmd = f"O,A,{idx:02X}"           # ele1 → 0x00
            att_cmd = f"O,A,{att_cmd_byte:02X}"   # att 0 → 0x40

            if progress_cb:
                pct = int((idx / self.TOTAL_ELEMENTS) * 100)
                progress_cb(f"Programming attenuator for ele{itg}...", pct)

            print(f"  ele{itg}: att={att_val} -> {att_cmd}")

            # Select element
            if not self.uart.send_command(elem_cmd, wait_ack=True):
                continue
            time.sleep(self.ELEM_DELAY)

            # Set attenuator (send twice for reliability, like task3)
            if not self.uart.send_command(att_cmd, wait_ack=True):
                continue
            if not self.uart.send_command(att_cmd, wait_ack=True):
                continue

            success_count += 1

        return success_count