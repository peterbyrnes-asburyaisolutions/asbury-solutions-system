#pragma once

#include <Arduino.h>

namespace Oled {

bool begin(uint8_t addr = 0x3C);
bool isPresent();
void clear();
void setCursor(uint8_t col, uint8_t row);
void print(const char* text);
void println(const char* text);
void showBanner(const char* version);
void showStatus(const char* line1, const char* line2);
void flush();

}  // namespace Oled
