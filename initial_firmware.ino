/*
 * Spectroscopy Controller
 * =======================
 * Target : ATmega 2560 Pro
 * Baud   : 9600
 *
 * Command protocol (received from Python):
 *   O,<port>,<value>\n  -- Set output port (port = A or B)
 *   I\n                 -- Read 12-bit value from INPUT_PINS
 *   T,<ms>\n            -- Non-blocking delay in milliseconds
 *
 * Response protocol (sent back to Python):
 *   K\n                 -- Acknowledgment for O and T commands
 *   D,<value>\n         -- ADC result; also acknowledges I commands
 *   # <text>\n          -- Debug message (ignored by Python)
 *
 * Flow control:
 *   Serial RX is always drained, including during a T delay.
 *   Buffered commands execute only when the delay has expired.
 */

#include <Arduino.h>
#include <stdlib.h>

// ============================================================================
// PIN DEFINITIONS
// ============================================================================

// Port A: 8 digital output bits
const uint8_t PORTA_PINS[8] = {
  22, 23, 24, 25, 26, 27, 28, 29
};

// Port B: 7 digital output bits
const uint8_t PORTB_PINS[7] = {
  32, 33, 34, 35, 36, 37, 38
};

// Pulse pin
const uint8_t PULSE_PIN = 30;

// 12-bit input lines
const uint8_t INPUT_PINS[12] = {
  54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65
};

// Built-in LED
const uint8_t DEBUG_LED = 13;

// ============================================================================
// STATE VARIABLES
// ============================================================================

String inputString = "";
bool commandReady = false;

unsigned long delayEndTime = 0;
bool inDelay = false;

uint8_t lastPortAValue = 0;

unsigned long adcTriggerTime = 0;
bool adcReadReady = false;

void processCommand(String cmd);
void readAndSendADC();
void writePortA(uint8_t val);
void writePortB(uint8_t val);

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  Serial.begin(9600);
  inputString.reserve(128);

  pinMode(DEBUG_LED, OUTPUT);
  digitalWrite(DEBUG_LED, LOW);

  pinMode(PULSE_PIN, OUTPUT);
  digitalWrite(PULSE_PIN, LOW);

  for (int i = 0; i < 8; i++) {
    pinMode(PORTA_PINS[i], OUTPUT);
    digitalWrite(PORTA_PINS[i], LOW);
  }

  for (int i = 0; i < 7; i++) {
    pinMode(PORTB_PINS[i], OUTPUT);
    digitalWrite(PORTB_PINS[i], LOW);
  }

  for (int i = 0; i < 12; i++) {
    pinMode(INPUT_PINS[i], INPUT);
  }

  Serial.println("# Spectroscopy Controller Ready.");
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
  // 1. Always drain the serial RX buffer.
  while (Serial.available() > 0) {
    char c = (char)Serial.read();

    if (c == '\n' || c == '\r') {
      if (inputString.length() > 0) {
        commandReady = true;
      }
    } else {
      // Prevent input buffer overflow.
      if (inputString.length() < 127) {
        inputString += c;
      }
    }
  }

  // 2. Check whether the active delay has expired.
  if (inDelay) {
    if ((long)(millis() - delayEndTime) >= 0) {
      inDelay = false;
    } else {
      return;
    }
  }

  // 3. Process one buffered command.
  if (commandReady) {
    digitalWrite(DEBUG_LED, !digitalRead(DEBUG_LED));

    processCommand(inputString);

    inputString = "";
    commandReady = false;
  }

  // 4. Check whether the ADC settling period has elapsed.
  if (adcReadReady && millis() - adcTriggerTime >= 100UL) {
    adcReadReady = false;
    readAndSendADC();
  }
}

// ============================================================================
// COMMAND PROCESSOR
// ============================================================================

void processCommand(String cmd) {
  cmd.trim();

  if (cmd.length() == 0) {
    return;
  }

  char type = toupper(cmd.charAt(0));

  // --------------------------------------------------------------------------
  // O,<port>,<value> -- Set output port
  // --------------------------------------------------------------------------

  if (type == 'O') {
    int firstComma = cmd.indexOf(',');
    int secondComma = cmd.indexOf(',', firstComma + 1);

    if (firstComma == -1 || secondComma == -1) {
      Serial.println("# ERROR: Malformed O command");
      return;
    }

    char port = toupper(cmd.charAt(firstComma + 1));
    uint8_t val = (uint8_t)strtoul(
      cmd.substring(secondComma + 1).c_str(),
      NULL,
      16
    );

    if (port == 'A') {
      writePortA(val);
    } else if (port == 'B') {
      writePortB(val);
    } else {
      Serial.println("# ERROR: Unknown port");
      return;
    }

    Serial.println("K");
  }

  // --------------------------------------------------------------------------
  // I -- Read 12-bit input value
  // --------------------------------------------------------------------------

  else if (type == 'I') {
    readAndSendADC();
  }

  // --------------------------------------------------------------------------
  // T,<ms> -- Start non-blocking delay
  // --------------------------------------------------------------------------

  else if (type == 'T') {
    int comma = cmd.indexOf(',');

    if (comma == -1) {
      Serial.println("# ERROR: Malformed T command");
      return;
    }

    // Preserves the original hexadecimal time parsing.
    unsigned long ms = strtoul(
      cmd.substring(comma + 1).c_str(),
      NULL,
      16
    );

    delayEndTime = millis() + ms;
    inDelay = true;

    // Acknowledge immediately.
    Serial.println("K");
  }

  // --------------------------------------------------------------------------
  // Unknown command
  // --------------------------------------------------------------------------

  else {
    Serial.print("# ERROR: Unknown command: ");
    Serial.println(cmd);
  }
}

// ============================================================================
// ADC READER
// ============================================================================

/*
 * Reads the 12 digital input lines and sends the result as D,<value>.
 * Called automatically 100 ms after the 0x3C trigger.
 */

void readAndSendADC() {
  uint16_t result = 0;

  for (int i = 0; i < 12; i++) {
    if (digitalRead(INPUT_PINS[i])) {
      result |= (1U << i);
    }
  }

  Serial.print("D,");
  Serial.println(result);
}

// ============================================================================
// GPIO HELPERS
// ============================================================================

/*
 * writePortA:
 *   Writes all 8 output bits.
 *   Generates a 40 ms pulse when the output value changes.
 *
 * Special ADC trigger:
 *   0x7C -- First ADC trigger
 *   0x3C -- Second ADC trigger; schedules an ADC read
 */

void writePortA(uint8_t val) {

  // Write the 8 output bits.
  for (int i = 0; i < 8; i++) {
    digitalWrite(PORTA_PINS[i], (val >> i) & 0x01);
  }

  // Queue ADC read after the 0x3C trigger.
  if (val == 0x3C) {
    adcTriggerTime = millis();
    adcReadReady = true;
  }

  // Generate a pulse only when the output value changes.
  if (val != lastPortAValue) {
    digitalWrite(PULSE_PIN, HIGH);
    delay(40);
    digitalWrite(PULSE_PIN, LOW);
    lastPortAValue = val;
  }
}

/*
 * writePortB:
 *   Uses the 7 least-significant bits.
 *   Inverts the output bits for the transistor interface.
 */

void writePortB(uint8_t val) {
  val &= 0x7F;
  val = (uint8_t)~val;

  for (int i = 0; i < 7; i++) {
    digitalWrite(PORTB_PINS[i], (val >> i) & 0x01);
  }
}
