"""
ATmega 2560 Pro Hardware Abstraction Layer
Accurate pin mapping: 54 Digital I/O (15 PWM), 16 Analog Inputs.
"""

from typing import Dict, Any
from .board_base import BoardHAL, PinCapability

class ATmega2560HAL(BoardHAL):
    def __init__(self):
        super().__init__(name="ATmega 2560 Pro", architecture="AVR 8-bit", default_baud=9600)
        self._init_pins()

    def _init_pins(self):
        # PWM capable pins on ATmega 2560
        pwm_pins = {2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 44, 45, 46}
        interrupt_pins = {2, 3, 18, 19, 20, 21}

        # Digital Pins D0 through D53
        for pin in range(54):
            self._pins[pin] = PinCapability(
                pin_id=pin,
                name=f"D{pin}",
                is_digital=True,
                is_analog_in=False,
                is_pwm=(pin in pwm_pins),
                is_interrupt=(pin in interrupt_pins),
                voltage_level=5.0,
                safe_default=0
            )

        # Analog Pins A0 through A15 (channels 0 to 15, corresponding digital pins 54-69)
        for ch in range(16):
            self._analog_pins[ch] = PinCapability(
                pin_id=ch,
                name=f"A{ch}",
                is_digital=True,
                is_analog_in=True,
                is_pwm=False,
                is_interrupt=False,
                voltage_level=5.0,
                safe_default=0
            )

    def get_pinout_summary(self) -> Dict[str, Any]:
        return {
            "board": self.name,
            "architecture": self.architecture,
            "operating_voltage": "5.0V",
            "digital_io_count": 54,
            "pwm_pins": [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 44, 45, 46],
            "analog_channels": [f"A{i}" for i in range(16)],
            "adc_resolution": "10-bit (0-1023)",
            "uart_default_baud": self.default_baud,
            "safe_reserved_pins": [0, 1]  # Serial Rx/Tx
        }
