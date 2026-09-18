#include "status_led.h"

#include "board_pins.h"

#include <Adafruit_NeoPixel.h>

namespace StatusLed {
namespace {

Adafruit_NeoPixel pixel(NEOPIXEL_COUNT, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);
Pattern current = Pattern::Off;
uint32_t lastTick = 0;
uint8_t phase = 0;

void apply(uint8_t r, uint8_t g, uint8_t b) {
  pixel.setPixelColor(0, pixel.Color(r, g, b));
  pixel.show();
}

}  // namespace

bool begin() {
  pixel.begin();
  pixel.clear();
  pixel.setBrightness(40);
  pixel.show();
  setPattern(Pattern::Boot);
  return true;
}

void setRgb(uint8_t r, uint8_t g, uint8_t b) {
  current = Pattern::Off;
  apply(r, g, b);
}

void setPattern(Pattern p) {
  current = p;
  phase = 0;
  lastTick = millis();
  switch (p) {
    case Pattern::Off:
      apply(0, 0, 0);
      break;
    case Pattern::Boot:
      apply(0, 0, 48);
      break;
    case Pattern::Ready:
      apply(0, 48, 12);
      break;
    case Pattern::Busy:
      apply(48, 32, 0);
      break;
    case Pattern::Error:
      apply(64, 0, 0);
      break;
    case Pattern::Wifi:
      apply(0, 24, 64);
      break;
    case Pattern::Thinking:
      apply(40, 0, 48);
      break;
    default: {
      Pattern unreachable = p;
      (void)unreachable;
      apply(0, 0, 0);
      break;
    }
  }
}

void tick() {
  uint32_t now = millis();
  if (now - lastTick < 120) {
    return;
  }
  lastTick = now;
  phase++;

  switch (current) {
    case Pattern::Busy: {
      uint8_t v = (phase & 1) ? 48 : 8;
      apply(v, v / 2, 0);
      break;
    }
    case Pattern::Thinking: {
      uint8_t v = 20 + (phase % 5) * 8;
      apply(v, 0, v + 8);
      break;
    }
    case Pattern::Wifi: {
      uint8_t v = (phase % 6) * 10;
      apply(0, v / 2, 20 + v);
      break;
    }
    case Pattern::Error: {
      apply((phase & 1) ? 64 : 8, 0, 0);
      break;
    }
    case Pattern::Off:
    case Pattern::Boot:
    case Pattern::Ready:
      break;
    default:
      break;
  }
}

}  // namespace StatusLed
