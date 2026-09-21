#pragma once

#include <Arduino.h>

namespace StatusLed {

enum class Pattern : uint8_t {
  Off = 0,
  Boot,
  Ready,
  Busy,
  Error,
  Wifi,
  Thinking,
};

bool begin();
void setPattern(Pattern p);
void setRgb(uint8_t r, uint8_t g, uint8_t b);
void tick();  // call from loop for animated patterns

}  // namespace StatusLed
