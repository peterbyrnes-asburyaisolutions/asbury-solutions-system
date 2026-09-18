#pragma once

// Axiometa Genesis Mini pin map (ESP32-S3-Mini-1-N4R2)
// Four AX22 modular ports: Port 1 hosts the microSD adapter;
// Ports 2–4 expose GPIO triples for pluggable modules.

#ifndef BOARD_PINS_H
#define BOARD_PINS_H

#include <Arduino.h>

// On-board status NeoPixel (avoid PIN_NEOPIXEL — reserved by Arduino-ESP32)
static constexpr uint8_t PIN_STATUS_LED = 21;
static constexpr uint8_t STATUS_LED_COUNT = 1;

// User / boot-adjacent button (active low)
static constexpr uint8_t PIN_BUTTON = 45;

// Shared I2C bus (OLED, sensors)
static constexpr uint8_t PIN_I2C_SDA = 10;
static constexpr uint8_t PIN_I2C_SCL = 11;

// Shared SPI bus (SD card on Port 1, future SPI modules)
static constexpr uint8_t PIN_SPI_MOSI = 12;
static constexpr uint8_t PIN_SPI_MISO = 13;
static constexpr uint8_t PIN_SPI_SCK  = 14;

// Port 1 — microSD (SPI CS)
static constexpr uint8_t PIN_SD_CS = 15;
static constexpr uint8_t AX22_PORT1_CS = PIN_SD_CS;

// AX22 port GPIO triples: {a, b, c}
// Convention: a = primary digital / 1-Wire / DHT data,
//             b = secondary digital / PWM / beep,
//             c = analog-capable or IRQ / CS override.
struct Ax22PortPins {
  uint8_t a;
  uint8_t b;
  uint8_t c;
};

static constexpr Ax22PortPins AX22_PORT2 = {16, 17, 18};
static constexpr Ax22PortPins AX22_PORT3 = {38, 39, 40};
static constexpr Ax22PortPins AX22_PORT4 = {41, 42, 47};

static constexpr uint8_t AX22_PORT_COUNT = 4;
static constexpr uint8_t AX22_FIRST_MODULE_PORT = 2;
static constexpr uint8_t AX22_LAST_MODULE_PORT = 4;

inline const Ax22PortPins* ax22PinsForPort(uint8_t port) {
  switch (port) {
    case 2: return &AX22_PORT2;
    case 3: return &AX22_PORT3;
    case 4: return &AX22_PORT4;
    default: return nullptr;
  }
}

#endif  // BOARD_PINS_H
