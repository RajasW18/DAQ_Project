#pragma once

#include <Arduino.h>

/**
 * Universal Hardware Abstraction Layer Header
 * Provides hardware-independent pin and timer primitives.
 */

#if defined(ARDUINO_AVR_MEGA2560) || defined(__AVR_ATmega2560__) || defined(MCU_ATMEGA2560)
    #define BOARD_NAME "ATmega 2560 Pro"
    #define MAX_DIGITAL_PINS 54
    #define MAX_ANALOG_PINS  16
    #define HAS_HARDWARE_TIMER1 1
#elif defined(STM32F4xx) || defined(MCU_STM32)
    #define BOARD_NAME "STM32 Generic"
    #define MAX_DIGITAL_PINS 64
    #define MAX_ANALOG_PINS  16
    #define HAS_HARDWARE_TIMER1 0
#else
    #define BOARD_NAME "Generic MCU"
    #define MAX_DIGITAL_PINS 32
    #define MAX_ANALOG_PINS  8
    #define HAS_HARDWARE_TIMER1 0
#endif

// Safe default baud rate
#ifndef SERIAL_BAUD
#define SERIAL_BAUD 9600
#endif

// Emergency Safe State
inline void hal_enter_safe_state() {
    // Drive standard digital output pins LOW
    for (uint8_t p = 2; p < 14; p++) {
        pinMode(p, OUTPUT);
        digitalWrite(p, LOW);
    }
}
