from .board_base import BoardHAL, PinCapability
from .atmega2560 import ATmega2560HAL
from .stm32_base import STM32GenericHAL
from .registry import get_board

__all__ = ["BoardHAL", "PinCapability", "ATmega2560HAL", "STM32GenericHAL", "get_board"]
