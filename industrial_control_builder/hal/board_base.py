"""
Hardware Abstraction Layer (HAL) - Base Class
Enables switching controllers (ATmega2560, STM32, ESP32) without changing sequence or business logic.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

@dataclass
class PinCapability:
    pin_id: int
    name: str
    is_digital: bool = True
    is_analog_in: bool = False
    is_pwm: bool = False
    is_interrupt: bool = False
    voltage_level: float = 5.0
    safe_default: int = 0  # 0 = LOW

class BoardHAL(ABC):
    """Abstract base class representing an MCU target board."""

    def __init__(self, name: str, architecture: str, default_baud: int = 9600):
        self.name = name
        self.architecture = architecture
        self.default_baud = default_baud
        self._pins: Dict[int, PinCapability] = {}
        self._analog_pins: Dict[int, PinCapability] = {}

    def get_pin(self, pin_id: int) -> Optional[PinCapability]:
        return self._pins.get(pin_id)

    def get_analog_pin(self, analog_channel: int) -> Optional[PinCapability]:
        return self._analog_pins.get(analog_channel)

    def validate_digital_pin(self, pin_id: int) -> bool:
        pin = self.get_pin(pin_id)
        return pin is not None and pin.is_digital

    def validate_pwm_pin(self, pin_id: int) -> bool:
        pin = self.get_pin(pin_id)
        return pin is not None and pin.is_pwm

    def validate_analog_channel(self, channel: int) -> bool:
        return channel in self._analog_pins

    @abstractmethod
    def get_pinout_summary(self) -> Dict[str, any]:
        """Return a structured summary of board capabilities for the LLM context."""
        pass
