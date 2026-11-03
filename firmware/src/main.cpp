/**
 * Universal Firmware Engine for Industrial Control Builder
 * Target: ATmega 2560 Pro / Compatible AVR / STM32
 * Baud: 9600 bps
 * Protocol: ASCII Line-Based Text Commands
 */

#include <Arduino.h>
#include "../include/hal_mcu.h"

// Firmware Version
#define FW_VERSION "1.2.0-UNIVERSAL"

// Maximum sequence steps buffered in MCU RAM
#define MAX_SEQ_STEPS 64
#define MAX_POLL_CHANNELS 8
#define CMD_BUFFER_LEN 64

// Step definition for sequence execution
enum StepType {
    STEP_NONE = 0,
    STEP_WRITE_DIGITAL,
    STEP_WRITE_PWM,
    STEP_READ_DIGITAL,
    STEP_READ_ANALOG,
    STEP_DELAY_MS
};

struct SequenceStep {
    StepType type;
    uint8_t pin;
    uint16_t value; // delay in ms, or write value
};

struct Poller {
    bool active;
    uint8_t pin;
    bool is_analog;
    uint32_t interval_ms;
    uint32_t last_poll_ms;
};

// Global State
static SequenceStep seq_buffer[MAX_SEQ_STEPS];
static uint8_t seq_count = 0;
static uint8_t seq_current_step = 0;
static bool seq_is_running = false;
static uint32_t seq_step_start_time = 0;

static Poller pollers[MAX_POLL_CHANNELS];

static char rx_line[CMD_BUFFER_LEN];
static uint8_t rx_idx = 0;

// Forward declarations
void process_command(char* cmd);
void run_sequence_engine();
void run_polling_engine();
void execute_estop();

void setup() {
    Serial.begin(SERIAL_BAUD);
    while (!Serial && millis() < 1000) {}

    // Initialize pollers
    for (uint8_t i = 0; i < MAX_POLL_CHANNELS; i++) {
        pollers[i].active = false;
    }

    // Default safe state
    hal_enter_safe_state();

    Serial.println();
    Serial.print(F("# READY: Universal Industrial Firmware "));
    Serial.print(F(FW_VERSION));
    Serial.print(F(" on "));
    Serial.println(F(BOARD_NAME));
}

void loop() {
    // 1. Process UART incoming bytes non-blockingly
    while (Serial.available() > 0) {
        char c = (char)Serial.read();
        if (c == '\r' || c == '\n') {
            if (rx_idx > 0) {
                rx_line[rx_idx] = '\0';
                process_command(rx_line);
                rx_idx = 0;
            }
        } else if (rx_idx < CMD_BUFFER_LEN - 1) {
            rx_line[rx_idx++] = c;
        }
    }

    // 2. Advance non-blocking sequence execution
    if (seq_is_running) {
        run_sequence_engine();
    }

    // 3. Advance non-blocking polling engine
    run_polling_engine();
}

/**
 * Execute immediate Emergency Stop
 */
void execute_estop() {
    seq_is_running = false;
    seq_count = 0;
    seq_current_step = 0;

    for (uint8_t i = 0; i < MAX_POLL_CHANNELS; i++) {
        pollers[i].active = false;
    }

    hal_enter_safe_state();
    Serial.println(F("ACK ESTOP SAFE"));
}

/**
 * Parse and dispatch incoming ASCII text commands
 */
void process_command(char* cmd) {
    // Strip leading whitespace
    while (*cmd == ' ' || *cmd == '\t') cmd++;
    if (*cmd == '\0' || *cmd == '#') return; // Empty or comment

    // PING
    if (strcmp(cmd, "PING") == 0) {
        Serial.println(F("PONG"));
        return;
    }

    // ESTOP
    if (strcmp(cmd, "ESTOP") == 0) {
        execute_estop();
        return;
    }

    // STATUS
    if (strcmp(cmd, "STATUS") == 0) {
        Serial.print(F("STATUS board="));
        Serial.print(F(BOARD_NAME));
        Serial.print(F(" seq_running="));
        Serial.print(seq_is_running ? 1 : 0);
        Serial.print(F(" seq_steps="));
        Serial.print(seq_count);
        Serial.print(F(" uptime="));
        Serial.println(millis());
        return;
    }

    // PIN <pin> <MODE: OUT|IN|PULLUP|PWM>
    if (strncmp(cmd, "PIN ", 4) == 0) {
        char* token = strtok(cmd + 4, " ");
        if (!token) { Serial.println(F("ERR PIN_SYNTAX")); return; }
        uint8_t pin = (uint8_t)atoi(token);
        token = strtok(NULL, " ");
        if (!token) { Serial.println(F("ERR PIN_SYNTAX")); return; }

        if (strcmp(token, "OUT") == 0 || strcmp(token, "OUTPUT") == 0) {
            pinMode(pin, OUTPUT);
            digitalWrite(pin, LOW);
            Serial.print(F("ACK PIN ")); Serial.print(pin); Serial.println(F(" OUT"));
        } else if (strcmp(token, "IN") == 0 || strcmp(token, "INPUT") == 0) {
            pinMode(pin, INPUT);
            Serial.print(F("ACK PIN ")); Serial.print(pin); Serial.println(F(" IN"));
        } else if (strcmp(token, "PULLUP") == 0) {
            pinMode(pin, INPUT_PULLUP);
            Serial.print(F("ACK PIN ")); Serial.print(pin); Serial.println(F(" PULLUP"));
        } else if (strcmp(token, "PWM") == 0) {
            pinMode(pin, OUTPUT);
            analogWrite(pin, 0);
            Serial.print(F("ACK PIN ")); Serial.print(pin); Serial.println(F(" PWM"));
        } else {
            Serial.println(F("ERR UNKNOWN_PIN_MODE"));
        }
        return;
    }

    // W <pin> <val> (Digital Write 0/1 or PWM 0-255)
    if (cmd[0] == 'W' && cmd[1] == ' ') {
        char* token = strtok(cmd + 2, " ");
        if (!token) { Serial.println(F("ERR W_SYNTAX")); return; }
        uint8_t pin = (uint8_t)atoi(token);
        token = strtok(NULL, " ");
        if (!token) { Serial.println(F("ERR W_SYNTAX")); return; }
        uint16_t val = (uint16_t)atoi(token);

        if (val <= 1) {
            digitalWrite(pin, val);
        } else {
            analogWrite(pin, (uint8_t)val);
        }
        Serial.print(F("ACK W ")); Serial.print(pin); Serial.print(' '); Serial.println(val);
        return;
    }

    // R <pin> (Read Digital)
    if (cmd[0] == 'R' && cmd[1] == ' ') {
        uint8_t pin = (uint8_t)atoi(cmd + 2);
        int val = digitalRead(pin);
        Serial.print(F("VAL ")); Serial.print(pin); Serial.print(' '); Serial.println(val);
        return;
    }

    // A <analog_pin_idx> (Read Analog A0..A15)
    if (cmd[0] == 'A' && cmd[1] == ' ') {
        uint8_t apin = (uint8_t)atoi(cmd + 2);
        int val = analogRead(apin);
        Serial.print(F("VAL A")); Serial.print(apin); Serial.print(' '); Serial.println(val);
        return;
    }

    // POLL <pin> <interval_ms> [A]
    // Example: POLL 0 500 A -> poll analog pin 0 every 500ms
    // Example: POLL 12 100 D -> poll digital pin 12 every 100ms
    if (strncmp(cmd, "POLL ", 5) == 0) {
        char* token = strtok(cmd + 5, " ");
        if (!token) { Serial.println(F("ERR POLL_SYNTAX")); return; }
        uint8_t pin = (uint8_t)atoi(token);

        token = strtok(NULL, " ");
        if (!token) { Serial.println(F("ERR POLL_SYNTAX")); return; }
        uint32_t interval = (uint32_t)atol(token);

        token = strtok(NULL, " ");
        bool is_analog = (token && (token[0] == 'A' || token[0] == 'a'));

        // Assign to first available slot
        int8_t slot = -1;
        for (uint8_t i = 0; i < MAX_POLL_CHANNELS; i++) {
            if (pollers[i].active && pollers[i].pin == pin && pollers[i].is_analog == is_analog) {
                slot = i;
                break;
            }
            if (!pollers[i].active && slot == -1) {
                slot = i;
            }
        }

        if (slot >= 0) {
            pollers[slot].active = true;
            pollers[slot].pin = pin;
            pollers[slot].is_analog = is_analog;
            pollers[slot].interval_ms = (interval < 10) ? 10 : interval;
            pollers[slot].last_poll_ms = millis();
            Serial.print(F("ACK POLL ")); Serial.print(pin); Serial.println(F(" OK"));
        } else {
            Serial.println(F("ERR POLL_SLOTS_FULL"));
        }
        return;
    }

    // POLL_STOP <pin>
    if (strncmp(cmd, "POLL_STOP ", 10) == 0) {
        uint8_t pin = (uint8_t)atoi(cmd + 10);
        for (uint8_t i = 0; i < MAX_POLL_CHANNELS; i++) {
            if (pollers[i].active && pollers[i].pin == pin) {
                pollers[i].active = false;
            }
        }
        Serial.print(F("ACK POLL_STOP ")); Serial.println(pin);
        return;
    }

    // Sequence Commands:
    // SEQ_CLEAR
    if (strcmp(cmd, "SEQ_CLEAR") == 0) {
        seq_is_running = false;
        seq_count = 0;
        seq_current_step = 0;
        Serial.println(F("ACK SEQ_CLEAR"));
        return;
    }

    // SEQ_ADD <TYPE> <PIN> <VAL_OR_DELAY>
    // e.g., SEQ_ADD W 13 1
    // e.g., SEQ_ADD DLY 200
    // e.g., SEQ_ADD A 0
    if (strncmp(cmd, "SEQ_ADD ", 8) == 0) {
        if (seq_count >= MAX_SEQ_STEPS) {
            Serial.println(F("ERR SEQ_OVERFLOW"));
            return;
        }

        char* token = strtok(cmd + 8, " ");
        if (!token) { Serial.println(F("ERR SEQ_SYNTAX")); return; }

        SequenceStep& step = seq_buffer[seq_count];

        if (strcmp(token, "W") == 0) {
            token = strtok(NULL, " ");
            if (!token) { Serial.println(F("ERR SEQ_SYNTAX")); return; }
            step.pin = (uint8_t)atoi(token);
            token = strtok(NULL, " ");
            if (!token) { Serial.println(F("ERR SEQ_SYNTAX")); return; }
            step.value = (uint16_t)atoi(token);
            step.type = (step.value <= 1) ? STEP_WRITE_DIGITAL : STEP_WRITE_PWM;
            seq_count++;
            Serial.print(F("ACK SEQ_ADD ")); Serial.println(seq_count);
        } else if (strcmp(token, "DLY") == 0) {
            token = strtok(NULL, " ");
            if (!token) { Serial.println(F("ERR SEQ_SYNTAX")); return; }
            step.type = STEP_DELAY_MS;
            step.value = (uint16_t)atoi(token);
            seq_count++;
            Serial.print(F("ACK SEQ_ADD ")); Serial.println(seq_count);
        } else if (strcmp(token, "R") == 0) {
            token = strtok(NULL, " ");
            if (!token) { Serial.println(F("ERR SEQ_SYNTAX")); return; }
            step.type = STEP_READ_DIGITAL;
            step.pin = (uint8_t)atoi(token);
            seq_count++;
            Serial.print(F("ACK SEQ_ADD ")); Serial.println(seq_count);
        } else if (strcmp(token, "A") == 0) {
            token = strtok(NULL, " ");
            if (!token) { Serial.println(F("ERR SEQ_SYNTAX")); return; }
            step.type = STEP_READ_ANALOG;
            step.pin = (uint8_t)atoi(token);
            seq_count++;
            Serial.print(F("ACK SEQ_ADD ")); Serial.println(seq_count);
        } else {
            Serial.println(F("ERR UNKNOWN_SEQ_OP"));
        }
        return;
    }

    // SEQ_RUN
    if (strcmp(cmd, "SEQ_RUN") == 0) {
        if (seq_count == 0) {
            Serial.println(F("ERR SEQ_EMPTY"));
            return;
        }
        seq_current_step = 0;
        seq_is_running = true;
        seq_step_start_time = millis();
        Serial.println(F("ACK SEQ_RUN STARTED"));
        return;
    }

    // SEQ_STOP
    if (strcmp(cmd, "SEQ_STOP") == 0) {
        seq_is_running = false;
        Serial.println(F("ACK SEQ_STOPPED"));
        return;
    }

    // Fallback unknown command
    Serial.print(F("ERR UNKNOWN_CMD "));
    Serial.println(cmd);
}

/**
 * Non-blocking Step-by-Step Sequence Runner
 */
void run_sequence_engine() {
    if (seq_current_step >= seq_count) {
        seq_is_running = false;
        Serial.println(F("NOTIFY SEQ_COMPLETED"));
        return;
    }

    SequenceStep& step = seq_buffer[seq_current_step];

    switch (step.type) {
        case STEP_WRITE_DIGITAL:
            digitalWrite(step.pin, step.value ? HIGH : LOW);
            seq_current_step++;
            seq_step_start_time = millis();
            break;

        case STEP_WRITE_PWM:
            analogWrite(step.pin, (uint8_t)step.value);
            seq_current_step++;
            seq_step_start_time = millis();
            break;

        case STEP_READ_DIGITAL: {
            int val = digitalRead(step.pin);
            Serial.print(F("DATA R_")); Serial.print(step.pin); Serial.print(' '); Serial.println(val);
            seq_current_step++;
            seq_step_start_time = millis();
            break;
        }

        case STEP_READ_ANALOG: {
            int val = analogRead(step.pin);
            Serial.print(F("DATA A_")); Serial.print(step.pin); Serial.print(' '); Serial.println(val);
            seq_current_step++;
            seq_step_start_time = millis();
            break;
        }

        case STEP_DELAY_MS:
            if (millis() - seq_step_start_time >= step.value) {
                seq_current_step++;
                seq_step_start_time = millis();
            }
            break;

        default:
            seq_current_step++;
            break;
    }
}

/**
 * Non-blocking Periodic Channel Polling Engine
 */
void run_polling_engine() {
    uint32_t now = millis();
    for (uint8_t i = 0; i < MAX_POLL_CHANNELS; i++) {
        if (!pollers[i].active) continue;

        if (now - pollers[i].last_poll_ms >= pollers[i].interval_ms) {
            pollers[i].last_poll_ms = now;

            if (pollers[i].is_analog) {
                int val = analogRead(pollers[i].pin);
                Serial.print(F("DATA A"));
                Serial.print(pollers[i].pin);
                Serial.print(' ');
                Serial.print(val);
                Serial.print(' ');
                Serial.println(now);
            } else {
                int val = digitalRead(pollers[i].pin);
                Serial.print(F("DATA D"));
                Serial.print(pollers[i].pin);
                Serial.print(' ');
                Serial.print(val);
                Serial.print(' ');
                Serial.println(now);
            }
        }
    }
}
