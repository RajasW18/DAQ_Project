"""
STM32 Generic Hardware Abstraction Layer
Ready for future hardware migration to 3.3V ARM Cortex-M controllers.
"""

from typing import Dict, Any
from .board_base import BoardHAL, PinCapability

class STM32GenericHAL(BoardHAL):
    def __init__(self):
        super().__init__(name="STM32 Nucleo/Generic", architecture="ARM Cortex-M4 32-bit", default_baud=9600)
        self._init_pins()

    def _init_pins(self):
        # Generic digital pins mapping (D0 to D31)
        for pin in range(32):
            self._pins[pin] = PinCapability(
                pin_id=pin,
                name=f"PA{pin}",
                is_digital=True,
                is_analog_in=False,
                is_pwm=(pin in {2, 3, 5, 6, 9}),
                voltage_level=3.3,
                safe_default=0
            )

        # Analog channels A0 to A7
        for ch in range(8):
            self._analog_pins[ch] = PinCapability(
                pin_id=ch,
                name=f"A{ch}",
                is_digital=False,
                is_analog_in=True,
                is_pwm=False,
                voltage_level=3.3,
                safe_default=0
            )

    def get_pinout_summary(self) -> Dict[str, Any]:
        return {
            "board": self.name,
            "architecture": self.architecture,
            "operating_voltage": "3.3V",
            "digital_io_count": 32,
            "pwm_pins": [2, 3, 5, 6, 9],
            "analog_channels": [f"A{i}" for i in range(8)],
            "adc_resolution": "12-bit (0-4095)",
            "uart_default_baud": self.default_baud,
            "safe_reserved_pins": [0, 1]
        }
