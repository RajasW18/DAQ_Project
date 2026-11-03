"""
HAL Registry for retrieving active board definitions dynamically.
"""

from typing import Dict, Type
from .board_base import BoardHAL
from .atmega2560 import ATmega2560HAL
from .stm32_base import STM32GenericHAL

_BOARD_REGISTRY: Dict[str, Type[BoardHAL]] = {
    "atmega2560": ATmega2560HAL,
    "atmega2560pro": ATmega2560HAL,
    "mega": ATmega2560HAL,
    "arduino_mega": ATmega2560HAL,
    "stm32": STM32GenericHAL,
    "nucleo": STM32GenericHAL,
}

def get_board(name: str = "atmega2560") -> BoardHAL:
    """Retrieve an initialized BoardHAL instance by board name."""
    clean_name = name.lower().replace(" ", "").replace("-", "").replace("_", "")
    for key, cls in _BOARD_REGISTRY.items():
        normalized_key = key.replace("_", "")
        if clean_name == normalized_key:
            return cls()
    raise ValueError(f"Unsupported controller {name!r}. Registered boards: {', '.join(_BOARD_REGISTRY)}")
